"""Retexture: swap blockstate properties on existing voxels in-place.

This module rewrites block *states* (axis, facing, half, shape, etc.) without
changing the block name. It is the foundation for:

- Rotating logs/pillars (``axis=y`` -> ``axis=x``).
- Flipping stairs (``half=top`` <-> ``half=bottom``).
- Reorienting stairs/fences/walls (``facing=north`` -> ``facing=east``).
- Randomising wall patterns (set ``axis`` per-cell from noise).

The core primitive is ``retexture(grid, property, value, name=None, where=None)``
which scans the palette for blocks that have the given property and rewrites
matching voxels to a new palette entry with that property set to ``value``.

For bulk property transforms (e.g. "rotate all axis values +1: x->y, y->z,
z->x") use ``retexture_map(grid, property, mapping, name=None)``.

All operations work on both dense and chunked backends.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..blocks.block import Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid


def _to_block(b: Block | str) -> Block:
    if isinstance(b, str):
        return Block.parse(b)
    return b


def _set_state(block: Block, property: str, value: object) -> Block:
    """Return a new Block with ``property`` set to ``value``."""
    states = dict(block.states)
    states[property] = value
    return Block(name=block.name, states=tuple(sorted(states.items())))


def retexture(grid: VoxelGrid | ChunkedGrid,
              property: str,
              value: object,
              *,
              name: str | None = None,
              where: Callable[[Block], bool] | None = None) -> int:
    """Set ``property`` = ``value`` on every block that has that property.

    Args:
        property: state property name (e.g. ``"axis"``, ``"facing"``, ``"half"``).
        value: the new value (e.g. ``"x"``, ``"north"``, ``"top"``).
        name: if given, only blocks with this block name are affected (e.g.
            ``"minecraft:oak_log"``). If None, every block with the property
            is affected.
        where: optional predicate ``(block) -> bool`` for finer filtering;
            receives each palette entry, not each voxel.

    Returns the number of voxels rewritten.
    """
    palette = grid.palette
    # Collect palette indices whose block has the property (and optionally
    # matches name + where predicate).
    targets: dict[int, int] = {}
    for i, b in enumerate(palette.blocks()):
        prop_names = {k for k, _ in b.states}
        if property not in prop_names:
            continue
        if name is not None and b.name != name:
            continue
        if where is not None and not where(b):
            continue
        new_b = _set_state(b, property, value)
        di = palette.add(new_b)
        if di != i:
            targets[i] = di
    if not targets:
        return 0
    return _apply_index_map(grid, targets)


def retexture_map(grid: VoxelGrid | ChunkedGrid,
                  property: str,
                  mapping: dict[object, object],
                  *,
                  name: str | None = None,
                  where: Callable[[Block], bool] | None = None) -> int:
    """Remap a state property across many values in one pass.

    ``mapping`` is ``{old_value: new_value}``, e.g.
    ``{"x": "y", "y": "z", "z": "x"}`` to rotate axes.

    Returns the number of voxels rewritten.
    """
    palette = grid.palette
    targets: dict[int, int] = {}
    for i, b in enumerate(palette.blocks()):
        prop_names = {k for k, _ in b.states}
        if property not in prop_names:
            continue
        if name is not None and b.name != name:
            continue
        cur_val = dict(b.states).get(property)
        if cur_val not in mapping:
            continue
        if where is not None and not where(b):
            continue
        new_b = _set_state(b, property, mapping[cur_val])
        di = palette.add(new_b)
        if di != i:
            targets[i] = di
    if not targets:
        return 0
    return _apply_index_map(grid, targets)


def retexture_random(grid: VoxelGrid | ChunkedGrid,
                     property: str,
                     values: list[object],
                     *,
                     name: str | None = None,
                     seed: int = 0) -> int:
    """Assign ``property`` a random value from ``values`` per voxel.

    Useful for randomising wall post orientations, stair facings, or
    mossy-stone-vs-clean-stone patterns. The value is chosen per-voxel using
    a deterministic PRNG seeded by ``seed``.

    Returns the number of voxels rewritten.
    """
    if not values:
        return 0
    palette = grid.palette
    rng = np.random.default_rng(seed)
    # Build per-palette-entry target indices for each value.
    # For each palette entry with the property, pre-compute the new palette
    # index for each possible value.
    src_indices: list[int] = []
    dst_per_value: list[list[int]] = []
    for i, b in enumerate(palette.blocks()):
        prop_names = {k for k, _ in b.states}
        if property not in prop_names:
            continue
        if name is not None and b.name != name:
            continue
        dst_list = []
        for v in values:
            new_b = _set_state(b, property, v)
            dst_list.append(palette.add(new_b))
        src_indices.append(i)
        dst_per_value.append(dst_list)
    if not src_indices:
        return 0
    total = 0
    if isinstance(grid, ChunkedGrid):
        for (cx, cy, cz), arr in list(grid._chunks.items()):
            for si_idx, si in enumerate(src_indices):
                sel = arr == si
                n = int(np.count_nonzero(sel))
                if not n:
                    continue
                # Pick a random value index per voxel.
                picks = rng.integers(len(values), size=n)
                # Map picks to dst palette indices.
                dst_list = dst_per_value[si_idx]
                arr[sel] = np.fromiter((dst_list[p] for p in picks),
                                       dtype=np.uint16, count=n)
                total += n
            if not np.any(arr):
                grid._drop_chunk_if_empty(cx, cy, cz)
    else:
        data = grid.data
        for si_idx, si in enumerate(src_indices):
            sel = data == si
            n = int(np.count_nonzero(sel))
            if not n:
                continue
            picks = rng.integers(len(values), size=n)
            dst_list = dst_per_value[si_idx]
            data[sel] = np.fromiter((dst_list[p] for p in picks),
                                     dtype=np.uint16, count=n)
            total += n
    return total


def _apply_index_map(grid: VoxelGrid | ChunkedGrid,
                     mapping: dict[int, int]) -> int:
    """Apply a palette-index -> palette-index mapping across the grid.

    This does a **single-pass simultaneous remap** to avoid chaining bugs
    (where applying ``a->b`` then ``b->c`` would incorrectly remap the
    just-changed voxels a second time). We build a lookup table and apply
    it in one vectorised step.
    """
    if not mapping:
        return 0
    palette_size = len(grid.palette)
    # Build a remap LUT: lut[i] = new_index for i, or i if unchanged.
    lut = np.arange(max(palette_size, max(mapping.keys()) + 1, max(mapping.values()) + 1),
                    dtype=np.uint16)
    for si, di in mapping.items():
        lut[si] = di
    total = 0
    if isinstance(grid, ChunkedGrid):
        for key, arr in list(grid._chunks.items()):
            before = arr.copy()
            # Apply LUT to every voxel.
            arr[...] = lut[arr]
            changed = int(np.count_nonzero(arr != before))
            total += changed
            if not np.any(arr):
                grid._drop_chunk_if_empty(*key)
    else:
        data = grid.data
        before = data.copy()
        data[...] = lut[data]
        total = int(np.count_nonzero(data != before))
    return total
