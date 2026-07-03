"""ChunkedGrid: sparse chunk-backed voxel storage for big maps.

A ChunkedGrid partitions world space into fixed-size chunks (default 16x16x16,
matching Minecraft's chunk column footprint per layer). Only chunks that contain
any non-air voxels are materialised as dense ``np.uint16`` arrays; untouched
chunks are represented implicitly as "all air" and never allocated.

This makes it practical to model maps spanning hundreds of chunks: a 100x100
chunk area with a mostly-empty interior only pays memory for the chunks that
actually hold blocks.

Coordinate convention (same as VoxelGrid):
    - world coords (x, y, z) with y up
    - grid shape == (sx, sy, sz)  (world extent, not chunk count)
    - chunk (cx, cy, cz) covers
          x in [cx*CS, cx*CS + CS)
          y in [cy*CS, cy*CS + CS)
          z in [cz*CS, cz*CS + CS)

The grid exposes the same read/write API as VoxelGrid (get/set/fill/replace/
apply_mask/erase_mask/paint_mask/count/nonempty_count/slice/subregion/copy) so
Session can drive either backend through a uniform surface. ``to_dense()`` and
``from_dense()`` bridge to the legacy VoxelGrid for exporters/renderers that
still want a contiguous array (used only on demand).
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import numpy as np

from ..blocks.block import AIR, Block
from .palette import Palette
from .voxel import VoxelGrid

DEFAULT_CHUNK_SIZE = 16


def _divmod_pos(n: int, cs: int) -> tuple[int, int]:
    """Floor division that handles negatives correctly (Python's // already does)."""
    q, r = divmod(n, cs)
    return q, r


@dataclass
class ChunkedGrid:
    """Sparse chunk-backed 3D voxel grid with a shared palette.

    ``shape`` is the world extent. ``chunk_size`` is the per-chunk edge length
    (must be a power of two in each axis for clean bitmath, but we only require
    a positive int; chunk indices are computed via divmod). Chunks are stored
    in ``_chunks`` keyed by (cx, cy, cz) -> ``np.ndarray`` of shape
    ``(chunk_size, chunk_size, chunk_size)`` dtype uint16. Missing keys == air.
    """
    shape: tuple[int, int, int]
    palette: Palette = field(default_factory=Palette)
    chunk_size: int = DEFAULT_CHUNK_SIZE
    _chunks: dict[tuple[int, int, int], np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {self.chunk_size}")

    # ---- chunk geometry helpers ------------------------------------------

    @property
    def size(self) -> tuple[int, int, int]:
        return self.shape

    @property
    def volume(self) -> int:
        sx, sy, sz = self.shape
        return sx * sy * sz

    @property
    def chunks_per_axis(self) -> tuple[int, int, int]:
        cs = self.chunk_size
        sx, sy, sz = self.shape
        return ((sx + cs - 1) // cs, (sy + cs - 1) // cs, (sz + cs - 1) // cs)

    def _chunk_index(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        cs = self.chunk_size
        return (x // cs, y // cs, z // cs)

    def _chunk_origin(self, cx: int, cy: int, cz: int) -> tuple[int, int, int]:
        cs = self.chunk_size
        return (cx * cs, cy * cs, cz * cs)

    def _chunk_local(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        cs = self.chunk_size
        return (x % cs, y % cs, z % cs)

    def _chunk_shape(self, cx: int, cy: int, cz: int) -> tuple[int, int, int]:
        """Actual ndarray shape for a chunk, clamped to grid extent at edges."""
        cs = self.chunk_size
        sx, sy, sz = self.shape
        ox, oy, oz = self._chunk_origin(cx, cy, cz)
        return (
            min(cs, sx - ox) if ox < sx else 0,
            min(cs, sy - oy) if oy < sy else 0,
            min(cs, sz - oz) if oz < sz else 0,
        )

    def _in_bounds(self, x: int, y: int, z: int) -> bool:
        sx, sy, sz = self.shape
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def _ensure_chunk(self, cx: int, cy: int, cz: int) -> np.ndarray:
        key = (cx, cy, cz)
        arr = self._chunks.get(key)
        if arr is None:
            shp = self._chunk_shape(cx, cy, cz)
            arr = np.zeros(shp, dtype=np.uint16)
            self._chunks[key] = arr
        return arr

    def _drop_chunk_if_empty(self, cx: int, cy: int, cz: int) -> None:
        key = (cx, cy, cz)
        arr = self._chunks.get(key)
        if arr is not None and not np.any(arr):
            del self._chunks[key]

    # ---- single-voxel read/write -----------------------------------------

    def get(self, x: int, y: int, z: int) -> Block:
        if not self._in_bounds(x, y, z):
            raise IndexError((x, y, z))
        cx, cy, cz = self._chunk_index(x, y, z)
        arr = self._chunks.get((cx, cy, cz))
        if arr is None:
            return AIR
        lx, ly, lz = self._chunk_local(x, y, z)
        return self.palette[int(arr[lx, ly, lz])]

    def set(self, x: int, y: int, z: int, block: Block) -> None:
        if not self._in_bounds(x, y, z):
            raise IndexError((x, y, z))
        idx = self.palette.add(block)
        cx, cy, cz = self._chunk_index(x, y, z)
        arr = self._ensure_chunk(cx, cy, cz)
        lx, ly, lz = self._chunk_local(x, y, z)
        arr[lx, ly, lz] = idx
        # If we just set air onto a chunk that became all-zero, free it.
        if block == AIR:
            self._drop_chunk_if_empty(cx, cy, cz)

    # ---- bulk operations -------------------------------------------------

    def fill(self, block: Block) -> None:
        """Fill the entire grid with ``block``. Allocates every chunk."""
        idx = self.palette.add(block)
        if idx == 0:
            # Filling with air = clear everything.
            self._chunks.clear()
            return
        ncx, ncy, ncz = self.chunks_per_axis
        for cx in range(ncx):
            for cy in range(ncy):
                for cz in range(ncz):
                    arr = self._ensure_chunk(cx, cy, cz)
                    arr[...] = idx

    def fill_air(self) -> None:
        self._chunks.clear()

    def apply_mask(self, mask: np.ndarray, block: Block) -> None:
        """Set every voxel where mask is True to ``block``.

        Walks only the chunks that intersect the mask's bounding box of True
        cells, so a sparse mask over a huge grid costs O(touched_chunks), not
        O(total_volume).
        """
        if mask.shape != self.shape:
            try:
                mask = np.broadcast_to(mask, self.shape)
            except ValueError as e:
                raise ValueError(f"mask shape {mask.shape} incompatible with grid {self.shape}") from e
        idx = self.palette.add(block)
        # Find the tight bounding box of True cells.
        coords = np.argwhere(mask)
        if coords.size == 0:
            return
        lo = coords.min(axis=0)
        hi = coords.max(axis=0)
        self._apply_in_box(int(lo[0]), int(lo[1]), int(lo[2]),
                           int(hi[0]), int(hi[1]), int(hi[2]),
                           mask, idx, paint_only=False)

    def erase_mask(self, mask: np.ndarray) -> None:
        """Set voxels where mask is True to air (0). Frees emptied chunks."""
        if mask.shape != self.shape:
            try:
                mask = np.broadcast_to(mask, self.shape)
            except ValueError as e:
                raise ValueError(f"mask shape {mask.shape} incompatible with grid {self.shape}") from e
        coords = np.argwhere(mask)
        if coords.size == 0:
            return
        lo = coords.min(axis=0)
        hi = coords.max(axis=0)
        # Walk touched chunks and zero out the masked cells.
        cs = self.chunk_size
        cx0, cy0, cz0 = int(lo[0]) // cs, int(lo[1]) // cs, int(lo[2]) // cs
        cx1, cy1, cz1 = int(hi[0]) // cs, int(hi[1]) // cs, int(hi[2]) // cs
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                for cz in range(cz0, cz1 + 1):
                    arr = self._chunks.get((cx, cy, cz))
                    if arr is None:
                        continue
                    ox, oy, oz = self._chunk_origin(cx, cy, cz)
                    sx, sy, sz = arr.shape
                    # Slice of mask covering this chunk.
                    msub = mask[ox:ox + sx, oy:oy + sy, oz:oz + sz]
                    arr[msub] = 0
                    self._drop_chunk_if_empty(cx, cy, cz)

    def paint_mask(self, mask: np.ndarray, block: Block) -> None:
        """Repaint only already-solid voxels matching mask."""
        if mask.shape != self.shape:
            try:
                mask = np.broadcast_to(mask, self.shape)
            except ValueError as e:
                raise ValueError(f"mask shape {mask.shape} incompatible with grid {self.shape}") from e
        idx = self.palette.add(block)
        coords = np.argwhere(mask)
        if coords.size == 0:
            return
        lo = coords.min(axis=0)
        hi = coords.max(axis=0)
        self._apply_in_box(int(lo[0]), int(lo[1]), int(lo[2]),
                           int(hi[0]), int(hi[1]), int(hi[2]),
                           mask, idx, paint_only=True)

    def _apply_in_box(self, x0: int, y0: int, z0: int,
                      x1: int, y1: int, z1: int,
                      mask: np.ndarray, idx: int, *,
                      paint_only: bool) -> None:
        """Apply ``idx`` to all True cells of ``mask`` within [x0..x1] bbox."""
        cs = self.chunk_size
        cx0, cy0, cz0 = x0 // cs, y0 // cs, z0 // cs
        cx1, cy1, cz1 = x1 // cs, y1 // cs, z1 // cs
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                for cz in range(cz0, cz1 + 1):
                    arr = self._ensure_chunk(cx, cy, cz)
                    ox, oy, oz = self._chunk_origin(cx, cy, cz)
                    sx, sy, sz = arr.shape
                    msub = mask[ox:ox + sx, oy:oy + sy, oz:oz + sz]
                    if paint_only:
                        # Only overwrite voxels that are already non-air.
                        solid = arr != 0
                        arr[solid & msub] = idx
                    else:
                        arr[msub] = idx
                    if not paint_only and idx == 0:
                        self._drop_chunk_if_empty(cx, cy, cz)

    def replace(self, src: Block | str, dst: Block | str) -> int:
        if isinstance(src, str):
            src = Block.parse(src)
        if isinstance(dst, str):
            dst = Block.parse(dst)
        src_idx = self.palette.index_of(src)
        if src_idx is None:
            return 0
        dst_idx = self.palette.add(dst)
        total = 0
        for key, arr in list(self._chunks.items()):
            sel = arr == src_idx
            n = int(np.count_nonzero(sel))
            if n:
                arr[sel] = dst_idx
                total += n
            if dst_idx == 0:
                self._drop_chunk_if_empty(*key)
        return total

    def count(self, block: Block | str) -> int:
        if isinstance(block, str):
            block = Block.parse(block)
        idx = self.palette.index_of(block)
        if idx is None:
            return 0
        return sum(int(np.count_nonzero(arr == idx)) for arr in self._chunks.values())

    def nonempty_count(self) -> int:
        return sum(int(np.count_nonzero(arr != 0)) for arr in self._chunks.values())

    # ---- slices / subregions / transforms --------------------------------

    def slice_y(self, y: int) -> np.ndarray:
        """Return a dense (sx, sz) int16 slice at height y (air outside chunks)."""
        sx, _, sz = self.shape
        out = np.zeros((sx, sz), dtype=np.uint16)
        cs = self.chunk_size
        cy = y // cs
        ly = y % cs
        for (cx, _cy, cz), arr in self._chunks.items():
            if _cy != cy:
                continue
            ox = cx * cs
            oz = cz * cs
            sx_a, sy_a, sz_a = arr.shape
            if ly >= sy_a:
                continue
            out[ox:ox + sx_a, oz:oz + sz_a] = arr[:, ly, :]
        return out

    def slice_x(self, x: int) -> np.ndarray:
        _, sy, sz = self.shape
        out = np.zeros((sy, sz), dtype=np.uint16)
        cs = self.chunk_size
        cx = x // cs
        lx = x % cs
        for (_cx, cy, cz), arr in self._chunks.items():
            if _cx != cx:
                continue
            oy = cy * cs
            oz = cz * cs
            sx_a, sy_a, sz_a = arr.shape
            if lx >= sx_a:
                continue
            out[oy:oy + sy_a, oz:oz + sz_a] = arr[lx, :, :]
        return out

    def slice_z(self, z: int) -> np.ndarray:
        sx, sy, _ = self.shape
        out = np.zeros((sx, sy), dtype=np.uint16)
        cs = self.chunk_size
        cz = z // cs
        lz = z % cs
        for (cx, cy, _cz), arr in self._chunks.items():
            if _cz != cz:
                continue
            ox = cx * cs
            oy = cy * cs
            sx_a, sy_a, sz_a = arr.shape
            if lz >= sz_a:
                continue
            out[ox:ox + sx_a, oy:oy + sy_a] = arr[:, :, lz]
        return out

    def subregion(self, corner: tuple[int, int, int], size: tuple[int, int, int]) -> ChunkedGrid:
        x0, y0, z0 = corner
        sx, sy, sz = size
        sx_t, sy_t, sz_t = self.shape
        if x0 < 0 or y0 < 0 or z0 < 0 or x0 + sx > sx_t or y0 + sy > sy_t or z0 + sz > sz_t:
            raise ValueError("subregion out of bounds")
        out = ChunkedGrid(shape=(sx, sy, sz), palette=Palette.from_blocks(self.palette.blocks()),
                           chunk_size=self.chunk_size)
        for (cx, cy, cz), arr in self._chunks.items():
            ox = cx * self.chunk_size
            oy = cy * self.chunk_size
            oz = cz * self.chunk_size
            sx_a, sy_a, sz_a = arr.shape
            # Intersect chunk extent with requested region.
            ix0 = max(x0, ox)
            iy0 = max(y0, oy)
            iz0 = max(z0, oz)
            ix1 = min(x0 + sx, ox + sx_a)
            iy1 = min(y0 + sy, oy + sy_a)
            iz1 = min(z0 + sz, oz + sz_a)
            if ix0 >= ix1 or iy0 >= iy1 or iz0 >= iz1:
                continue
            sub = arr[ix0 - ox:ix1 - ox, iy0 - oy:iy1 - oy, iz0 - oz:iz1 - oz]
            for xx in range(ix0, ix1):
                for yy in range(iy0, iy1):
                    for zz in range(iz0, iz1):
                        v = sub[xx - ix0, yy - iy0, zz - iz0]
                        if v != 0:
                            out.set(xx - x0, yy - y0, zz - z0, self.palette[int(v)])
        return out

    def copy(self) -> ChunkedGrid:
        out = ChunkedGrid(shape=self.shape,
                           palette=Palette.from_blocks(self.palette.blocks()),
                           chunk_size=self.chunk_size)
        for key, arr in self._chunks.items():
            out._chunks[key] = arr.copy()
        return out

    def rotate(self, times: int, axes: str = "xy") -> ChunkedGrid:
        """Rotate by 90*times via dense round-trip. Heavy for huge grids."""
        return ChunkedGrid.from_dense(self.to_dense().rotate(times, axes), self.chunk_size)

    def mirror(self, axis: int) -> ChunkedGrid:
        out = ChunkedGrid(shape=self.shape,
                           palette=Palette.from_blocks(self.palette.blocks()),
                           chunk_size=self.chunk_size)
        sx, sy, sz = self.shape
        for (cx, cy, cz), arr in self._chunks.items():
            ox = cx * self.chunk_size
            oy = cy * self.chunk_size
            oz = cz * self.chunk_size
            sx_a, sy_a, sz_a = arr.shape
            if axis == 0:
                new_x = sx - ox - sx_a
                for i in range(sx_a):
                    for j in range(sy_a):
                        for k in range(sz_a):
                            v = arr[i, j, k]
                            if v:
                                out.set(new_x + i, oy + j, oz + k, self.palette[int(v)])
            elif axis == 1:
                new_y = sy - oy - sy_a
                for i in range(sx_a):
                    for j in range(sy_a):
                        for k in range(sz_a):
                            v = arr[i, j, k]
                            if v:
                                out.set(ox + i, new_y + j, oz + k, self.palette[int(v)])
            elif axis == 2:
                new_z = sz - oz - sz_a
                for i in range(sx_a):
                    for j in range(sy_a):
                        for k in range(sz_a):
                            v = arr[i, j, k]
                            if v:
                                out.set(ox + i, oy + j, new_z + k, self.palette[int(v)])
            else:
                raise ValueError("axis must be 0,1,2")
        return out

    # ---- dense bridge ----------------------------------------------------

    def to_dense(self) -> VoxelGrid:
        """Flatten into a contiguous VoxelGrid. Heavy for huge grids."""
        sx, sy, sz = self.shape
        data = np.zeros((sx, sy, sz), dtype=np.uint16)
        for (cx, cy, cz), arr in self._chunks.items():
            ox = cx * self.chunk_size
            oy = cy * self.chunk_size
            oz = cz * self.chunk_size
            sx_a, sy_a, sz_a = arr.shape
            data[ox:ox + sx_a, oy:oy + sy_a, oz:oz + sz_a] = arr
        return VoxelGrid(shape=(sx, sy, sz), palette=Palette.from_blocks(self.palette.blocks()),
                          data=data)

    @classmethod
    def from_dense(cls, grid: VoxelGrid, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ChunkedGrid:
        out = cls(shape=grid.shape, palette=grid.palette, chunk_size=chunk_size)
        cs = chunk_size
        sx, sy, sz = grid.shape
        ncx, ncy, ncz = (sx + cs - 1) // cs, (sy + cs - 1) // cs, (sz + cs - 1) // cs
        for cx in range(ncx):
            for cy in range(ncy):
                for cz in range(ncz):
                    ox = cx * cs
                    oy = cy * cs
                    oz = cz * cs
                    sx_a = min(cs, sx - ox)
                    sy_a = min(cs, sy - oy)
                    sz_a = min(cs, sz - oz)
                    sub = grid.data[ox:ox + sx_a, oy:oy + sy_a, oz:oz + sz_a]
                    if np.any(sub):
                        out._chunks[(cx, cy, cz)] = sub.copy()
        return out

    # ---- iteration -------------------------------------------------------

    def iter_chunks(self) -> Iterator[tuple[int, int, int, np.ndarray]]:
        """Yield (cx, cy, cz, ndarray) for every materialised chunk."""
        for key, arr in self._chunks.items():
            yield key[0], key[1], key[2], arr

    def iter_chunks_in_box(self, x0: int, y0: int, z0: int,
                           x1: int, y1: int, z1: int) -> Iterator[tuple[int, int, int, np.ndarray, tuple[int, int, int]]]:
        """Yield (cx, cy, cz, arr, origin) for chunks overlapping the bbox."""
        cs = self.chunk_size
        cx0, cy0, cz0 = x0 // cs, y0 // cs, z0 // cs
        cx1, cy1, cz1 = x1 // cs, y1 // cs, z1 // cs
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                for cz in range(cz0, cz1 + 1):
                    arr = self._chunks.get((cx, cy, cz))
                    if arr is None:
                        continue
                    yield cx, cy, cz, arr, self._chunk_origin(cx, cy, cz)

    def chunk_count(self) -> int:
        return len(self._chunks)

    def memory_estimate_bytes(self) -> int:
        return sum(arr.nbytes for arr in self._chunks.values())

    # ---- equality / repr -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChunkedGrid):
            return False
        if self.shape != other.shape or self.chunk_size != other.chunk_size:
            return False
        if self.palette != other.palette:
            return False
        if set(self._chunks.keys()) != set(other._chunks.keys()):
            return False
        for key in self._chunks:
            if not np.array_equal(self._chunks[key], other._chunks[key]):
                return False
        return True

    def __repr__(self) -> str:
        return (f"ChunkedGrid(shape={self.shape}, chunk_size={self.chunk_size}, "
                f"chunks={self.chunk_count()}, solid={self.nonempty_count()}, "
                f"palette_size={len(self.palette)})")
