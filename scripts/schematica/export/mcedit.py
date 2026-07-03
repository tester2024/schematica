"""Write legacy MCEdit `.schematic` files (NBT format used by WorldEdit before
Sponge, Minecraft 1.12 and earlier).

Legacy format (uncompressed or gzip; we gzip):
  Root compound (no "Schematic" wrapper):
    Width, Height, Length (short)
    Materials: String("Classic")     # Alpha/Classic; we always emit "Alpha"
    Blocks: ByteArray                 # 1 byte per voxel, XZY order
    Data: ByteArray                    # 1 byte per voxel block metadata
    Offset / WEOriginX/Y/Z (optional)

Block ids are 0-255 single bytes -- this format predates the flattening. The
caller passes a mapping ``blockstate_str -> legacy_id`` so unknown modern
blocks can be mapped to ids. Voxels whose block has no mapping are written as
air (id 0). Block metadata (the old ``Data`` array) is set from an optional
``block_meta`` mapping; default 0 everywhere.
"""
from __future__ import annotations

from pathlib import Path

import nbtlib
import numpy as np
from nbtlib import ByteArray, Compound, Short, String

from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

# Sensible default mapping of common vanilla blocks to legacy ids. Anything
# not in this map (and not in the caller's override) becomes air (id 0).
DEFAULT_LEGACY_IDS: dict[str, int] = {
    "minecraft:air": 0,
    "minecraft:stone": 1,
    "minecraft:grass_block": 2,
    "minecraft:dirt": 3,
    "minecraft:cobblestone": 4,
    "minecraft:oak_planks": 5,
    "minecraft:bedrock": 7,
    "minecraft:sand": 12,
    "minecraft:gravel": 13,
    "minecraft:gold_ore": 14,
    "minecraft:iron_ore": 15,
    "minecraft:coal_ore": 16,
    "minecraft:oak_log": 17,
    "minecraft:oak_leaves": 18,
    "minecraft:glass": 20,
    "minecraft:lapis_ore": 21,
    "minecraft:lapis_block": 22,
    "minecraft:sandstone": 24,
    "minecraft:bricks": 45,
    "minecraft:obsidian": 49,
    "minecraft:oak_fence": 85,
    "minecraft:glowstone": 89,
    "minecraft:stone_bricks": 98,
    "minecraft:mossy_stone_bricks": 98,  # same id, meta 1 -- approximated here
    "minecraft:cracked_stone_bricks": 98,
    "minecraft:iron_block": 42,
    "minecraft:gold_block": 41,
    "minecraft:diamond_block": 57,
    "minecraft:emerald_block": 133,
    "minecraft:end_stone": 121,
    "minecraft:quartz_block": 155,
    "minecraft:purple_stained_glass": 95,
    "minecraft:prismarine": 168,
    "minecraft:sea_lantern": 169,
    "minecraft:red_sand": 179,
    "minecraft:packed_ice": 174,
    "minecraft:mossy_cobblestone": 48,
}


def _resolve_id(blockstate_str: str, mapping: dict[str, int]) -> int:
    """Look up the legacy id for a blockstate, falling back to the base name."""
    if blockstate_str in mapping:
        return mapping[blockstate_str]
    base = blockstate_str.split("[", 1)[0]
    return mapping.get(base, 0)


def _encode_voxels_dense(grid: VoxelGrid, mapping: dict[str, int]) -> tuple[bytes, bytes]:
    sx, sy, sz = grid.shape
    blocks = bytearray(sx * sy * sz)
    data = bytearray(sx * sy * sz)
    palette = grid.palette.blocks()
    idx_to_id = [0] * len(palette)
    for i, b in enumerate(palette):
        idx_to_id[i] = _resolve_id(b.to_blockstate_str(), mapping)
    arr = grid.data
    i = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                v = int(arr[x, y, z])
                blocks[i] = idx_to_id[v] & 0xFF
                # data byte is metadata; we always emit 0 here (no per-state map)
                i += 1
    return bytes(blocks), bytes(data)


def _encode_voxels_chunked(grid: ChunkedGrid, mapping: dict[str, int]) -> tuple[bytes, bytes]:
    sx, sy, sz = grid.shape
    blocks = bytearray(sx * sy * sz)
    data = bytearray(sx * sy * sz)
    palette = grid.palette.blocks()
    idx_to_id = [_resolve_id(b.to_blockstate_str(), mapping) for b in palette]
    cs = grid.chunk_size
    chunks_by_cy: dict[int, dict[tuple[int, int], np.ndarray]] = {}
    for (cx, cy, cz), arr in grid._chunks.items():
        chunks_by_cy.setdefault(cy, {})[(cx, cz)] = arr
    for y in range(sy):
        cy = y // cs
        ly = y % cs
        row = chunks_by_cy.get(cy, {})
        # Build the (sx, sz) plane for this Y.
        plane = np.zeros((sx, sz), dtype=np.uint16)
        for (cx, cz), arr in row.items():
            ox = cx * cs
            oz = cz * cs
            sx_a, sy_a, sz_a = arr.shape
            if ly >= sy_a:
                continue
            plane[ox:ox + sx_a, oz:oz + sz_a] = arr[:, ly, :]
        # Emit in z-outer, x-inner order.
        base = y * sx * sz
        for z in range(sz):
            rowoff = base + z * sx
            for x in range(sx):
                blocks[rowoff + x] = idx_to_id[int(plane[x, z])] & 0xFF
    return bytes(blocks), bytes(data)


def write_mcedit(grid: VoxelGrid | ChunkedGrid, path: str | Path, *,
                 legacy_ids: dict[str, int] | None = None,
                 block_meta: dict[str, int] | None = None) -> Path:
    """Write a legacy MCEdit `.schematic` (gzip NBT, byte block ids).

    ``legacy_ids`` optionally augments/overrides ``DEFAULT_LEGACY_IDS``.
    ``block_meta`` is accepted for future use; currently metadata is emitted
    as all-zero (callers should not rely on it).
    """
    path = Path(path)
    mapping = dict(DEFAULT_LEGACY_IDS)
    if legacy_ids:
        mapping.update(legacy_ids)
    if isinstance(grid, ChunkedGrid):
        blocks, data = _encode_voxels_chunked(grid, mapping)
    else:
        blocks, data = _encode_voxels_dense(grid, mapping)
    sx, sy, sz = grid.shape
    root = Compound({
        "Width": Short(sx),
        "Height": Short(sy),
        "Length": Short(sz),
        "Materials": String("Alpha"),
        "Blocks": ByteArray([b if b < 128 else b - 256 for b in blocks]),
        "Data": ByteArray([b if b < 128 else b - 256 for b in data]),
    })
    file = nbtlib.File(root, gzipped=True)
    file.save(path)
    return path
