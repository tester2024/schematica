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
            grid.fill(fill)
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
        return st


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
