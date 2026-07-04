"""Procedural micro-detail tools: gradients, edge wear, surface scatter.

These tools add organic weathering and variation to builds by operating on
existing solid voxels. They never fill empty space -- they modify blocks that
are already placed, so they are safe to run after the structural build is
complete.

All tools work on both ``VoxelGrid`` (dense) and ``ChunkedGrid`` (sparse)
backends and integrate with the session history system when called via
``Session`` methods.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from ..blocks.block import AIR, Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

Grid = VoxelGrid | ChunkedGrid


# ---- helpers -----------------------------------------------------------

def _dense_data(grid: Grid) -> np.ndarray:
    """Return a writable dense uint16 view (or copy) for vectorised ops."""
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data


def _solid_mask(grid: Grid) -> np.ndarray:
    """Boolean array: True where the voxel is non-air."""
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data != 0
    return grid.data != 0


def _air_neighbour_count(dense: np.ndarray) -> np.ndarray:
    """Count how many of the 6 face-neighbours of each voxel are air.

    Out-of-bounds neighbours are treated as air. Returns an int array of
    the same shape as ``dense`` with values 0-6.
    """
    sx, sy, sz = dense.shape
    air = dense == 0
    count = np.zeros(dense.shape, dtype=np.int8)
    # +x / -x
    count[1:, :, :] += air[:-1, :, :]
    count[:-1, :, :] += air[1:, :, :]
    # +y / -y
    count[:, 1:, :] += air[:, :-1, :]
    count[:, :-1, :] += air[:, 1:, :]
    # +z / -z
    count[:, :, 1:] += air[:, :, :-1]
    count[:, :, :-1] += air[:, :, 1:]
    # Edges: out-of-bounds = air
    count[0, :, :] += 1
    count[-1, :, :] += 1
    count[:, 0, :] += 1
    count[:, -1, :] += 1
    count[:, :, 0] += 1
    count[:, :, -1] += 1
    # But we added +1 on faces that are in-bounds air, then we also need
    # to subtract the in-bounds contributions that were double-counted.
    # Actually: the shift logic above already handles in-bounds. For
    # boundary voxels, out-of-bounds = air, so add 1 per boundary face.
    # The shifts above didn't cover the boundary because slicing drops
    # one element. Let's redo this cleanly.
    return _air_neighbour_count_clean(dense)


def _air_neighbour_count_clean(dense: np.ndarray) -> np.ndarray:
    """Correct air-neighbour count with out-of-bounds = air."""
    air = dense == 0
    sx, sy, sz = dense.shape
    count = np.zeros(dense.shape, dtype=np.int8)
    # For each of the 6 directions, build a mask of "neighbour is air"
    # (out-of-bounds counts as air).
    # +x neighbour
    px = np.zeros(dense.shape, dtype=bool)
    px[:-1, :, :] = air[1:, :, :]  # voxel at x has neighbour at x+1
    px[-1, :, :] = True
    count += px
    # -x neighbour
    nx = np.zeros(dense.shape, dtype=bool)
    nx[1:, :, :] = air[:-1, :, :]
    nx[0, :, :] = True
    count += nx
    # +y neighbour
    py = np.zeros(dense.shape, dtype=bool)
    py[:, :-1, :] = air[:, 1:, :]
    py[:, -1, :] = True
    count += py
    # -y neighbour
    ny = np.zeros(dense.shape, dtype=bool)
    ny[:, 1:, :] = air[:, :-1, :]
    ny[:, 0, :] = True
    count += ny
    # +z neighbour
    pz = np.zeros(dense.shape, dtype=bool)
    pz[:, :, :-1] = air[:, :, 1:]
    pz[:, :, -1] = True
    count += pz
    # -z neighbour
    nz = np.zeros(dense.shape, dtype=bool)
    nz[:, :, 1:] = air[:, :, :-1]
    nz[:, :, 0] = True
    count += nz
    return count


# ---- paint gradient ----------------------------------------------------

def paint_gradient(grid: Grid, frm: tuple[int, int, int], to: tuple[int, int, int],
                   blocks: list[str], *, axis: str = "y",
                   blend: float = 0.0, seed: int = 0) -> int:
    """Paint a linear gradient of blocks along an axis across a region.

    ``blocks`` is a list of blockstate strings interpolated from ``frm`` to
    ``to``. The gradient runs along ``axis`` (``"x"``, ``"y"``, or ``"z"``).
    ``blend`` in [0, 1] adds perlin-like noise jitter to the gradient boundary
    for organic transitions (0.0 = sharp, 1.0 = very noisy).

    Only paints existing *solid* voxels (like ``paint`` / ``intersect``).
    Returns the number of voxels painted.
    """
    if not blocks:
        raise ValueError("blocks list cannot be empty")
    if axis not in ("x", "y", "z"):
        raise ValueError(f"axis must be x, y, or z, got {axis}")
    ax_idx = {"x": 0, "y": 1, "z": 2}[axis]
    x0, y0, z0 = frm
    x1, y1, z1 = to
    lo = (min(x0, x1), min(y0, y1), min(z0, z1))
    hi = (max(x0, x1), max(y0, y1), max(z0, z1))
    # Clip to grid bounds.
    gs = grid.shape
    lo = tuple(max(lo[i], 0) for i in range(3))
    hi = tuple(min(hi[i], gs[i] - 1) for i in range(3))
    if any(lo[i] > hi[i] for i in range(3)):
        return 0

    # Resolve blocks to palette indices.
    resolved = [Block.parse(b) for b in blocks]
    palette_indices = [grid.palette.add(b) for b in resolved]
    n_blocks = len(blocks)

    # Compute gradient coordinate.
    region_shape = (hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, hi[2] - lo[2] + 1)
    # Build coordinate array along the gradient axis.
    ax_coords = np.arange(region_shape[ax_idx], dtype=np.float32)
    ax_lo = lo[ax_idx]
    ax_hi = hi[ax_idx]
    ax_span = max(ax_hi - ax_lo, 1)
    t = (ax_coords - ax_lo) / ax_span  # 0..1 along the axis
    t = np.clip(t, 0.0, 1.0)

    if blend > 0:
        rng = np.random.default_rng(seed)
        jitter = rng.uniform(-blend, blend, size=region_shape[ax_idx]).astype(np.float32)
        t = np.clip(t + jitter, 0.0, 1.0)

    # Map t to block index: 0 at start, n_blocks-1 at end.
    block_idx = (t * (n_blocks - 1)).astype(np.int32)
    block_idx = np.clip(block_idx, 0, n_blocks - 1)

    # Broadcast to 3D.
    if ax_idx == 0:
        idx_grid = np.broadcast_to(block_idx[:, None, None], region_shape)
    elif ax_idx == 1:
        idx_grid = np.broadcast_to(block_idx[None, :, None], region_shape)
    else:
        idx_grid = np.broadcast_to(block_idx[None, None, :], region_shape)

    # Map to palette indices.
    lut = np.array(palette_indices, dtype=np.uint16)
    new_vals = lut[idx_grid]

    # Apply to solid voxels only.
    dense = _dense_data(grid)
    region = dense[lo[0]:hi[0] + 1, lo[1]:hi[1] + 1, lo[2]:hi[2] + 1]
    solid = region != 0
    count = int(np.count_nonzero(solid))
    if count == 0:
        return 0
    region[solid] = new_vals[solid]
    _write_back(grid, dense, lo, hi)
    return count


# ---- edge wear ---------------------------------------------------------

def edge_wear(grid: Grid, blocks: list[str], *,
              min_exposure: int = 1, max_exposure: int = 6,
              noise: float = 0.0, seed: int = 0) -> int:
    """Apply weathering blocks to exposed surfaces.

    Each solid voxel that has between ``min_exposure`` and ``max_exposure``
    air face-neighbours is repainted with a block from ``blocks``. Voxels with
    more air neighbours (more exposed) map to earlier blocks in the list, so
    the first block is the most weathered (e.g. mossy_cobblestone) and the last
    is the least weathered (e.g. stone).

    ``noise`` in [0, 1] randomly skips some voxels for patchy, organic wear.

    Returns the number of voxels weathered.
    """
    if not blocks:
        raise ValueError("blocks list cannot be empty")
    if min_exposure < 1 or max_exposure < 1:
        raise ValueError("exposure must be >= 1")
    if min_exposure > max_exposure:
        raise ValueError("min_exposure cannot exceed max_exposure")

    dense = _dense_data(grid)
    solid = dense != 0
    air_count = _air_neighbour_count_clean(dense)

    # Mask: solid voxels within the exposure range.
    exposed = solid & (air_count >= min_exposure) & (air_count <= max_exposure)

    if noise > 0:
        rng = np.random.default_rng(seed)
        skip = rng.random(dense.shape) < noise
        exposed = exposed & ~skip

    if not exposed.any():
        return 0

    # Map exposure level to block index.
    # exposure = max_exposure -> block 0 (most weathered)
    # exposure = min_exposure -> block n-1 (least weathered)
    n = len(blocks)
    span = max(max_exposure - min_exposure, 1)
    # For each exposed voxel, compute block index from its air_count.
    exposed_counts = air_count[exposed]
    t = 1.0 - (exposed_counts.astype(np.float32) - min_exposure) / span
    t = np.clip(t, 0.0, 1.0)
    block_indices = (t * (n - 1)).astype(np.int32)
    block_indices = np.clip(block_indices, 0, n - 1)

    # Resolve blocks to palette indices.
    palette_indices = np.array(
        [grid.palette.add(Block.parse(b)) for b in blocks], dtype=np.uint16
    )
    new_vals = palette_indices[block_indices]
    dense[exposed] = new_vals
    _write_back(grid, dense, (0, 0, 0), tuple(d - 1 for d in dense.shape))
    return int(np.count_nonzero(exposed))


# ---- surface scatter ---------------------------------------------------

def surface_scatter(grid: Grid, block: str, *,
                    density: float = 0.1, min_exposure: int = 1,
                    max_exposure: int = 6, seed: int = 0,
                    on_blocks: list[str] | None = None) -> int:
    """Scatter a block on exposed surfaces with probabilistic density.

    Each solid voxel that has between ``min_exposure`` and ``max_exposure``
    air face-neighbours has a ``density`` probability (0.0 to 1.0) of being
    repainted with ``block``. This is ideal for scattering moss, lichen, gravel
    patches, or small flowers on surfaces.

    ``on_blocks`` if given restricts the scatter to voxels whose current block
    name is in the list (e.g. only scatter moss on stone, not on wood).

    Returns the number of voxels scattered.
    """
    if density <= 0:
        return 0
    dense = _dense_data(grid)
    solid = dense != 0
    air_count = _air_neighbour_count_clean(dense)
    exposed = solid & (air_count >= min_exposure) & (air_count <= max_exposure)

    if on_blocks:
        # Build mask of allowed source blocks.
        allowed = np.zeros(dense.shape, dtype=bool)
        for name in on_blocks:
            b = Block.parse(name)
            idx = grid.palette.index_of(b)
            if idx is not None:
                allowed |= dense == idx
        exposed = exposed & allowed

    if not exposed.any():
        return 0

    rng = np.random.default_rng(seed)
    selected = exposed & (rng.random(dense.shape) < density)
    if not selected.any():
        return 0

    b = Block.parse(block)
    new_idx = grid.palette.add(b)
    dense[selected] = new_idx
    _write_back(grid, dense, (0, 0, 0), tuple(d - 1 for d in dense.shape))
    return int(np.count_nonzero(selected))


# ---- write-back for chunked grids --------------------------------------

def _write_back(grid: Grid, dense: np.ndarray,
                lo: tuple[int, int, int], hi: tuple[int, int, int]) -> None:
    """Write a modified dense array back to the grid.

    For VoxelGrid this is a no-op (dense was grid.data, modified in-place).
    For ChunkedGrid we need to copy the region back into the chunked structure.
    """
    if isinstance(grid, ChunkedGrid):
        cs = grid.chunk_size
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    val = int(dense[x, y, z])
                    cx, cy, cz = x // cs, y // cs, z // cs
                    if val == 0:
                        arr = grid._chunks.get((cx, cy, cz))
                        if arr is not None:
                            arr[x % cs, y % cs, z % cs] = 0
                            if not np.any(arr):
                                grid._drop_chunk_if_empty(cx, cy, cz)
                    else:
                        arr = grid._ensure_chunk(cx, cy, cz)
                        arr[x % cs, y % cs, z % cs] = val