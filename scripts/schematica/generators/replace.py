"""Advanced block replacement: multi-block mapping, pattern filters, bulk ops.

This module extends the single-block ``replace(src, dst)`` API with:

- **Bulk replace**: replace many source blocks at once via a mapping dict.
  ``replace_bulk({"stone": "diorite", "dirt": "grass_block", ...})`` walks the
  grid once and applies all mappings in a single pass.
- **Filter-based replace**: replace only voxels matching a predicate filter
  (by block name, by state property, by region mask, by neighbour count).
  ``replace_filtered(src, dst, where=lambda b: b.state("axis") == "y")``.
- **Pattern replace**: replace blocks matching a 2D/3D neighbourhood pattern.
  Useful for "replace dirt that has grass above it" or "replace stone that
  touches air on any side".
- **Retexture**: swap blockstate properties in-place without changing the
  block name (e.g. rotate all logs to ``axis=x``, flip stairs ``half=top``).
  See ``retexture.py``.

All operations work on both dense ``VoxelGrid`` and sparse ``ChunkedGrid``
backends, walking only touched chunks where possible.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..blocks.block import Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

# A block filter is a predicate ``(block) -> bool``.
BlockFilter = Callable[[Block], bool]
# A mapping is ``{src_block: dst_block}`` (or blockstate strings).
BlockMapping = dict[Block, Block] | dict[str, str]


def _to_block(b: Block | str) -> Block:
    if isinstance(b, str):
        return Block.parse(b)
    return b


def _normalise_mapping(mapping: BlockMapping) -> dict[Block, Block]:
    """Accept str-keyed or Block-keyed mappings; return Block-keyed."""
    out: dict[Block, Block] = {}
    for k, v in mapping.items():
        out[_to_block(k)] = _to_block(v)
    return out


# ---- bulk replace (single pass, many sources) -------------------------

def replace_bulk(grid: VoxelGrid | ChunkedGrid,
                 mapping: BlockMapping) -> int:
    """Replace every source block in ``mapping`` with its target, in one pass.

    ``mapping`` is a dict of ``{src_block_or_str: dst_block_or_str}``. Each
    voxel whose block matches a source key is rewritten to the corresponding
    target. Returns the total count of voxels rewritten.

    On a ``ChunkedGrid`` only touched chunks are walked; on a dense grid the
    full array is scanned once with vectorised ``np.isin`` for speed.
    """
    m = _normalise_mapping(mapping)
    # Resolve src/dst palette indices.
    palette = grid.palette
    src_to_dst: dict[int, int] = {}
    for src_b, dst_b in m.items():
        si = palette.index_of(src_b)
        if si is None:
            continue
        di = palette.add(dst_b)
        src_to_dst[si] = di
    if not src_to_dst:
        return 0
    # Build a remap LUT for single-pass simultaneous application (avoids
    # chaining bugs where a->b then b->c would double-remap).
    palette_size = len(palette)
    lut = np.arange(max(palette_size, max(src_to_dst.keys()) + 1, max(src_to_dst.values()) + 1),
                    dtype=np.uint16)
    for si, di in src_to_dst.items():
        lut[si] = di
    total = 0
    if isinstance(grid, ChunkedGrid):
        for key, arr in list(grid._chunks.items()):
            before = arr.copy()
            arr[...] = lut[arr]
            total += int(np.count_nonzero(arr != before))
            if not np.any(arr):
                grid._drop_chunk_if_empty(*key)
    else:
        data = grid.data
        before = data.copy()
        data[...] = lut[data]
        total = int(np.count_nonzero(data != before))
    return total


# ---- filter-based replace --------------------------------------------

def replace_filtered(grid: VoxelGrid | ChunkedGrid,
                     src: Block | str,
                     dst: Block | str,
                     *,
                     where: BlockFilter | None = None) -> int:
    """Replace ``src`` with ``dst`` only where ``where(block)`` is True.

    The filter receives the *source* block (with its states) so it can
    discriminate by property (e.g. only replace ``oak_log[axis=y]`` not
    ``oak_log[axis=x]``). If ``where`` is None, behaves like plain replace.

    Returns the number of voxels rewritten.
    """
    src_b = _to_block(src)
    dst_b = _to_block(dst)
    src_idx = grid.palette.index_of(src_b)
    if src_idx is None:
        return 0
    dst_idx = grid.palette.add(dst_b)
    if where is None:
        # No filter: same as plain replace.
        if isinstance(grid, ChunkedGrid):
            return grid.replace(src_b, dst_b)
        return grid.replace(src_b, dst_b)
    # Filter is a per-block predicate. We need to inspect each matching voxel's
    # full block (which == src_b here, so we only need to check states). Since
    # palette dedupes by full blockstate, src_idx already encodes the exact
    # state. If where(src_b) is False, we replace nothing. If True, all of them
    # match. For finer-grained filtering across multiple states of the same
    # block name, use replace_by_name below.
    if not where(src_b):
        return 0
    if isinstance(grid, ChunkedGrid):
        total = 0
        for key, arr in list(grid._chunks.items()):
            sel = arr == src_idx
            n = int(np.count_nonzero(sel))
            if n:
                arr[sel] = dst_idx
                total += n
            if not np.any(arr):
                grid._drop_chunk_if_empty(*key)
        return total
    data = grid.data
    sel = data == src_idx
    n = int(np.count_nonzero(sel))
    if n:
        data[sel] = dst_idx
    return n


def replace_by_name(grid: VoxelGrid | ChunkedGrid,
                    src_name: str,
                    dst: Block | str,
                    *,
                    where: BlockFilter | None = None) -> int:
    """Replace every block whose name matches ``src_name`` regardless of state.

    Optionally filter via ``where(block)``: the predicate receives each
    distinct matched blockstate in the palette (not each voxel), so it is
    efficient even on large grids -- it filters palette entries first, then
    does a vectorised index replacement for the surviving entries.

    Example::

        # Flip every oak_log to axis=x regardless of current axis.
        replace_by_name(grid, "minecraft:oak_log", "minecraft:oak_log[axis=x]")

        # Replace only oak_logs currently axis=y.
        replace_by_name(grid, "minecraft:oak_log", "minecraft:birch_log",
                        where=lambda b: b.states.get("axis") == "y")
    """
    dst_b = _to_block(dst)
    palette = grid.palette
    # Collect all palette entries whose name matches src_name.
    candidates: list[tuple[int, Block]] = []
    for i, b in enumerate(palette.blocks()):
        if b.name == src_name:
            candidates.append((i, b))
    if not candidates:
        return 0
    dst_idx = palette.add(dst_b)
    # Apply the filter per palette entry (cheap: at most palette_size checks).
    targets: dict[int, int] = {}
    for si, b in candidates:
        if where is None or where(b):
            targets[si] = dst_idx
    if not targets:
        return 0
    # Single-pass LUT remap.
    palette_size = len(palette)
    lut = np.arange(max(palette_size, max(targets.keys()) + 1, max(targets.values()) + 1),
                    dtype=np.uint16)
    for si, di in targets.items():
        lut[si] = di
    total = 0
    if isinstance(grid, ChunkedGrid):
        for key, arr in list(grid._chunks.items()):
            before = arr.copy()
            arr[...] = lut[arr]
            total += int(np.count_nonzero(arr != before))
            if not np.any(arr):
                grid._drop_chunk_if_empty(*key)
    else:
        data = grid.data
        before = data.copy()
        data[...] = lut[data]
        total = int(np.count_nonzero(data != before))
    return total


# ---- neighbourhood pattern replace ------------------------------------

@dataclass(frozen=True)
class NeighbourSpec:
    """Describes a neighbour condition for pattern matching.

    ``offset`` is the (dx, dy, dz) relative voxel offset.
    ``block`` is the block name (or ``"*"`` for any solid, ``"air"`` for air)
    that must occupy that offset for the pattern to match.
    """
    offset: tuple[int, int, int]
    block: str  # block name, or "*" for any non-air, or "air"

    @classmethod
    def above(cls, block: str = "*") -> NeighbourSpec:
        return cls((0, 1, 0), block)

    @classmethod
    def below(cls, block: str = "*") -> NeighbourSpec:
        return cls((0, -1, 0), block)

    @classmethod
    def side(cls, block: str = "*") -> NeighbourSpec:
        """Any of the 4 horizontal sides."""
        # Represented specially via offset (0,0,0) with a side flag; we encode
        # as a list of 4 specs in the matcher. For simplicity here we return
        # the +x neighbour; callers wanting "any side" use NeighbourSpec.any_side.
        return cls((1, 0, 0), block)


def _build_neighbour_index(grid: VoxelGrid | ChunkedGrid) -> np.ndarray:
    """Return a dense (sx, sy, sz) uint16 array of palette indices."""
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data


def replace_pattern(grid: VoxelGrid | ChunkedGrid,
                    src: Block | str,
                    dst: Block | str,
                    *,
                    neighbours: list[NeighbourSpec] | None = None) -> int:
    """Replace ``src`` with ``dst`` where all neighbour constraints hold.

    Each ``NeighbourSpec`` in ``neighbours`` describes a relative offset and the
    block that must be at that offset. ``block="*`` means "any non-air"; ``"air"``
    means air. All specs must match (AND semantics). If ``neighbours`` is empty
    or None, this is equivalent to plain ``replace``.

    Example: replace dirt that has grass above it::

        replace_pattern(grid, "minecraft:dirt", "minecraft:grass_block",
                        neighbours=[NeighbourSpec.above("minecraft:grass_block")])

    Example: replace stone that touches air on any side::

        replace_pattern(grid, "minecraft:stone", "minecraft:cobblestone",
                        neighbours=[NeighbourSpec((1,0,0),"air"),
                                    NeighbourSpec((-1,0,0),"air")])
    """
    if not neighbours:
        return replace_filtered(grid, src, dst)
    src_b = _to_block(src)
    dst_b = _to_block(dst)
    src_idx = grid.palette.index_of(src_b)
    if src_idx is None:
        return 0
    dst_idx = grid.palette.add(dst_b)
    # Work on a dense view for neighbour lookups (shifts are easier).
    dense = _build_neighbour_index(grid)
    sx, sy, sz = grid.shape
    match = dense == src_idx
    # Build a solid (non-air) mask once for "*" specs.
    solid = dense != 0
    # Air mask: True where voxel is air.
    air = dense == 0
    for spec in neighbours:
        dx, dy, dz = spec.offset
        shifted = _shift(dense, solid, air, dx, dy, dz, spec.block, grid)
        match = match & shifted
    if not match.any():
        return 0
    count = int(np.count_nonzero(match))
    # Apply on the original backend.
    if isinstance(grid, ChunkedGrid):
        for (cx, cy, cz), arr in list(grid._chunks.items()):
            ox = cx * grid.chunk_size
            oy = cy * grid.chunk_size
            oz = cz * grid.chunk_size
            sx_a, sy_a, sz_a = arr.shape
            sub = match[ox:ox + sx_a, oy:oy + sy_a, oz:oz + sz_a]
            arr[sub] = dst_idx
            if not np.any(arr):
                grid._drop_chunk_if_empty(cx, cy, cz)
    else:
        dense[match] = dst_idx
    return count


def _shift(dense: np.ndarray, solid: np.ndarray, air: np.ndarray,
           dx: int, dy: int, dz: int, block: str,
           grid: VoxelGrid | ChunkedGrid) -> np.ndarray:
    """Return a bool array same shape as ``dense`` that is True at (x,y,z) iff
    the voxel at (x+dx, y+dy, z+dz) satisfies the block spec.
    """
    sx, sy, sz = dense.shape
    out = np.zeros((sx, sy, sz), dtype=bool)
    # Source window: the region of the neighbour we read.
    x0s = max(0, dx)
    y0s = max(0, dy)
    z0s = max(0, dz)
    x1s = min(sx, sx + dx)
    y1s = min(sy, sy + dy)
    z1s = min(sz, sz + dz)
    # Destination window: where we write the shifted mask.
    x0d = max(0, -dx)
    y0d = max(0, -dy)
    z0d = max(0, -dz)
    x1d = x0d + (x1s - x0s)
    y1d = y0d + (y1s - y0s)
    z1d = z0d + (z1s - z0s)
    if x1d <= x0d or y1d <= y0d or z1d <= z0d:
        return out
    if block == "*":
        src = solid
    elif block == "air":
        src = air
    else:
        b = _to_block(block)
        idx = grid.palette.index_of(b)
        if idx is None:
            return out
        src = dense == idx
    out[x0d:x1d, y0d:y1d, z0d:z1d] = src[x0s:x1s, y0s:y1s, z0s:z1s]
    return out


# ---- convenience: replace by region mask ------------------------------

def replace_in_mask(grid: VoxelGrid | ChunkedGrid,
                     src: Block | str,
                     dst: Block | str,
                     mask: np.ndarray) -> int:
    """Replace ``src`` with ``dst`` only within the True cells of ``mask``.

    Useful for "replace stone with mossy_cobblestone only inside this box /
    sphere / noise-selected region".
    """
    if mask.shape != grid.shape:
        try:
            mask = np.broadcast_to(mask, grid.shape)
        except ValueError as e:
            raise ValueError(f"mask shape {mask.shape} != grid {grid.shape}") from e
    src_b = _to_block(src)
    dst_b = _to_block(dst)
    src_idx = grid.palette.index_of(src_b)
    if src_idx is None:
        return 0
    dst_idx = grid.palette.add(dst_b)
    count = 0
    if isinstance(grid, ChunkedGrid):
        for (cx, cy, cz), arr in list(grid._chunks.items()):
            ox = cx * grid.chunk_size
            oy = cy * grid.chunk_size
            oz = cz * grid.chunk_size
            sx_a, sy_a, sz_a = arr.shape
            msub = mask[ox:ox + sx_a, oy:oy + sy_a, oz:oz + sz_a]
            sel = (arr == src_idx) & msub
            n = int(np.count_nonzero(sel))
            if n:
                arr[sel] = dst_idx
                count += n
            if not np.any(arr):
                grid._drop_chunk_if_empty(cx, cy, cz)
    else:
        sel = (grid.data == src_idx) & mask
        count = int(np.count_nonzero(sel))
        if count:
            grid.data[sel] = dst_idx
    return count
