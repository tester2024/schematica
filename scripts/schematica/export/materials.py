"""Material intelligence: automatic legacy block substitutions.

When exporting to the legacy MCEdit format (``.schematic``), modern blocks that
don't have a legacy ID mapping are silently converted to air, causing data
loss. This module provides:

- **suggest_substitutions**: for each unmapped modern block, suggest the closest
  visually/functionally equivalent block that *does* have a legacy mapping.
- **apply_substitutions**: replace unmapped blocks with their suggested
  substitutes on the grid, so the MCEdit export preserves the build's shape and
  approximate appearance.

The substitution table encodes Minecraft material knowledge: e.g.
``minecraft:deepslate`` -> ``minecraft:stone``, ``minecraft:cobblestone_wall``
-> ``minecraft:cobblestone``, ``minecraft:smooth_stone`` -> ``minecraft:stone``.

Usage::

    from schematica.export.materials import suggest_substitutions

    subs = suggest_substitutions(grid)
    for block, sub in subs.items():
        print(f"{block} -> {sub}")
"""
from __future__ import annotations

import re

import numpy as np

from ..blocks.block import AIR, Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid
from .mcedit import DEFAULT_LEGACY_IDS, _resolve_id

Grid = VoxelGrid | ChunkedGrid

# ---- substitution knowledge base ---------------------------------------
# Ordered by specificity: more specific rules first.
# Each entry: (modern_block_name_or_pattern, suggested_substitute)
# Patterns use * as a wildcard prefix/suffix matcher.

_SUBSTITUTION_TABLE: list[tuple[str, str]] = [
    # Deepslate family -> stone family
    ("minecraft:deepslate", "minecraft:stone"),
    ("minecraft:cobbled_deepslate", "minecraft:cobblestone"),
    ("minecraft:deepslate_bricks", "minecraft:stone_bricks"),
    ("minecraft:deepslate_tiles", "minecraft:stone_bricks"),
    ("minecraft:polished_deepslate", "minecraft:smooth_stone"),
    ("minecraft:chiseled_deepslate", "minecraft:stone_bricks"),
    ("minecraft:cracked_deepslate_bricks", "minecraft:mossy_stone_bricks"),
    ("minecraft:cracked_deepslate_tiles", "minecraft:mossy_stone_bricks"),
    ("minecraft:deepslate_coal_ore", "minecraft:coal_ore"),
    ("minecraft:deepslate_iron_ore", "minecraft:iron_ore"),
    ("minecraft:deepslate_gold_ore", "minecraft:gold_ore"),
    ("minecraft:deepslate_diamond_ore", "minecraft:diamond_ore"),
    ("minecraft:deepslate_lapis_ore", "minecraft:lapis_ore"),
    ("minecraft:deepslate_redstone_ore", "minecraft:redstone_ore"),
    ("minecraft:deepslate_emerald_ore", "minecraft:emerald_ore"),
    # Tuff / calcite -> stone
    ("minecraft:tuff", "minecraft:stone"),
    ("minecraft:calcite", "minecraft:stone"),
    ("minecraft:smooth_basalt", "minecraft:stone"),
    ("minecraft:basalt", "minecraft:stone"),
    ("minecraft:polished_basalt", "minecraft:stone"),
    # Nether blocks
    ("minecraft:netherrack", "minecraft:netherrack"),  # mapped
    ("minecraft:blackstone", "minecraft:obsidian"),
    ("minecraft:polished_blackstone", "minecraft:obsidian"),
    ("minecraft:polished_blackstone_bricks", "minecraft:stone_bricks"),
    ("minecraft:cracked_polished_blackstone_bricks", "minecraft:mossy_stone_bricks"),
    ("minecraft:chiseled_polished_blackstone", "minecraft:stone_bricks"),
    ("minecraft:gilded_blackstone", "minecraft:gold_ore"),
    ("minecraft:basalt", "minecraft:stone"),
    # 1.14+ blocks
    ("minecraft:smooth_stone", "minecraft:stone"),
    ("minecraft:smooth_sandstone", "minecraft:sandstone"),
    ("minecraft:smooth_red_sandstone", "minecraft:red_sand"),
    ("minecraft:smooth_quartz", "minecraft:quartz_block"),
    ("minecraft:granite", "minecraft:stone"),
    ("minecraft:diorite", "minecraft:stone"),
    ("minecraft:andesite", "minecraft:stone"),
    ("minecraft:polished_granite", "minecraft:granite"),
    ("minecraft:polished_diorite", "minecraft:diorite"),
    ("minecraft:polished_andesite", "minecraft:andesite"),
    # Walls -> cobblestone wall (mapped)
    ("minecraft:*_wall", "minecraft:cobblestone_wall"),
    # Fences -> oak_fence (mapped)
    ("minecraft:*_fence", "minecraft:oak_fence"),
    # Signs -> oak_sign (mapped)
    ("minecraft:*_sign", "minecraft:oak_sign"),
    ("minecraft:*_wall_sign", "minecraft:oak_wall_sign"),
    ("minecraft:*_hanging_sign", "minecraft:oak_sign"),
    ("minecraft:*_wall_hanging_sign", "minecraft:oak_wall_sign"),
    # Doors -> oak_door (mapped)
    ("minecraft:*_door", "minecraft:oak_door"),
    # Trapdoors -> oak_trapdoor (mapped)
    ("minecraft:*_trapdoor", "minecraft:oak_trapdoor"),
    # Buttons -> stone_button (mapped via 0, fallback)
    ("minecraft:*_button", "minecraft:stone_button"),
    # Pressure plates -> stone_pressure_plate (unmapped, -> stone)
    ("minecraft:*_pressure_plate", "minecraft:stone"),
    # Slabs -> stone_slab (mapped)
    ("minecraft:*_slab", "minecraft:stone_slab"),
    ("minecraft:*_stairs", "minecraft:cobblestone_stairs"),
    # Carpet -> carpet (mapped for colors)
    ("minecraft:*_carpet", "minecraft:red_carpet"),
    # Shulker boxes -> chest
    ("minecraft:*_shulker_box", "minecraft:chest"),
    # Banners -> air (no legacy equivalent; they're decorative)
    ("minecraft:*_banner", "minecraft:air"),
    # Conduit, structure blocks
    ("minecraft:conduit", "minecraft:sea_lantern"),
    ("minecraft:structure_block", "minecraft:command_block"),
    ("minecraft:jigsaw", "minecraft:command_block"),
    ("minecraft:lightning_rod", "minecraft:iron_bars"),
    # Amethyst
    ("minecraft:amethyst_block", "minecraft:quartz_block"),
    ("minecraft:budding_amethyst", "minecraft:quartz_block"),
    ("minecraft:amethyst_cluster", "minecraft:quartz_block"),
    ("minecraft:amethyst_bud", "minecraft:quartz_block"),
    # Copper family -> iron (closest metallic block)
    ("minecraft:copper_block", "minecraft:iron_block"),
    ("minecraft:exposed_copper", "minecraft:iron_block"),
    ("minecraft:weathered_copper", "minecraft:iron_block"),
    ("minecraft:oxidized_copper", "minecraft:iron_block"),
    ("minecraft:waxed_copper_block", "minecraft:iron_block"),
    ("minecraft:*_copper", "minecraft:iron_block"),
    ("minecraft:cut_copper", "minecraft:iron_block"),
    ("minecraft:exposed_cut_copper", "minecraft:iron_block"),
    ("minecraft:weathered_cut_copper", "minecraft:iron_block"),
    ("minecraft:oxidized_cut_copper", "minecraft:iron_block"),
    # Dripstone / pointed dripstone -> stone
    ("minecraft:dripstone_block", "minecraft:stone"),
    ("minecraft:pointed_dripstone", "minecraft:stone"),
    ("minecraft:moss_block", "minecraft:mossy_cobblestone"),
    ("minecraft:spore_blossom", "minecraft:air"),
    ("minecraft:azalea", "minecraft:oak_leaves"),
    ("minecraft:flowering_azalea", "minecraft:oak_leaves"),
    ("minecraft:azalea_leaves", "minecraft:oak_leaves"),
    ("minecraft:flowering_azalea_leaves", "minecraft:oak_leaves"),
    ("minecraft:big_dripleaf", "minecraft:oak_leaves"),
    ("minecraft:small_dripleaf", "minecraft:fern"),
    ("minecraft:hanging_roots", "minecraft:vine"),
    ("minecraft:rooted_dirt", "minecraft:dirt"),
    ("minecraft:muddy_mangrove_roots", "minecraft:dirt"),
    # Mangrove family -> oak equivalents
    ("minecraft:mangrove_log", "minecraft:oak_log"),
    ("minecraft:mangrove_planks", "minecraft:oak_planks"),
    ("minecraft:mangrove_leaves", "minecraft:oak_leaves"),
    ("minecraft:mangrove_roots", "minecraft:oak_roots"),
    ("minecraft:mangrove_propagule", "minecraft:oak_sapling"),
    # Cherry family -> oak equivalents
    ("minecraft:cherry_log", "minecraft:oak_log"),
    ("minecraft:cherry_planks", "minecraft:oak_planks"),
    ("minecraft:cherry_leaves", "minecraft:oak_leaves"),
    ("minecraft:cherry_sapling", "minecraft:oak_sapling"),
    # Bamboo
    ("minecraft:bamboo_block", "minecraft:oak_log"),
    ("minecraft:bamboo_planks", "minecraft:oak_planks"),
    ("minecraft:bamboo_mosaic", "minecraft:oak_planks"),
    # Mud bricks
    ("minecraft:mud_bricks", "minecraft:bricks"),
    ("minecraft:mud_brick_stairs", "minecraft:stone_brick_stairs"),
    ("minecraft:mud_brick_slab", "minecraft:stone_slab"),
    ("minecraft:mud", "minecraft:dirt"),
    ("minecraft:packed_mud", "minecraft:bricks"),
    # Frosted ice / blue ice
    ("minecraft:blue_ice", "minecraft:packed_ice"),
    ("minecraft:frosted_ice", "minecraft:ice"),
    # Nether wood families -> oak
    ("minecraft:crimson_stem", "minecraft:oak_log"),
    ("minecraft:warped_stem", "minecraft:oak_log"),
    ("minecraft:crimson_planks", "minecraft:oak_planks"),
    ("minecraft:warped_planks", "minecraft:oak_planks"),
    ("minecraft:crimson_hyphae", "minecraft:oak_log"),
    ("minecraft:warped_hyphae", "minecraft:oak_log"),
    ("minecraft:crimson_nylium", "minecraft:netherrack"),
    ("minecraft:warped_nylium", "minecraft:netherrack"),
    ("minecraft:crimson_roots", "minecraft:fern"),
    ("minecraft:warped_roots", "minecraft:fern"),
    ("minecraft:weeping_vines", "minecraft:vine"),
    ("minecraft:twisting_vines", "minecraft:vine"),
    ("minecraft:shroomlight", "minecraft:glowstone"),
    ("minecraft:crimson_fungus", "minecraft:red_mushroom"),
    ("minecraft:warped_fungus", "minecraft:brown_mushroom"),
    # 1.20+ blocks
    ("minecraft:bamboo", "minecraft:oak_log"),
    ("minecraft:cherry_sign", "minecraft:oak_sign"),
    ("minecraft:cherry_wall_sign", "minecraft:oak_wall_sign"),
    ("minecraft:cherry_hanging_sign", "minecraft:oak_sign"),
    ("minecraft:bamboo_sign", "minecraft:oak_sign"),
    ("minecraft:bamboo_wall_sign", "minecraft:oak_wall_sign"),
    ("minecraft:bamboo_hanging_sign", "minecraft:oak_sign"),
    ("minecraft:mangrove_sign", "minecraft:oak_sign"),
    ("minecraft:mangrove_wall_sign", "minecraft:oak_wall_sign"),
    ("minecraft:mangrove_hanging_sign", "minecraft:oak_sign"),
    # Decorative pots
    ("minecraft:decorated_pot", "minecraft:flower_pot"),
    # Sniffer / archeology
    ("minecraft:suspicious_sand", "minecraft:sand"),
    ("minecraft:suspicious_gravel", "minecraft:gravel"),
    ("minecraft:brush", "minecraft:stick"),
    # 1.21 blocks
    ("minecraft:tuff_bricks", "minecraft:stone_bricks"),
    ("minecraft:polished_tuff", "minecraft:smooth_stone"),
    ("minecraft:tuff_brick_stairs", "minecraft:stone_brick_stairs"),
    ("minecraft:tuff_brick_slab", "minecraft:stone_slab"),
    ("minecraft:tuff_brick_wall", "minecraft:cobblestone_wall"),
    ("minecraft:chiseled_tuff", "minecraft:chiseled_stone_bricks"),
    ("minecraft:chiseled_tuff_bricks", "minecraft:chiseled_stone_bricks"),
    ("minecraft:crafter", "minecraft:crafting_table"),
    ("minecraft:trial_spawner", "minecraft:spawner"),
    ("minecraft:vault", "minecraft:chest"),
    ("minecraft:copper_bulb", "minecraft:redstone_lamp"),
    ("minecraft:copper_grate", "minecraft:iron_block"),
    ("minecraft:copper_door", "minecraft:iron_door"),
    ("minecraft:copper_trapdoor", "minecraft:iron_trapdoor"),
    # Fallback for any remaining unmapped
    ("minecraft:*", "minecraft:stone"),
]


def _has_legacy_mapping(blockstate_str: str) -> bool:
    """Check if a blockstate string resolves to a non-air legacy ID."""
    return _resolve_id(blockstate_str, DEFAULT_LEGACY_IDS) != 0


def _match_substitution(block_name: str) -> str | None:
    """Find the best substitution for a block name from the table."""
    for pattern, substitute in _SUBSTITUTION_TABLE:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if block_name.startswith(prefix):
                return substitute
        elif pattern.startswith("*"):
            suffix = pattern[1:]
            if block_name.endswith(suffix):
                return substitute
        elif pattern == block_name:
            return substitute
    return None


def suggest_substitutions(grid: Grid) -> dict[str, str]:
    """Suggest legacy-compatible substitutes for unmapped palette blocks.

    Returns a dict ``{blockstate_str: substitute_blockstate_str}`` for each
    non-air palette entry that would become air in a MCEdit export. The
    substitute is chosen from the substitution knowledge base and is guaranteed
    to have a legacy ID mapping (or air if no good substitute exists).
    """
    subs: dict[str, str] = {}
    for b in grid.palette.blocks():
        bs = b.to_blockstate_str()
        if b.name == "minecraft:air":
            continue
        if _has_legacy_mapping(bs):
            continue
        # This block is unmapped; find a substitute.
        sub_name = _match_substitution(b.name)
        if sub_name is None:
            sub_name = "minecraft:stone"
        # Verify the substitute has a mapping. If not, try stone.
        if not _has_legacy_mapping(sub_name):
            sub_name = "minecraft:stone"
        if not _has_legacy_mapping(sub_name):
            sub_name = "minecraft:air"
        subs[bs] = sub_name
    return subs


def apply_substitutions(grid: Grid, *,
                        subs: dict[str, str] | None = None) -> int:
    """Replace unmapped blocks with their suggested substitutes on the grid.

    If ``subs`` is None, calls ``suggest_substitutions(grid)`` first.
    Returns the number of voxels substituted.
    """
    if subs is None:
        subs = suggest_substitutions(grid)
    if not subs:
        return 0
    # Build a remap LUT from source palette index -> substitute palette index.
    src_to_dst: dict[int, int] = {}
    for src_bs, dst_bs in subs.items():
        src_b = Block.parse(src_bs)
        dst_b = Block.parse(dst_bs)
        src_idx = grid.palette.index_of(src_b)
        if src_idx is None:
            continue
        dst_idx = grid.palette.add(dst_b)
        src_to_dst[src_idx] = dst_idx
    if not src_to_dst:
        return 0
    palette_size = len(grid.palette)
    lut = np.arange(
        max(palette_size, max(src_to_dst.keys()) + 1, max(src_to_dst.values()) + 1),
        dtype=np.uint16,
    )
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


def substitution_report(grid: Grid) -> dict[str, Any]:
    """Return a detailed report of what substitutions would be made.

    Returns a dict with:
    - ``unmapped_count``: number of distinct unmapped blockstates.
    - ``substitutions``: dict of {block: substitute}.
    - ``mapped_count``: number of distinct palette entries with legacy mappings.
    - ``total_blocks``: total distinct palette entries (excluding air).
    """
    from typing import Any
    blocks = grid.palette.blocks()
    non_air = [b for b in blocks if b.name != "minecraft:air"]
    subs = suggest_substitutions(grid)
    mapped = [b.to_blockstate_str() for b in non_air if _has_legacy_mapping(b.to_blockstate_str())]
    return {
        "unmapped_count": len(subs),
        "substitutions": subs,
        "mapped_count": len(mapped),
        "total_blocks": len(non_air),
    }