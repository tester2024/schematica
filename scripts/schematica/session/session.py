"""Session: the orchestrator holding grid + palette + version + history.

This is the primary library API surface. The CLI is a thin shell over it.

The session can run in two storage backends:
  * dense  (default)  -- VoxelGrid, a single contiguous ``np.uint16`` array.
  * chunked           -- ChunkedGrid, sparse chunk map; only touched chunks are
                        allocated. Use this for big maps (100+ chunks) so RAM
                        cost scales with built volume, not grid extent.

Both backends expose the same read/write/apply/replace surface so the
add/subtract/paint pipeline is backend-agnostic.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..blocks.block import AIR, Block
from ..blocks.registry import BlockRegistry
from ..core.chunked import DEFAULT_CHUNK_SIZE, ChunkedGrid
from ..core.palette import Palette
from ..core.voxel import VoxelGrid
from ..shapes.base import Shape, shape_bounds
from .history import Delta, History, diff_delta


@dataclass
class Session:
    version: str = "1.20.1"
    grid: VoxelGrid | ChunkedGrid = field(default_factory=lambda: VoxelGrid(shape=(16, 16, 16)))
    history: History = field(default_factory=History)
    metadata: dict[str, Any] = field(default_factory=dict)
    registry: BlockRegistry | None = field(default=None)

    def __post_init__(self) -> None:
        if self.registry is None:
            self.registry = BlockRegistry.for_version(self.version)

    @classmethod
    def new(cls, shape: tuple[int, int, int], version: str = "1.20.1",
            fill: Block = AIR, *, chunked: bool = False,
            chunk_size: int = DEFAULT_CHUNK_SIZE) -> Session:
        reg = BlockRegistry.for_version(version)
        if chunked:
            grid: VoxelGrid | ChunkedGrid = ChunkedGrid(shape=shape, chunk_size=chunk_size)
        else:
            grid = VoxelGrid(shape=shape)
        if fill != AIR:
            grid.fill(reg.resolve(fill))
        return cls(version=version, grid=grid, registry=reg)

    @property
    def is_chunked(self) -> bool:
        return isinstance(self.grid, ChunkedGrid)

    def _resolve(self, block: Block | str) -> Block:
        if isinstance(block, str):
            block = Block.parse(block)
        assert self.registry is not None
        return self.registry.resolve(block)

    # ---- history ---------------------------------------------------------

    @property
    def _dense(self) -> VoxelGrid:
        """Return self.grid narrowed to VoxelGrid (asserts dense backend)."""
        assert isinstance(self.grid, VoxelGrid), "dense backend required"
        return self.grid

    @property
    def _chunked(self) -> ChunkedGrid:
        """Return self.grid narrowed to ChunkedGrid (asserts chunked backend)."""
        assert isinstance(self.grid, ChunkedGrid), "chunked backend required"
        return self.grid

    def _record(self, new_data: np.ndarray) -> None:
        """Dense-grid history hook (legacy)."""
        g = self._dense
        delta = diff_delta(g.data, new_data)
        self.history.push(delta)
        g.data = new_data

    def _record_chunk_delta(self, coords: tuple[np.ndarray, np.ndarray, np.ndarray],
                             old_values: np.ndarray, new_values: np.ndarray) -> None:
        self.history.push(Delta(coords=coords, old_values=old_values, new_values=new_values))

    # ---- add / subtract / paint (backend-aware) -------------------------

    def add(self, shape: Shape, block: Block | str = "minecraft:stone") -> Session:
        b = self._resolve(block)
        idx = self.grid.palette.add(b)
        if self.is_chunked:
            self._apply_chunked(shape, idx, paint_only=False)
        else:
            g = self._dense
            mask = shape.mask(g.shape)
            new = g.data.copy()
            new[mask.astype(bool)] = idx
            self._record(new)
        return self

    def subtract(self, shape: Shape) -> Session:
        if self.is_chunked:
            self._apply_chunked(shape, 0, paint_only=False, erase=True)
        else:
            g = self._dense
            mask = shape.mask(g.shape)
            new = g.data.copy()
            new[mask.astype(bool)] = 0
            self._record(new)
        return self

    def intersect(self, shape: Shape, block: Block | str) -> Session:
        b = self._resolve(block)
        idx = self.grid.palette.add(b)
        if self.is_chunked:
            self._apply_chunked(shape, idx, paint_only=True)
        else:
            g = self._dense
            mask = shape.mask(g.shape)
            new = g.data.copy()
            solid = new != 0
            sel = solid & mask.astype(bool)
            new[sel] = idx
            self._record(new)
        return self

    def paint(self, shape: Shape, block: Block | str) -> Session:
        b = self._resolve(block)
        idx = self.grid.palette.add(b)
        if self.is_chunked:
            self._apply_chunked(shape, idx, paint_only=True)
        else:
            g = self._dense
            mask = shape.mask(g.shape)
            new = g.data.copy()
            solid = new != 0
            sel = solid & mask.astype(bool)
            new[sel] = idx
            self._record(new)
        return self

    def set_box(self, frm: tuple[int, int, int], to: tuple[int, int, int],
                block: Block | str, *, history: bool = True,
                clip: bool = True) -> int:
        """Set an inclusive cuboid directly, optimized for procedural builders.

        Unlike ``add(Box(...))``, this does not build a shape mask. It resolves
        the block through the session registry, clips by default, and records a
        single history delta unless ``history=False`` is used.
        """
        bounds = _clipped_box(frm, to, self.grid.shape, clip=clip)
        if bounds is None:
            return 0
        x0, y0, z0, x1, y1, z1 = bounds
        idx = self.grid.palette.add(self._resolve(block))
        if self.is_chunked:
            return self._set_box_chunked(x0, y0, z0, x1, y1, z1, idx, history=history)
        g = self._dense
        region = g.data[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1]
        changed = region != idx
        count = int(np.count_nonzero(changed))
        if count == 0:
            return 0
        if history:
            local_x, local_y, local_z = np.nonzero(changed)
            coords_delta = (local_x + x0, local_y + y0, local_z + z0)
            old_values = region[changed].copy()
            region[...] = idx
            self.history.push(Delta(
                coords=coords_delta,
                old_values=old_values,
                new_values=np.full(count, idx, dtype=np.uint16),
            ))
            return count
        region[...] = idx
        self.history.clear()
        return count

    def set_many(self, coords: Iterable[tuple[int, int, int]], block: Block | str, *,
                 history: bool = True, skip_out_of_bounds: bool = True) -> int:
        """Set many points to one block with one palette lookup and history delta."""
        sx, sy, sz = self.grid.shape
        points: dict[tuple[int, int, int], None] = {}
        for x, y, z in coords:
            pos = (int(x), int(y), int(z))
            in_bounds = 0 <= pos[0] < sx and 0 <= pos[1] < sy and 0 <= pos[2] < sz
            if not in_bounds:
                if skip_out_of_bounds:
                    continue
                raise ValueError(f"point {pos} is outside grid {self.grid.shape}")
            points[pos] = None
        if not points:
            return 0
        idx = self.grid.palette.add(self._resolve(block))
        if self.is_chunked:
            coords_list: list[tuple[int, int, int]] = []
            old_values: list[int] = []
            new_values: list[int] = []
            for pos in points:
                old = _raw_index_at(self.grid, *pos)
                if old == idx:
                    continue
                _set_raw_index_at(self._chunked, *pos, idx)
                coords_list.append(pos)
                old_values.append(old)
                new_values.append(idx)
            if history and coords_list:
                coords_delta = tuple(
                    np.array([p[i] for p in coords_list], dtype=np.int64) for i in range(3)
                )
                self._record_chunk_delta(coords_delta, np.array(old_values, dtype=np.uint16),
                                         np.array(new_values, dtype=np.uint16))
            elif coords_list:
                self.history.clear()
            return len(coords_list)
        g = self._dense
        xs = np.array([p[0] for p in points], dtype=np.int64)
        ys = np.array([p[1] for p in points], dtype=np.int64)
        zs = np.array([p[2] for p in points], dtype=np.int64)
        old = g.data[xs, ys, zs].copy()
        changed = old != idx
        if not bool(np.any(changed)):
            return 0
        g.data[xs[changed], ys[changed], zs[changed]] = idx
        count = int(np.count_nonzero(changed))
        if history:
            coords_delta = (xs[changed], ys[changed], zs[changed])
            self.history.push(Delta(
                coords=coords_delta,
                old_values=old[changed],
                new_values=np.full(count, idx, dtype=np.uint16),
            ))
        else:
            self.history.clear()
        return count

    def _set_box_chunked(self, x0: int, y0: int, z0: int,
                         x1: int, y1: int, z1: int, idx: int, *,
                         history: bool) -> int:
        grid = self._chunked
        cs = grid.chunk_size
        delta_coords: list[np.ndarray] = []
        delta_old: list[np.ndarray] = []
        delta_new: list[np.ndarray] = []
        changed_total = 0
        for cx in range(x0 // cs, x1 // cs + 1):
            for cy in range(y0 // cs, y1 // cs + 1):
                for cz in range(z0 // cs, z1 // cs + 1):
                    arr = grid._chunks.get((cx, cy, cz)) if idx == 0 else grid._ensure_chunk(cx, cy, cz)
                    if arr is None:
                        continue
                    ox, oy, oz = grid._chunk_origin(cx, cy, cz)
                    lx0 = max(x0 - ox, 0)
                    ly0 = max(y0 - oy, 0)
                    lz0 = max(z0 - oz, 0)
                    lx1 = min(x1 - ox, arr.shape[0] - 1)
                    ly1 = min(y1 - oy, arr.shape[1] - 1)
                    lz1 = min(z1 - oz, arr.shape[2] - 1)
                    region = arr[lx0:lx1 + 1, ly0:ly1 + 1, lz0:lz1 + 1]
                    changed = region != idx
                    changed_count = int(np.count_nonzero(changed))
                    if changed_count == 0:
                        continue
                    if history:
                        local_x, local_y, local_z = np.nonzero(changed)
                        wx = local_x + lx0 + ox
                        wy = local_y + ly0 + oy
                        wz = local_z + lz0 + oz
                        delta_coords.append(np.stack([wx, wy, wz], axis=0))
                        delta_old.append(region[changed].copy())
                        delta_new.append(np.full(changed_count, idx, dtype=np.uint16))
                    region[...] = idx
                    changed_total += changed_count
                    if idx == 0:
                        grid._drop_chunk_if_empty(cx, cy, cz)
        if history and delta_coords:
            coords: tuple[np.ndarray, np.ndarray, np.ndarray] = (
                np.concatenate([dc[0] for dc in delta_coords]),
                np.concatenate([dc[1] for dc in delta_coords]),
                np.concatenate([dc[2] for dc in delta_coords]),
            )
            self._record_chunk_delta(coords, np.concatenate(delta_old), np.concatenate(delta_new))
        elif changed_total:
            self.history.clear()
        return changed_total

    def _apply_chunked(self, shape: Shape, idx: int, *,
                        paint_only: bool, erase: bool = False) -> None:
        """Apply ``idx`` (or air if erase) to voxels in ``shape``, touching only
        the chunks the shape's bbox overlaps.

        For each touched chunk we evaluate the shape's mask on a local sub-grid
        (sized to the chunk, offset to world coords) -- so memory cost is one
        chunk-sized mask at a time, not full-grid.
        """
        grid = self._chunked
        gs = grid.shape
        bbox = shape_bounds(shape, gs)
        x0, y0, z0, x1, y1, z1 = bbox
        # Clamp to grid extent.
        x0 = max(x0, 0)
        y0 = max(y0, 0)
        z0 = max(z0, 0)
        x1 = min(x1, gs[0] - 1)
        y1 = min(y1, gs[1] - 1)
        z1 = min(z1, gs[2] - 1)
        if x1 < x0 or y1 < y0 or z1 < z0:
            return
        cs = grid.chunk_size
        cx0, cy0, cz0 = x0 // cs, y0 // cs, z0 // cs
        cx1, cy1, cz1 = x1 // cs, y1 // cs, z1 // cs
        delta_coords: list[np.ndarray] = []
        delta_old: list[np.ndarray] = []
        delta_new: list[np.ndarray] = []
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                for cz in range(cz0, cz1 + 1):
                    ox, oy, oz = cx * cs, cy * cs, cz * cs
                    cshp = grid._chunk_shape(cx, cy, cz)
                    if cshp[0] <= 0 or cshp[1] <= 0 or cshp[2] <= 0:
                        continue
                    arr = grid._ensure_chunk(cx, cy, cz)
                    # Build the local mask: shape.mask_region if available, else
                    # slice the full-grid mask. We avoid full-grid by using
                    # bounds-aware mask_region default which still computes full
                    # then slices -- but most primitives now implement
                    # mask_region natively. Fallback for shapes that don't:
                    # compute mask only over the chunk bbox sub-grid.
                    if hasattr(shape, "mask_region"):
                        local = shape.mask_region(gs, (ox, oy, oz), cshp)
                    else:
                        # Generic fallback: evaluate the shape on a sub-grid
                        # sized to the chunk and offset to world coords. Most
                        # shapes use coords_grid(shape) so we need a wrapper.
                        local = _eval_shape_subgrid(shape, gs, (ox, oy, oz), cshp)
                    if not local.any():
                        if not arr.any():
                            grid._drop_chunk_if_empty(cx, cy, cz)
                        continue
                    # Capture delta for history.
                    sel = local.astype(bool)
                    if paint_only or erase:
                        sel = sel & (arr != 0) if paint_only else sel
                    if not sel.any():
                        continue
                    old_vals = arr[sel].copy()
                    if delta_coords:
                        # Convert local sel to world coords.
                        lx, ly, lz = np.nonzero(sel)
                        wx = lx + ox
                        wy = ly + oy
                        wz = lz + oz
                    else:
                        lx, ly, lz = np.nonzero(sel)
                        wx = lx + ox
                        wy = ly + oy
                        wz = lz + oz
                    delta_coords.append(np.stack([wx, wy, wz], axis=0))
                    delta_old.append(old_vals)
                    if erase:
                        arr[sel] = 0
                        delta_new.append(np.zeros_like(old_vals))
                    else:
                        arr[sel] = idx
                        delta_new.append(np.full_like(old_vals, idx))
                    if erase:
                        grid._drop_chunk_if_empty(cx, cy, cz)
        if delta_coords:
            coords: tuple[np.ndarray, np.ndarray, np.ndarray] = (
                np.concatenate([dc[0] for dc in delta_coords]),
                np.concatenate([dc[1] for dc in delta_coords]),
                np.concatenate([dc[2] for dc in delta_coords]),
            )
            oldv = np.concatenate(delta_old)
            newv = np.concatenate(delta_new)
            self._record_chunk_delta(coords, oldv, newv)

    def replace(self, src: Block | str, dst: Block | str) -> int:
        src_b = self._resolve(src)
        dst_b = self._resolve(dst)
        if self.is_chunked:
            return self._chunked.replace(src_b, dst_b)
        g = self._dense
        src_idx = g.palette.index_of(src_b)
        if src_idx is None:
            return 0
        new = g.data.copy()
        sel = new == src_idx
        dst_idx = g.palette.add(dst_b)
        new[sel] = dst_idx
        self._record(new)
        return int(np.count_nonzero(sel))

    def clone_translate(self, frm: tuple[int, int, int], to: tuple[int, int, int],
                        offset: tuple[int, int, int], *, count: int = 1,
                        include_air: bool = False) -> int:
        """Clone a source box by an offset one or more times.

        ``count`` is the number of copies, not including the original source.
        Air is skipped by default so cloning a corner build onto empty quadrants
        does not accidentally erase existing work.
        """
        if count <= 0:
            return 0
        source = self._clone_source(frm, to, include_air=include_air)
        dx, dy, dz = offset
        targets: dict[tuple[int, int, int], int] = {}
        for step in range(1, count + 1):
            ox, oy, oz = dx * step, dy * step, dz * step
            for x, y, z, value in source:
                targets[(x + ox, y + oy, z + oz)] = value
        return self._paste_palette_indices(targets)

    def clone_cardinal(self, frm: tuple[int, int, int], to: tuple[int, int, int],
                       center: tuple[float, float], *, include_air: bool = False) -> int:
        """Clone a source box into the other three cardinal rotations around Y."""
        source = self._clone_source(frm, to, include_air=include_air)
        cx, cz = center
        targets: dict[tuple[int, int, int], int] = {}
        for x, y, z, value in source:
            dx = x - cx
            dz = z - cz
            rotations = (
                (cx - dz, cz + dx),
                (cx - dx, cz - dz),
                (cx + dz, cz - dx),
            )
            for rx, rz in rotations:
                targets[(round(rx), y, round(rz))] = value
        return self._paste_palette_indices(targets)

    def _clone_source(self, frm: tuple[int, int, int], to: tuple[int, int, int], *,
                      include_air: bool) -> list[tuple[int, int, int, int]]:
        x0, y0, z0, x1, y1, z1 = _normalized_box(frm, to, self.grid.shape)
        out: list[tuple[int, int, int, int]] = []
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    value = _raw_index_at(self.grid, x, y, z)
                    if include_air or value != 0:
                        out.append((x, y, z, value))
        return out

    def _paste_palette_indices(self, targets: dict[tuple[int, int, int], int]) -> int:
        sx, sy, sz = self.grid.shape
        in_bounds = {
            pos: value for pos, value in targets.items()
            if 0 <= pos[0] < sx and 0 <= pos[1] < sy and 0 <= pos[2] < sz
        }
        if not in_bounds:
            return 0
        if self.is_chunked:
            coords_list: list[tuple[int, int, int]] = []
            old_values: list[int] = []
            new_values: list[int] = []
            for pos, value in in_bounds.items():
                old = _raw_index_at(self.grid, *pos)
                if old == value:
                    continue
                _set_raw_index_at(self._chunked, *pos, value)
                coords_list.append(pos)
                old_values.append(old)
                new_values.append(value)
            if coords_list:
                coords = tuple(np.array([p[i] for p in coords_list], dtype=np.int64) for i in range(3))
                self._record_chunk_delta(coords, np.array(old_values, dtype=np.uint16),
                                         np.array(new_values, dtype=np.uint16))
            return len(coords_list)
        g = self._dense
        new = g.data.copy()
        for (x, y, z), value in in_bounds.items():
            new[x, y, z] = value
        changed = int(np.count_nonzero(g.data != new))
        if changed == 0:
            return 0
        self._record(new)
        return changed

    def fill_all(self, block: Block | str) -> Session:
        b = self._resolve(block)
        if self.is_chunked:
            self._chunked.fill(b)
            return self
        g = self._dense
        new = np.zeros_like(g.data)
        idx = g.palette.add(b)
        new[...] = idx
        self._record(new)
        return self

    def clear(self) -> Session:
        if self.is_chunked:
            self._chunked.fill_air()
            return self
        new = np.zeros_like(self._dense.data)
        self._record(new)
        return self

    def transform_rotate(self, times: int, axes: str = "xy") -> Session:
        ax_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
        if self.is_chunked:
            self.grid = self._chunked.rotate(times, axes)
        else:
            g = self._dense
            new = np.ascontiguousarray(np.rot90(g.data, k=times, axes=ax_map[axes]))
            self.grid = VoxelGrid.from_array(new, g.palette)
        return self

    def transform_mirror(self, axis: int) -> Session:
        if self.is_chunked:
            self.grid = self._chunked.mirror(axis)
        else:
            g = self._dense
            new = np.flip(g.data, axis=axis).copy()
            self.grid = VoxelGrid.from_array(new, g.palette)
        return self

    def undo(self) -> bool:
        if not self.history.can_undo():
            return False
        if self.is_chunked:
            self.history.apply_inverse(self._chunked)
        else:
            self.history.apply_inverse(self._dense.data)
        return True

    def redo(self) -> bool:
        if not self.history.can_redo():
            return False
        if self.is_chunked:
            self.history.apply_redo(self._chunked)
        else:
            self.history.apply_redo(self._dense.data)
        return True

    # ---- snapshot / save / load -----------------------------------------

    def snapshot(self) -> dict[str, Any]:
        if self.is_chunked:
            g = self._chunked
            return {
                "version": self.version,
                "shape": list(g.shape),
                "chunked": True,
                "chunk_size": g.chunk_size,
                "palette": g.palette.to_json(),
                "chunks": _chunks_to_json(g),
                "metadata": self.metadata,
            }
        return {
            "version": self.version,
            "shape": list(self.grid.shape),
            "chunked": False,
            "palette": self.grid.palette.to_json(),
            "data_b64": _np_to_b64(self.grid.data) if isinstance(self.grid, VoxelGrid) else "",
            "metadata": self.metadata,
        }

    @classmethod
    def restore(cls, snap: dict[str, Any]) -> Session:
        s = cls.new(tuple(snap["shape"]), version=str(snap["version"]),
                    chunked=bool(snap.get("chunked", False)),
                    chunk_size=int(snap.get("chunk_size", DEFAULT_CHUNK_SIZE)))
        s.grid.palette = Palette.from_json(snap["palette"])
        if snap.get("chunked") and isinstance(s.grid, ChunkedGrid):
            _load_chunks_from_json(s.grid, snap["chunks"])
        elif isinstance(s.grid, VoxelGrid):
            s.grid.data = _b64_to_np(snap["data_b64"], tuple(snap["shape"]))
        s.metadata = dict(snap.get("metadata", {}))
        return s

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.snapshot()), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> Session:
        return cls.restore(json.loads(Path(path).read_text(encoding="utf-8")))

    def stats(self) -> dict[str, Any]:
        st: dict[str, Any] = {
            "shape": list(self.grid.shape),
            "volume": self.grid.volume,
            "solid": self.grid.nonempty_count(),
            "palette_size": len(self.grid.palette),
            "chunked": self.is_chunked,
        }
        if self.is_chunked and isinstance(self.grid, ChunkedGrid):
            st["chunks"] = self.grid.chunk_count()
            st["chunk_size"] = self.grid.chunk_size
            st["memory_bytes"] = self.grid.memory_estimate_bytes()
        st["markers"] = len(self.metadata.get("markers", []))
        st["regions"] = len(self.metadata.get("regions", []))
        return st

    # ---- markers / regions ----------------------------------------------

    def marker(self, name: str, x: int, y: int, z: int, *,
               kind: str = "point") -> Session:
        """Add a generic named marker at ``(x, y, z)``.

        ``kind`` is a free-form label (e.g. ``"spawn"``, ``"entrance"``,
        ``"viewpoint"``, ``"loot_room"``) so markers work for any build type,
        not just minigames.
        """
        markers = self.metadata.setdefault("markers", [])
        markers.append({"name": name, "pos": [int(x), int(y), int(z)], "kind": kind})
        return self

    def region(self, name: str, corner: tuple[int, int, int],
               size: tuple[int, int, int], *, kind: str = "area") -> Session:
        """Add a generic named region (bounding box annotation).

        ``corner`` is the min corner and ``size`` is the (w, h, d) extent.
        ``kind`` is a free-form label (e.g. ``"area"``, ``"arena"``,
        ``"spawn_pad"``, ``"no_build"``).
        """
        cx, cy, cz = corner
        sw, sh, sd = size
        if sw <= 0 or sh <= 0 or sd <= 0:
            raise ValueError(f"region size must be positive, got {size}")
        sx, sy, sz = self.grid.shape
        if cx < 0 or cy < 0 or cz < 0 or cx + sw > sx or cy + sh > sy or cz + sd > sz:
            raise ValueError(f"region {corner}+{size} is outside grid {self.grid.shape}")
        regions = self.metadata.setdefault("regions", [])
        regions.append({
            "name": name,
            "corner": [int(cx), int(cy), int(cz)],
            "size": [int(sw), int(sh), int(sd)],
            "kind": kind,
        })
        return self

    def markers(self) -> list[dict[str, Any]]:
        """Return all stored markers (shallow copy)."""
        return list(self.metadata.get("markers", []))

    def regions(self) -> list[dict[str, Any]]:
        """Return all stored regions (shallow copy)."""
        return list(self.metadata.get("regions", []))

    def export_markers(self, path: str | Path) -> Path:
        """Write markers + regions + build summary to a JSON file beside the schematic.

        The file is suitable for plugins, datapacks, or manual setup and includes
        the grid shape, version, marker list, and region list.
        """
        p = Path(path)
        p.write_text(json.dumps({
            "version": self.version,
            "shape": list(self.grid.shape),
            "markers": self.markers(),
            "regions": self.regions(),
        }, indent=2), encoding="utf-8")
        return p

    # ---- procedural detail tools ---------------------------------------

    def paint_gradient(self, frm: tuple[int, int, int], to: tuple[int, int, int],
                       blocks: list[str], *, axis: str = "y",
                       blend: float = 0.0, seed: int = 0) -> int:
        """Paint a linear gradient of blocks along an axis. Returns voxels painted."""
        from ..procedural.detail import paint_gradient as _pg
        old = self._dense.data.copy() if not self.is_chunked else None
        n = _pg(self.grid, frm, to, blocks, axis=axis, blend=blend, seed=seed)
        if not self.is_chunked and n > 0:
            self._record(self.grid.data.copy())
        return n

    def edge_wear(self, blocks: list[str], *, min_exposure: int = 1,
                  max_exposure: int = 6, noise: float = 0.0,
                  seed: int = 0) -> int:
        """Apply weathering blocks to exposed surfaces. Returns voxels weathered."""
        from ..procedural.detail import edge_wear as _ew
        n = _ew(self.grid, blocks, min_exposure=min_exposure,
                max_exposure=max_exposure, noise=noise, seed=seed)
        if not self.is_chunked and n > 0:
            self._record(self.grid.data.copy())
        return n

    def surface_scatter(self, block: str, *, density: float = 0.1,
                        min_exposure: int = 1, max_exposure: int = 6,
                        seed: int = 0, on_blocks: list[str] | None = None) -> int:
        """Scatter a block on exposed surfaces. Returns voxels scattered."""
        from ..procedural.detail import surface_scatter as _ss
        n = _ss(self.grid, block, density=density, min_exposure=min_exposure,
                max_exposure=max_exposure, seed=seed, on_blocks=on_blocks)
        if not self.is_chunked and n > 0:
            self._record(self.grid.data.copy())
        return n

    # ---- spatial analysis -----------------------------------------------

    def walkable_at(self, x: int, y: int, z: int) -> bool:
        """Check if a player can stand at (x, y, z)."""
        from ..analysis.spatial import walkable_at as _wa
        return _wa(self.grid, x, y, z)

    def clearance_at(self, x: int, y: int, z: int, *, height: int = 2) -> int:
        """Return vertical clearance (free blocks above) at (x, y, z)."""
        from ..analysis.spatial import clearance_at as _ca
        return _ca(self.grid, x, y, z, height=height)

    def is_connected(self, a: tuple[int, int, int],
                     b: tuple[int, int, int]) -> bool:
        """Check if a player can walk from position a to position b."""
        from ..analysis.spatial import is_connected as _ic
        return _ic(self.grid, a, b)

    def reachable_area(self, start: tuple[int, int, int]) -> int:
        """Return the number of walkable voxels reachable from start."""
        from ..analysis.spatial import reachable_area as _ra
        mask = _ra(self.grid, start)
        return int(np.count_nonzero(mask))

    def shortest_path(self, a: tuple[int, int, int],
                      b: tuple[int, int, int]) -> list[tuple[int, int, int]] | None:
        """BFS shortest walking path from a to b. Returns list or None."""
        from ..analysis.spatial import shortest_path as _sp
        return _sp(self.grid, a, b)


def _eval_shape_subgrid(shape: Shape, grid_shape: tuple[int, int, int],
                         origin: tuple[int, int, int], size: tuple[int, int, int]) -> np.ndarray:
    """Evaluate a shape's mask over a sub-grid at world offset ``origin``.

    Shapes whose ``mask`` uses ``coords_grid(shape)`` (which builds index arrays
    starting at 0) get a corrected evaluation by translating the shape's coords
    by ``origin``. We do this by wrapping the shape in a temporary that offsets
    the input grid coordinates. Cheap fallback: compute full-grid mask and slice.
    """
    # The only safe generic fallback is full-grid + slice. Most primitives
    # implement mask_region natively; this is only hit for exotic shapes.
    full = shape.mask(grid_shape)
    ox, oy, oz = origin
    sx, sy, sz = size
    return full[ox:ox + sx, oy:oy + sy, oz:oz + sz].copy()


def _normalized_box(frm: tuple[int, int, int], to: tuple[int, int, int],
                    shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    lo = tuple(min(frm[i], to[i]) for i in range(3))
    hi = tuple(max(frm[i], to[i]) for i in range(3))
    if any(lo[i] < 0 or hi[i] >= shape[i] for i in range(3)):
        raise ValueError(f"clone region {frm}->{to} is outside grid {shape}")
    return lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]


def _clipped_box(frm: tuple[int, int, int], to: tuple[int, int, int],
                 shape: tuple[int, int, int], *, clip: bool) -> tuple[int, int, int, int, int, int] | None:
    lo = tuple(min(int(frm[i]), int(to[i])) for i in range(3))
    hi = tuple(max(int(frm[i]), int(to[i])) for i in range(3))
    if not clip:
        if any(lo[i] < 0 or hi[i] >= shape[i] for i in range(3)):
            raise ValueError(f"box {frm}->{to} is outside grid {shape}")
        return lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]
    clipped_lo = tuple(max(lo[i], 0) for i in range(3))
    clipped_hi = tuple(min(hi[i], shape[i] - 1) for i in range(3))
    if any(clipped_hi[i] < clipped_lo[i] for i in range(3)):
        return None
    return clipped_lo[0], clipped_lo[1], clipped_lo[2], clipped_hi[0], clipped_hi[1], clipped_hi[2]


def _raw_index_at(grid: VoxelGrid | ChunkedGrid, x: int, y: int, z: int) -> int:
    if isinstance(grid, VoxelGrid):
        return int(grid.data[x, y, z])
    cx, cy, cz = x // grid.chunk_size, y // grid.chunk_size, z // grid.chunk_size
    arr = grid._chunks.get((cx, cy, cz))
    if arr is None:
        return 0
    return int(arr[x % grid.chunk_size, y % grid.chunk_size, z % grid.chunk_size])


def _set_raw_index_at(grid: ChunkedGrid, x: int, y: int, z: int, value: int) -> None:
    cx, cy, cz = x // grid.chunk_size, y // grid.chunk_size, z // grid.chunk_size
    if value == 0:
        arr = grid._chunks.get((cx, cy, cz))
        if arr is None:
            return
    else:
        arr = grid._ensure_chunk(cx, cy, cz)
    arr[x % grid.chunk_size, y % grid.chunk_size, z % grid.chunk_size] = value
    if value == 0:
        grid._drop_chunk_if_empty(cx, cy, cz)


def _chunks_to_json(grid: ChunkedGrid) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for (cx, cy, cz), arr in grid._chunks.items():
        out.append({
            "c": [cx, cy, cz],
            "shape": list(arr.shape),
            "data_b64": _np_to_b64(arr),
        })
    return out


def _load_chunks_from_json(grid: ChunkedGrid, chunks: list[dict[str, Any]]) -> None:
    for ch in chunks:
        cx, cy, cz = ch["c"]
        arr = _b64_to_np(ch["data_b64"], tuple(ch["shape"]))
        grid._chunks[(cx, cy, cz)] = arr


def _np_to_b64(arr: np.ndarray) -> str:
    import base64

    return base64.b64encode(arr.tobytes()).decode("ascii")


def _b64_to_np(s: str, shape: tuple[int, int, int] | list[int]) -> np.ndarray:
    import base64

    raw = base64.b64decode(s)
    return np.frombuffer(raw, dtype=np.uint16).reshape(tuple(shape)).copy()
