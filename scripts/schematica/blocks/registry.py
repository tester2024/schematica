"""Block registry loading from PrismarineJS minecraft-data JSON.

The canonical source is the PrismarineJS/minecraft-data repo, laid out as
``data/pc/<version>/blocks.json``. Each entry looks like::

    {
      "id": 1,
      "name": "minecraft:stone",
      "displayName": "Stone",
      "states": [{"name":"axis","type":"enum","num_values":3,"values":["x","y","z"],"default":"y"}]
    }

This loader reads that JSON from a configurable base directory (default:
``<repo_root>/minecraft_data``). It also ships a tiny fallback catalog so the
package is importable without the submodule vendored.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from .block import AIR, Block

_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)+$")


def _normalize_name(name: str) -> str:
    key = name.strip().lower()
    if ":" not in key:
        key = f"minecraft:{key}"
    return key


@dataclass(frozen=True)
class BlockStateSchema:
    name: str
    type: str
    default: object
    values: tuple[object, ...] = ()


@dataclass(frozen=True)
class BlockDef:
    id: int
    name: str
    display_name: str
    states: tuple[BlockStateSchema, ...] = ()

    def default_block(self) -> Block:
        if not self.states:
            return Block(name=self.name)
        pairs = tuple((s.name, s.default) for s in self.states if s.default is not None)
        return Block(name=self.name, states=pairs)


_HORIZONTAL_DIRECTIONS = ["north", "south", "west", "east"]
_AXIS_STATES = [
    {"name": "axis", "type": "enum", "values": ["x", "y", "z"], "default": "y"},
]
_FACING_STATE = {
    "name": "facing", "type": "enum", "values": _HORIZONTAL_DIRECTIONS, "default": "north",
}
_WATERLOGGED_STATE = {"name": "waterlogged", "type": "bool", "default": False}
_STAIRS_STATES = [
    _FACING_STATE,
    {"name": "half", "type": "enum", "values": ["top", "bottom"], "default": "bottom"},
    {"name": "shape", "type": "enum", "values": [
        "straight", "inner_left", "inner_right", "outer_left", "outer_right",
    ], "default": "straight"},
    _WATERLOGGED_STATE,
]
_SLAB_STATES = [
    {"name": "type", "type": "enum", "values": ["top", "bottom", "double"], "default": "bottom"},
    _WATERLOGGED_STATE,
]
_FENCE_STATES = [
    {"name": "north", "type": "bool", "default": False},
    {"name": "east", "type": "bool", "default": False},
    {"name": "south", "type": "bool", "default": False},
    {"name": "west", "type": "bool", "default": False},
    _WATERLOGGED_STATE,
]
_WALL_STATES = [
    {"name": "up", "type": "bool", "default": True},
    {"name": "north", "type": "enum", "values": ["none", "low", "tall"], "default": "none"},
    {"name": "east", "type": "enum", "values": ["none", "low", "tall"], "default": "none"},
    {"name": "south", "type": "enum", "values": ["none", "low", "tall"], "default": "none"},
    {"name": "west", "type": "enum", "values": ["none", "low", "tall"], "default": "none"},
    _WATERLOGGED_STATE,
]
_FENCE_GATE_STATES = [
    _FACING_STATE,
    {"name": "in_wall", "type": "bool", "default": False},
    {"name": "open", "type": "bool", "default": False},
    {"name": "powered", "type": "bool", "default": False},
]
_TRAPDOOR_STATES = [
    _FACING_STATE,
    {"name": "half", "type": "enum", "values": ["top", "bottom"], "default": "bottom"},
    {"name": "open", "type": "bool", "default": False},
    {"name": "powered", "type": "bool", "default": False},
    _WATERLOGGED_STATE,
]
_DOOR_STATES = [
    _FACING_STATE,
    {"name": "half", "type": "enum", "values": ["lower", "upper"], "default": "lower"},
    {"name": "hinge", "type": "enum", "values": ["left", "right"], "default": "left"},
    {"name": "open", "type": "bool", "default": False},
    {"name": "powered", "type": "bool", "default": False},
]
_BED_STATES = [
    _FACING_STATE,
    {"name": "part", "type": "enum", "values": ["head", "foot"], "default": "foot"},
    {"name": "occupied", "type": "bool", "default": False},
]
_CHEST_STATES = [
    _FACING_STATE,
    {"name": "type", "type": "enum", "values": ["single", "left", "right"], "default": "single"},
    _WATERLOGGED_STATE,
]
_PANE_STATES = [
    {"name": "north", "type": "bool", "default": False},
    {"name": "east", "type": "bool", "default": False},
    {"name": "south", "type": "bool", "default": False},
    {"name": "west", "type": "bool", "default": False},
    _WATERLOGGED_STATE,
]


_FALLBACK_BLOCKS: list[dict[str, object]] = [
    {"id": 0, "name": "minecraft:air", "displayName": "Air"},
    {"id": 1, "name": "minecraft:stone", "displayName": "Stone"},
    {"id": 2, "name": "minecraft:grass_block", "displayName": "Grass Block"},
    {"id": 3, "name": "minecraft:dirt", "displayName": "Dirt"},
    {"id": 4, "name": "minecraft:cobblestone", "displayName": "Cobblestone"},
    {"id": 5, "name": "minecraft:oak_planks", "displayName": "Oak Planks"},
    {"id": 7, "name": "minecraft:bedrock", "displayName": "Bedrock"},
    {"id": 12, "name": "minecraft:sand", "displayName": "Sand"},
    {"id": 17, "name": "minecraft:oak_log", "displayName": "Oak Log", "states": _AXIS_STATES},
    {"id": 20, "name": "minecraft:glass", "displayName": "Glass"},
    {"id": 45, "name": "minecraft:bricks", "displayName": "Bricks"},
    {"id": 49, "name": "minecraft:obsidian", "displayName": "Obsidian"},
    {"id": 85, "name": "minecraft:oak_fence", "displayName": "Oak Fence", "states": _FENCE_STATES},
    {"id": 89, "name": "minecraft:glowstone", "displayName": "Glowstone"},
    {"id": 121, "name": "minecraft:end_stone", "displayName": "End Stone"},
    {"id": 155, "name": "minecraft:quartz_block", "displayName": "Block of Quartz"},
    {"id": 95, "name": "minecraft:purple_stained_glass", "displayName": "Purple Stained Glass"},
    {"id": 168, "name": "minecraft:prismarine", "displayName": "Prismarine"},
    {"id": 169, "name": "minecraft:sea_lantern", "displayName": "Sea Lantern"},
    {"id": 12, "name": "minecraft:red_sand", "displayName": "Red Sand"},
    {"id": 174, "name": "minecraft:packed_ice", "displayName": "Packed Ice"},
    {"id": 18, "name": "minecraft:oak_leaves", "displayName": "Oak Leaves"},
    {"id": 98, "name": "minecraft:stone_bricks", "displayName": "Stone Bricks"},
    {"id": 109, "name": "minecraft:stone_brick_stairs", "displayName": "Stone Brick Stairs", "states": _STAIRS_STATES},
    {"id": 48, "name": "minecraft:mossy_cobblestone", "displayName": "Mossy Cobblestone"},
    {"id": 1, "name": "minecraft:granite", "displayName": "Granite"},
    {"id": 1, "name": "minecraft:diorite", "displayName": "Diorite"},
    {"id": 1, "name": "minecraft:andesite", "displayName": "Andesite"},
    {"id": 1, "name": "minecraft:deepslate", "displayName": "Deepslate"},
    {"id": 1, "name": "minecraft:tuff", "displayName": "Tuff"},
    {"id": 1, "name": "minecraft:calcite", "displayName": "Calcite"},
    {"id": 1, "name": "minecraft:amethyst_block", "displayName": "Block of Amethyst"},
    {"id": 1, "name": "minecraft:budding_amethyst", "displayName": "Budding Amethyst"},
    {"id": 1, "name": "minecraft:smooth_stone", "displayName": "Smooth Stone"},
    {"id": 53, "name": "minecraft:oak_stairs", "displayName": "Oak Stairs", "states": _STAIRS_STATES},
    {"id": 1, "name": "minecraft:spruce_log", "displayName": "Spruce Log", "states": _AXIS_STATES},
    {"id": 1, "name": "minecraft:birch_log", "displayName": "Birch Log", "states": _AXIS_STATES},
    {"id": 1, "name": "minecraft:spruce_planks", "displayName": "Spruce Planks"},
    {"id": 1, "name": "minecraft:birch_planks", "displayName": "Birch Planks"},
    {"id": 1, "name": "minecraft:water", "displayName": "Water"},
    {"id": 1, "name": "minecraft:lava", "displayName": "Lava"},
    {"id": 1, "name": "minecraft:snow_block", "displayName": "Snow Block"},
    {"id": 1, "name": "minecraft:ice", "displayName": "Ice"},
    {"id": 1, "name": "minecraft:blue_ice", "displayName": "Blue Ice"},
    {"id": 1, "name": "minecraft:terracotta", "displayName": "Terracotta"},
    {"id": 1, "name": "minecraft:white_concrete", "displayName": "White Concrete"},
    {"id": 1, "name": "minecraft:black_concrete", "displayName": "Black Concrete"},
    {"id": 1, "name": "minecraft:red_concrete", "displayName": "Red Concrete"},
    {"id": 1, "name": "minecraft:blue_concrete", "displayName": "Blue Concrete"},
    {"id": 1, "name": "minecraft:white_wool", "displayName": "White Wool"},
    {"id": 1, "name": "minecraft:black_wool", "displayName": "Black Wool"},
    {"id": 1, "name": "minecraft:red_wool", "displayName": "Red Wool"},
    {"id": 1, "name": "minecraft:blue_wool", "displayName": "Blue Wool"},
    {"id": 1, "name": "minecraft:white_terracotta", "displayName": "White Terracotta"},
    {"id": 1, "name": "minecraft:sandstone", "displayName": "Sandstone"},
    {"id": 1, "name": "minecraft:red_sandstone", "displayName": "Red Sandstone"},
    {"id": 1, "name": "minecraft:smooth_sandstone", "displayName": "Smooth Sandstone"},
    {"id": 1, "name": "minecraft:netherrack", "displayName": "Netherrack"},
    {"id": 1, "name": "minecraft:soul_sand", "displayName": "Soul Sand"},
    {"id": 1, "name": "minecraft:soul_soil", "displayName": "Soul Soil"},
    {"id": 1, "name": "minecraft:glowstone", "displayName": "Glowstone"},
    {"id": 1, "name": "minecraft:obsidian", "displayName": "Obsidian"},
    {"id": 1, "name": "minecraft:crying_obsidian", "displayName": "Crying Obsidian"},
    {"id": 1, "name": "minecraft:nether_bricks", "displayName": "Nether Bricks"},
    {"id": 1, "name": "minecraft:blackstone", "displayName": "Blackstone"},
    {"id": 1, "name": "minecraft:basalt", "displayName": "Basalt"},
    {"id": 1, "name": "minecraft:smooth_basalt", "displayName": "Smooth Basalt"},
    {"id": 1, "name": "minecraft:end_stone_bricks", "displayName": "End Stone Bricks"},
    {"id": 1, "name": "minecraft:purpur_block", "displayName": "Purpur Block"},
    {"id": 1, "name": "minecraft:purpur_pillar", "displayName": "Purpur Pillar", "states": _AXIS_STATES},
]

_FALLBACK_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)

_FALLBACK_EXTRA_BLOCKS: list[dict[str, object]] = []
_next_fallback_id = 5000
for _family in ("wool", "stained_glass", "terracotta", "concrete"):
    for _color in _FALLBACK_COLORS:
        _display = f"{_color.replace('_', ' ').title()} {_family.replace('_', ' ').title()}"
        _FALLBACK_EXTRA_BLOCKS.append({
            "id": _next_fallback_id,
            "name": f"minecraft:{_color}_{_family}",
            "displayName": _display,
        })
        _next_fallback_id += 1

_COMMON_FALLBACK_BLOCKS: list[dict[str, object]] = [
    {"id": 42, "name": "minecraft:iron_block", "displayName": "Block of Iron"},
    {"id": 41, "name": "minecraft:gold_block", "displayName": "Block of Gold"},
    {"id": 57, "name": "minecraft:diamond_block", "displayName": "Block of Diamond"},
    {"id": 133, "name": "minecraft:emerald_block", "displayName": "Block of Emerald"},
    {"id": 173, "name": "minecraft:coal_block", "displayName": "Block of Coal"},
    {"id": 22, "name": "minecraft:lapis_block", "displayName": "Lapis Lazuli Block"},
    {"id": 152, "name": "minecraft:redstone_block", "displayName": "Block of Redstone"},
    {"id": 138, "name": "minecraft:beacon", "displayName": "Beacon"},
    {"id": 145, "name": "minecraft:anvil", "displayName": "Anvil"},
    {"id": 58, "name": "minecraft:crafting_table", "displayName": "Crafting Table"},
    {"id": 61, "name": "minecraft:furnace", "displayName": "Furnace",
     "states": [_FACING_STATE, {"name": "lit", "type": "bool", "default": False}]},
    {"id": 54, "name": "minecraft:chest", "displayName": "Chest", "states": _CHEST_STATES},
    {"id": 130, "name": "minecraft:ender_chest", "displayName": "Ender Chest",
     "states": [_FACING_STATE, _WATERLOGGED_STATE]},
    {"id": 65, "name": "minecraft:ladder", "displayName": "Ladder",
     "states": [_FACING_STATE, _WATERLOGGED_STATE]},
    {"id": 102, "name": "minecraft:glass_pane", "displayName": "Glass Pane", "states": _PANE_STATES},
    {"id": 101, "name": "minecraft:iron_bars", "displayName": "Iron Bars", "states": _PANE_STATES},
    {"id": 96, "name": "minecraft:oak_trapdoor", "displayName": "Oak Trapdoor", "states": _TRAPDOOR_STATES},
    {"id": 167, "name": "minecraft:iron_trapdoor", "displayName": "Iron Trapdoor", "states": _TRAPDOOR_STATES},
    {"id": 64, "name": "minecraft:oak_door", "displayName": "Oak Door", "states": _DOOR_STATES},
    {"id": 71, "name": "minecraft:iron_door", "displayName": "Iron Door", "states": _DOOR_STATES},
    {"id": 107, "name": "minecraft:oak_fence_gate", "displayName": "Oak Fence Gate", "states": _FENCE_GATE_STATES},
    {"id": 139, "name": "minecraft:cobblestone_wall", "displayName": "Cobblestone Wall", "states": _WALL_STATES},
    {"id": 44, "name": "minecraft:stone_slab", "displayName": "Stone Slab", "states": _SLAB_STATES},
    {"id": 126, "name": "minecraft:oak_slab", "displayName": "Oak Slab", "states": _SLAB_STATES},
    {"id": 67, "name": "minecraft:cobblestone_stairs", "displayName": "Cobblestone Stairs", "states": _STAIRS_STATES},
    {"id": 53, "name": "minecraft:oak_stairs", "displayName": "Oak Stairs", "states": _STAIRS_STATES},
    {"id": 26, "name": "minecraft:red_bed", "displayName": "Red Bed", "states": _BED_STATES},
    {"id": 166, "name": "minecraft:barrier", "displayName": "Barrier"},
    {"id": 50, "name": "minecraft:torch", "displayName": "Torch"},
    {"id": 76, "name": "minecraft:redstone_torch", "displayName": "Redstone Torch", "states": [
        {"name": "lit", "type": "bool", "default": True},
    ]},
    {"id": 123, "name": "minecraft:redstone_lamp", "displayName": "Redstone Lamp", "states": [
        {"name": "lit", "type": "bool", "default": False},
    ]},
    {"id": _next_fallback_id, "name": "minecraft:lantern", "displayName": "Lantern", "states": [
        {"name": "hanging", "type": "bool", "default": False}, _WATERLOGGED_STATE,
    ]},
    {"id": _next_fallback_id + 1, "name": "minecraft:chain", "displayName": "Chain", "states": _AXIS_STATES},
    {"id": _next_fallback_id + 2, "name": "minecraft:oak_sign", "displayName": "Oak Sign",
     "states": [{"name": "rotation", "type": "int", "default": 0, "values": list(range(16))},
                _WATERLOGGED_STATE]},
    {"id": _next_fallback_id + 3, "name": "minecraft:oak_wall_sign", "displayName": "Oak Wall Sign",
     "states": [_FACING_STATE, _WATERLOGGED_STATE]},
]

_FALLBACK_EXTRA_BLOCKS.extend(_COMMON_FALLBACK_BLOCKS)
_next_fallback_id += len(_COMMON_FALLBACK_BLOCKS)

# Quartz and smooth quartz variants (blocks, slabs, stairs) so modern builds
# don't KeyError without a vendored minecraft-data tree.
_QUARTZ_FAMILY: list[dict[str, object]] = [
    {"id": _next_fallback_id, "name": "minecraft:smooth_quartz", "displayName": "Smooth Quartz"},
    {"id": _next_fallback_id + 1, "name": "minecraft:quartz_pillar",
     "displayName": "Quartz Pillar", "states": _AXIS_STATES},
    {"id": _next_fallback_id + 2, "name": "minecraft:chiseled_quartz_block",
     "displayName": "Chiseled Quartz Block"},
    {"id": _next_fallback_id + 3, "name": "minecraft:quartz_slab",
     "displayName": "Quartz Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 4, "name": "minecraft:smooth_quartz_slab",
     "displayName": "Smooth Quartz Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 5, "name": "minecraft:quartz_stairs",
     "displayName": "Quartz Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 6, "name": "minecraft:smooth_quartz_stairs",
     "displayName": "Smooth Quartz Stairs", "states": _STAIRS_STATES},
]
_FALLBACK_EXTRA_BLOCKS.extend(_QUARTZ_FAMILY)
_next_fallback_id += len(_QUARTZ_FAMILY)

# Concrete slabs + stairs and stone-variant slabs + stairs for modern detailing.
_CONCRETE_SLAB_STAIRS: list[dict[str, object]] = []
for _color in _FALLBACK_COLORS:
    _display_color = _color.replace("_", " ").title()
    _CONCRETE_SLAB_STAIRS.append({
        "id": _next_fallback_id,
        "name": f"minecraft:{_color}_concrete_slab",
        "displayName": f"{_display_color} Concrete Slab",
        "states": _SLAB_STATES,
    })
    _next_fallback_id += 1
    _CONCRETE_SLAB_STAIRS.append({
        "id": _next_fallback_id,
        "name": f"minecraft:{_color}_concrete_stairs",
        "displayName": f"{_display_color} Concrete Stairs",
        "states": _STAIRS_STATES,
    })
    _next_fallback_id += 1
_FALLBACK_EXTRA_BLOCKS.extend(_CONCRETE_SLAB_STAIRS)

_STONE_VARIANT_SLABS_STAIRS: list[dict[str, object]] = [
    {"id": _next_fallback_id, "name": "minecraft:smooth_stone_slab",
     "displayName": "Smooth Stone Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 1, "name": "minecraft:sandstone_slab",
     "displayName": "Sandstone Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 2, "name": "minecraft:red_sandstone_slab",
     "displayName": "Red Sandstone Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 3, "name": "minecraft:nether_brick_slab",
     "displayName": "Nether Brick Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 4, "name": "minecraft:smooth_sandstone_stairs",
     "displayName": "Smooth Sandstone Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 5, "name": "minecraft:red_sandstone_stairs",
     "displayName": "Red Sandstone Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 6, "name": "minecraft:nether_brick_stairs",
     "displayName": "Nether Brick Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 7, "name": "minecraft:prismarine_slab",
     "displayName": "Prismarine Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 8, "name": "minecraft:prismarine_bricks_slab",
     "displayName": "Prismarine Bricks Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 9, "name": "minecraft:dark_prismarine_slab",
     "displayName": "Dark Prismarine Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 10, "name": "minecraft:prismarine_stairs",
     "displayName": "Prismarine Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 11, "name": "minecraft:end_stone_brick_slab",
     "displayName": "End Stone Brick Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 12, "name": "minecraft:end_stone_brick_stairs",
     "displayName": "End Stone Brick Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 13, "name": "minecraft:mossy_stone_brick_slab",
     "displayName": "Mossy Stone Brick Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 14, "name": "minecraft:mossy_stone_brick_stairs",
     "displayName": "Mossy Stone Brick Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 15, "name": "minecraft:mossy_cobblestone_slab",
     "displayName": "Mossy Cobblestone Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 16, "name": "minecraft:mossy_cobblestone_stairs",
     "displayName": "Mossy Cobblestone Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 17, "name": "minecraft:granite_slab",
     "displayName": "Granite Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 18, "name": "minecraft:granite_stairs",
     "displayName": "Granite Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 19, "name": "minecraft:polished_granite_slab",
     "displayName": "Polished Granite Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 20, "name": "minecraft:polished_granite_stairs",
     "displayName": "Polished Granite Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 21, "name": "minecraft:diorite_slab",
     "displayName": "Diorite Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 22, "name": "minecraft:diorite_stairs",
     "displayName": "Diorite Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 23, "name": "minecraft:andesite_slab",
     "displayName": "Andesite Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 24, "name": "minecraft:andesite_stairs",
     "displayName": "Andesite Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 25, "name": "minecraft:deepslate_brick_slab",
     "displayName": "Deepslate Brick Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 26, "name": "minecraft:deepslate_brick_stairs",
     "displayName": "Deepslate Brick Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 27, "name": "minecraft:deepslate_tile_slab",
     "displayName": "Deepslate Tile Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 28, "name": "minecraft:deepslate_tile_stairs",
     "displayName": "Deepslate Tile Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 29, "name": "minecraft:blackstone_slab",
     "displayName": "Blackstone Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 30, "name": "minecraft:blackstone_stairs",
     "displayName": "Blackstone Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 31, "name": "minecraft:smooth_basalt",
     "displayName": "Smooth Basalt"},
    {"id": _next_fallback_id + 32, "name": "minecraft:tuff_slab",
     "displayName": "Tuff Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 33, "name": "minecraft:tuff_stairs",
     "displayName": "Tuff Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 34, "name": "minecraft:tuff_bricks",
     "displayName": "Tuff Bricks"},
    {"id": _next_fallback_id + 35, "name": "minecraft:tuff_brick_slab",
     "displayName": "Tuff Brick Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 36, "name": "minecraft:tuff_brick_stairs",
     "displayName": "Tuff Brick Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 37, "name": "minecraft:calcite_slab",
     "displayName": "Calcite Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 38, "name": "minecraft:calcite_stairs",
     "displayName": "Calcite Stairs", "states": _STAIRS_STATES},
    {"id": _next_fallback_id + 39, "name": "minecraft:chiseled_deepslate",
     "displayName": "Chiseled Deepslate"},
    {"id": _next_fallback_id + 40, "name": "minecraft:polished_deepslate_slab",
     "displayName": "Polished Deepslate Slab", "states": _SLAB_STATES},
    {"id": _next_fallback_id + 41, "name": "minecraft:polished_deepslate_stairs",
     "displayName": "Polished Deepslate Stairs", "states": _STAIRS_STATES},
]
_FALLBACK_EXTRA_BLOCKS.extend(_STONE_VARIANT_SLABS_STAIRS)
_next_fallback_id += len(_STONE_VARIANT_SLABS_STAIRS)

for _color in _FALLBACK_COLORS:
    _display_color = _color.replace("_", " ").title()
    _FALLBACK_EXTRA_BLOCKS.append({
        "id": _next_fallback_id,
        "name": f"minecraft:{_color}_bed",
        "displayName": f"{_display_color} Bed",
        "states": _BED_STATES,
    })
    _next_fallback_id += 1
    _FALLBACK_EXTRA_BLOCKS.append({
        "id": _next_fallback_id,
        "name": f"minecraft:{_color}_carpet",
        "displayName": f"{_display_color} Carpet",
    })
    _next_fallback_id += 1
    _FALLBACK_EXTRA_BLOCKS.append({
        "id": _next_fallback_id,
        "name": f"minecraft:{_color}_stained_glass_pane",
        "displayName": f"{_display_color} Stained Glass Pane",
        "states": _PANE_STATES,
    })
    _next_fallback_id += 1

_FALLBACK_BLOCKS.extend(_FALLBACK_EXTRA_BLOCKS)


def _parse_state_schema(raw: dict[str, object]) -> BlockStateSchema:
    values_raw = raw.get("values", [])
    if isinstance(values_raw, list):
        values = tuple(values_raw)
    else:
        values = ()
    return BlockStateSchema(
        name=str(raw["name"]),
        type=str(raw.get("type", "enum")),
        default=raw.get("default"),
        values=values,
    )


def _parse_block_def(raw: dict[str, object]) -> BlockDef:
    states_raw = raw.get("states", [])
    states: tuple[BlockStateSchema, ...] = ()
    if isinstance(states_raw, list):
        states = tuple(_parse_state_schema(s) for s in states_raw if isinstance(s, dict))
    return BlockDef(
        id=int(raw["id"]),  # type: ignore[call-overload]
        name=_normalize_name(str(raw["name"])),
        display_name=str(raw.get("displayName", raw["name"])),
        states=states,
    )


def _coerce_state_value(schema: BlockStateSchema, value: object) -> object:
    if schema.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.lower()
            if low == "true":
                return True
            if low == "false":
                return False
        raise ValueError(f"state '{schema.name}' expects true or false, got {value!r}")
    if schema.type == "int":
        if isinstance(value, bool):
            raise ValueError(f"state '{schema.name}' expects an integer, got {value!r}")
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as e:
            raise ValueError(f"state '{schema.name}' expects an integer, got {value!r}") from e
    return str(value).lower() if isinstance(value, str) else value


def _validate_state_value(block_name: str, schema: BlockStateSchema, value: object,
                          version: str) -> object:
    value = _coerce_state_value(schema, value)
    if schema.values and value not in schema.values:
        allowed = ", ".join(str(v) for v in schema.values[:12])
        suffix = "..." if len(schema.values) > 12 else ""
        raise ValueError(
            f"Block {block_name} state '{schema.name}'={value!r} is invalid for "
            f"version {version}; expected one of: {allowed}{suffix}"
        )
    return value


def _validate_states(block_def: BlockDef, states: tuple[tuple[str, object], ...],
                     version: str) -> tuple[tuple[str, object], ...]:
    schemas = {s.name: s for s in block_def.states}
    validated: list[tuple[str, object]] = []
    seen: set[str] = set()
    for key, value in states:
        if key in seen:
            raise ValueError(f"Block {block_def.name} repeats state '{key}' in version {version}")
        seen.add(key)
        schema = schemas.get(key)
        if schema is None:
            if not schemas:
                raise ValueError(
                    f"Block {block_def.name} has no known states in version {version}; "
                    f"cannot accept explicit state '{key}'"
                )
            raise ValueError(
                f"Block {block_def.name} has no state '{key}' in version {version}"
            )
        validated.append((key, _validate_state_value(block_def.name, schema, value, version)))
    return tuple(validated)


class BlockRegistry:
    """Versioned block catalog.

    Usage::

        reg = BlockRegistry.for_version("1.20.1")
        reg["minecraft:stone"]  # -> BlockDef
        reg.validate(Block.parse("minecraft:oak_log[axis=y]"))
    """

    def __init__(self, version: str, blocks: list[BlockDef]) -> None:
        self.version = version
        self._by_name: dict[str, BlockDef] = {}
        self._by_id: dict[int, BlockDef] = {}
        used_ids: set[int] = set()
        next_synthetic_id = max((b.id for b in blocks), default=-1) + 1
        for block_def in blocks:
            name = _normalize_name(block_def.name)
            bd = block_def if block_def.name == name else replace(block_def, name=name)
            if name in self._by_name:
                # Prefer the first definition so fallback duplicates cannot
                # overwrite known legacy ids such as glowstone=89 or obsidian=49.
                continue
            if bd.id in used_ids:
                while next_synthetic_id in used_ids:
                    next_synthetic_id += 1
                bd = replace(bd, id=next_synthetic_id)
                next_synthetic_id += 1
            self._by_name[name] = bd
            self._by_id[bd.id] = bd
            used_ids.add(bd.id)

    @classmethod
    @lru_cache(maxsize=16)
    def for_version(cls, version: str, data_root: str | Path | None = None) -> BlockRegistry:
        root = Path(data_root) if data_root else _default_data_root()
        path = root / "data" / "pc" / version / "blocks.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                raw_list = json.load(fh)
            blocks = [_parse_block_def(r) for r in raw_list if isinstance(r, dict)]
        else:
            blocks = [_parse_block_def(r) for r in _FALLBACK_BLOCKS]
        return cls(version=version, blocks=blocks)

    def __getitem__(self, name: str) -> BlockDef:
        key = _normalize_name(name)
        if key not in self._by_name:
            raise KeyError(f"Unknown block '{name}' for version {self.version}")
        return self._by_name[key]

    def by_id(self, block_id: int) -> BlockDef:
        return self._by_id[block_id]

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return _normalize_name(name) in self._by_name

    def validate(self, block: Block) -> Block:
        bd = self[block.name]
        _validate_states(bd, block.states, self.version)
        return block

    def resolve(self, block: Block, *, strict: bool = True) -> Block:
        """Validate and fill defaults: returns a Block with all states explicit."""
        bd = self[block.name]
        if not bd.states:
            if strict:
                _validate_states(bd, block.states, self.version)
            return Block(name=bd.name)
        explicit = dict(block.states)
        if strict:
            explicit = dict(_validate_states(bd, block.states, self.version))
        for s in bd.states:
            if s.name not in explicit:
                if s.default is None:
                    raise ValueError(
                        f"Block {bd.name} requires state '{s.name}' "
                        f"(no default) for version {self.version}"
                    )
                explicit[s.name] = s.default
            elif strict:
                explicit[s.name] = _validate_state_value(bd.name, s, explicit[s.name], self.version)
        return Block(name=bd.name, states=tuple(sorted(explicit.items())))

    def search(self, query: str, limit: int = 50) -> list[BlockDef]:
        q = query.lower()
        return [b for b in self._by_name.values() if q in b.name or q in b.display_name.lower()][:limit]

    def all(self) -> list[BlockDef]:
        return list(self._by_name.values())

    @staticmethod
    def list_versions(data_root: str | Path | None = None) -> list[str]:
        root = Path(data_root) if data_root else _default_data_root()
        pc = root / "data" / "pc"
        if not pc.exists():
            return []
        out: list[str] = []
        for p in pc.iterdir():
            if p.is_dir() and _VERSION_DIR_RE.match(p.name) and (p / "blocks.json").exists():
                out.append(p.name)
        return sorted(out, key=lambda v: tuple(int(x) for x in v.split(".")))


def _default_data_root() -> Path:
    """Locate the minecraft-data tree: env var > repo/skill root > scripts dir > fallback."""
    import os

    env = os.environ.get("SCHEMATICA_MINECRAFT_DATA")
    if env:
        return Path(env)
    scripts_root = Path(__file__).resolve().parent.parent.parent
    for cand in (scripts_root.parent / "minecraft_data", scripts_root / "minecraft_data"):
        if cand.exists():
            return cand
    return Path()  # triggers fallback in for_version


def air() -> Block:
    return AIR
