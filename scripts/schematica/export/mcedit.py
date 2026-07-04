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

import warnings
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
    "minecraft:granite": 1,
    "minecraft:diorite": 1,
    "minecraft:andesite": 1,
    "minecraft:deepslate": 1,
    "minecraft:tuff": 1,
    "minecraft:calcite": 1,
    "minecraft:smooth_stone": 1,
    "minecraft:grass_block": 2,
    "minecraft:dirt": 3,
    "minecraft:cobblestone": 4,
    "minecraft:oak_planks": 5,
    "minecraft:spruce_planks": 5,
    "minecraft:birch_planks": 5,
    "minecraft:bedrock": 7,
    "minecraft:sand": 12,
    "minecraft:red_sand": 12,
    "minecraft:gravel": 13,
    "minecraft:gold_ore": 14,
    "minecraft:iron_ore": 15,
    "minecraft:coal_ore": 16,
    "minecraft:oak_log": 17,
    "minecraft:spruce_log": 17,
    "minecraft:birch_log": 17,
    "minecraft:oak_leaves": 18,
    "minecraft:glass": 20,
    "minecraft:lapis_ore": 21,
    "minecraft:lapis_block": 22,
    "minecraft:sandstone": 24,
    "minecraft:red_bed": 26,
    "minecraft:oak_slab": 44,
    "minecraft:stone_slab": 44,
    "minecraft:bricks": 45,
    "minecraft:mossy_cobblestone": 48,
    "minecraft:obsidian": 49,
    "minecraft:torch": 50,
    "minecraft:chest": 54,
    "minecraft:diamond_block": 57,
    "minecraft:crafting_table": 58,
    "minecraft:furnace": 61,
    "minecraft:oak_door": 64,
    "minecraft:ladder": 65,
    "minecraft:cobblestone_stairs": 67,
    "minecraft:iron_door": 71,
    "minecraft:redstone_torch": 76,
    "minecraft:oak_trapdoor": 96,
    "minecraft:oak_fence": 85,
    "minecraft:glowstone": 89,
    "minecraft:portal": 90,
    "minecraft:glass_pane": 102,
    "minecraft:iron_bars": 101,
    "minecraft:oak_fence_gate": 107,
    "minecraft:stone_brick_stairs": 109,
    "minecraft:stone_bricks": 98,
    "minecraft:mossy_stone_bricks": 98,  # same id, meta 1 -- approximated here
    "minecraft:cracked_stone_bricks": 98,
    "minecraft:redstone_lamp": 123,
    "minecraft:ender_chest": 130,
    "minecraft:iron_block": 42,
    "minecraft:gold_block": 41,
    "minecraft:emerald_block": 133,
    "minecraft:cobblestone_wall": 139,
    "minecraft:beacon": 138,
    "minecraft:anvil": 145,
    "minecraft:redstone_block": 152,
    "minecraft:barrier": 166,
    "minecraft:iron_trapdoor": 167,
    "minecraft:coal_block": 173,
    "minecraft:end_stone": 121,
    "minecraft:quartz_block": 155,
    "minecraft:purple_stained_glass": 95,
    "minecraft:prismarine": 168,
    "minecraft:sea_lantern": 169,
    "minecraft:packed_ice": 174,
    "minecraft:chain": 101,
    "minecraft:lantern": 50,
    "minecraft:oak_sign": 63,
    "minecraft:oak_wall_sign": 68,
}

DEFAULT_LEGACY_META: dict[str, int] = {
    "minecraft:granite": 1,
    "minecraft:diorite": 3,
    "minecraft:andesite": 5,
    "minecraft:spruce_planks": 1,
    "minecraft:birch_planks": 2,
    "minecraft:spruce_log": 1,
    "minecraft:birch_log": 2,
    "minecraft:red_sand": 1,
    "minecraft:mossy_stone_bricks": 1,
    "minecraft:cracked_stone_bricks": 2,
    "minecraft:chiseled_stone_bricks": 3,
}

_COLOR_META = {
    "white": 0,
    "orange": 1,
    "magenta": 2,
    "light_blue": 3,
    "yellow": 4,
    "lime": 5,
    "pink": 6,
    "gray": 7,
    "light_gray": 8,
    "cyan": 9,
    "purple": 10,
    "blue": 11,
    "brown": 12,
    "green": 13,
    "red": 14,
    "black": 15,
}

for _color, _meta in _COLOR_META.items():
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_wool"] = 35
    DEFAULT_LEGACY_META[f"minecraft:{_color}_wool"] = _meta
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_stained_glass"] = 95
    DEFAULT_LEGACY_META[f"minecraft:{_color}_stained_glass"] = _meta
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_stained_glass_pane"] = 160
    DEFAULT_LEGACY_META[f"minecraft:{_color}_stained_glass_pane"] = _meta
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_terracotta"] = 159
    DEFAULT_LEGACY_META[f"minecraft:{_color}_terracotta"] = _meta
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_concrete"] = 251
    DEFAULT_LEGACY_META[f"minecraft:{_color}_concrete"] = _meta
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_bed"] = 26
    DEFAULT_LEGACY_IDS[f"minecraft:{_color}_carpet"] = 171
    DEFAULT_LEGACY_META[f"minecraft:{_color}_carpet"] = _meta


def _resolve_id(blockstate_str: str, mapping: dict[str, int]) -> int:
    """Look up the legacy id for a blockstate, falling back to the base name."""
    if blockstate_str in mapping:
        return mapping[blockstate_str]
    base = blockstate_str.split("[", 1)[0]
    return mapping.get(base, 0)


def _resolve_meta(blockstate_str: str, mapping: dict[str, int]) -> int:
    """Look up legacy block metadata, falling back to zero."""
    if blockstate_str in mapping:
        return mapping[blockstate_str]
    base = blockstate_str.split("[", 1)[0]
    return mapping.get(base, 0)


def legacy_unmapped_blocks(grid: VoxelGrid | ChunkedGrid,
                           legacy_ids: dict[str, int] | None = None) -> list[str]:
    """Return non-air palette entries that would become air in MCEdit export."""
    ids = dict(DEFAULT_LEGACY_IDS)
    if legacy_ids:
        ids.update(legacy_ids)
    unmapped: list[str] = []
    for block in grid.palette.blocks():
        blockstate = block.to_blockstate_str()
        base = blockstate.split("[", 1)[0]
        if base == "minecraft:air":
            continue
        if _resolve_id(blockstate, ids) == 0:
            unmapped.append(blockstate)
    return unmapped


def _check_unmapped_legacy_blocks(grid: VoxelGrid | ChunkedGrid,
                                  legacy_ids: dict[str, int] | None,
                                  strict: bool) -> None:
    unmapped = legacy_unmapped_blocks(grid, legacy_ids)
    if not unmapped:
        return
    sample = ", ".join(unmapped[:8])
    suffix = "..." if len(unmapped) > 8 else ""
    message = (
        f"MCEdit export will map {len(unmapped)} non-air block(s) to air because "
        f"they have no legacy id mapping: {sample}{suffix}. Pass legacy_ids=... "
        f"or choose Sponge/Litematica for modern blocks."
    )
    if strict:
        raise ValueError(message)
    warnings.warn(message, RuntimeWarning, stacklevel=3)


def _encode_voxels_dense(grid: VoxelGrid, ids: dict[str, int], meta: dict[str, int]) -> tuple[bytes, bytes]:
    sx, sy, sz = grid.shape
    blocks = bytearray(sx * sy * sz)
    data = bytearray(sx * sy * sz)
    palette = grid.palette.blocks()
    idx_to_id = [0] * len(palette)
    idx_to_meta = [0] * len(palette)
    for i, b in enumerate(palette):
        blockstate = b.to_blockstate_str()
        idx_to_id[i] = _resolve_id(blockstate, ids)
        idx_to_meta[i] = _resolve_meta(blockstate, meta)
    arr = grid.data
    i = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                v = int(arr[x, y, z])
                blocks[i] = idx_to_id[v] & 0xFF
                data[i] = idx_to_meta[v] & 0xFF
                i += 1
    return bytes(blocks), bytes(data)


def _encode_voxels_chunked(grid: ChunkedGrid, ids: dict[str, int], meta: dict[str, int]) -> tuple[bytes, bytes]:
    sx, sy, sz = grid.shape
    blocks = bytearray(sx * sy * sz)
    data = bytearray(sx * sy * sz)
    palette = grid.palette.blocks()
    idx_to_id = [_resolve_id(b.to_blockstate_str(), ids) for b in palette]
    idx_to_meta = [_resolve_meta(b.to_blockstate_str(), meta) for b in palette]
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
                v = int(plane[x, z])
                blocks[rowoff + x] = idx_to_id[v] & 0xFF
                data[rowoff + x] = idx_to_meta[v] & 0xFF
    return bytes(blocks), bytes(data)


def write_mcedit(grid: VoxelGrid | ChunkedGrid, path: str | Path, *,
                 legacy_ids: dict[str, int] | None = None,
                 block_meta: dict[str, int] | None = None,
                 strict: bool = False) -> Path:
    """Write a legacy MCEdit `.schematic` (gzip NBT, byte block ids).

    ``legacy_ids`` optionally augments/overrides ``DEFAULT_LEGACY_IDS``.
    ``block_meta`` optionally augments/overrides ``DEFAULT_LEGACY_META``.
    If ``strict`` is True, non-air blocks without legacy mappings raise instead
    of being written as air.
    """
    path = Path(path)
    _check_unmapped_legacy_blocks(grid, legacy_ids, strict)
    ids = dict(DEFAULT_LEGACY_IDS)
    meta = dict(DEFAULT_LEGACY_META)
    if legacy_ids:
        ids.update(legacy_ids)
    if block_meta:
        meta.update(block_meta)
    if isinstance(grid, ChunkedGrid):
        blocks, data = _encode_voxels_chunked(grid, ids, meta)
    else:
        blocks, data = _encode_voxels_dense(grid, ids, meta)
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
