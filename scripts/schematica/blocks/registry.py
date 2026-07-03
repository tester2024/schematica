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


_FALLBACK_BLOCKS: list[dict[str, object]] = [
    {"id": 0, "name": "minecraft:air", "displayName": "Air"},
    {"id": 1, "name": "minecraft:stone", "displayName": "Stone"},
    {"id": 2, "name": "minecraft:grass_block", "displayName": "Grass Block"},
    {"id": 3, "name": "minecraft:dirt", "displayName": "Dirt"},
    {"id": 4, "name": "minecraft:cobblestone", "displayName": "Cobblestone"},
    {"id": 5, "name": "minecraft:oak_planks", "displayName": "Oak Planks"},
    {"id": 7, "name": "minecraft:bedrock", "displayName": "Bedrock"},
    {"id": 12, "name": "minecraft:sand", "displayName": "Sand"},
    {"id": 17, "name": "minecraft:oak_log", "displayName": "Oak Log",
     "states": [{"name": "axis", "type": "enum", "values": ["x", "y", "z"], "default": "y"}]},
    {"id": 20, "name": "minecraft:glass", "displayName": "Glass"},
    {"id": 45, "name": "minecraft:bricks", "displayName": "Bricks"},
    {"id": 49, "name": "minecraft:obsidian", "displayName": "Obsidian"},
    {"id": 54, "name": "minecraft:oak_fence", "displayName": "Oak Fence"},
    {"id": 89, "name": "minecraft:glowstone", "displayName": "Glowstone"},
    {"id": 121, "name": "minecraft:end_stone", "displayName": "End Stone"},
    {"id": 155, "name": "minecraft:quartz_block", "displayName": "Block of Quartz"},
    {"id": 160, "name": "minecraft:purple_stained_glass", "displayName": "Purple Stained Glass"},
    {"id": 162, "name": "minecraft:prismarine", "displayName": "Prismarine"},
    {"id": 168, "name": "minecraft:sea_lantern", "displayName": "Sea Lantern"},
    {"id": 173, "name": "minecraft:red_sand", "displayName": "Red Sand"},
    {"id": 174, "name": "minecraft:packed_ice", "displayName": "Packed Ice"},
    {"id": 18, "name": "minecraft:oak_leaves", "displayName": "Oak Leaves"},
    {"id": 98, "name": "minecraft:stone_bricks", "displayName": "Stone Bricks"},
    {"id": 109, "name": "minecraft:stone_brick_stairs", "displayName": "Stone Brick Stairs"},
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
    {"id": 1, "name": "minecraft:oak_stairs", "displayName": "Oak Stairs"},
    {"id": 1, "name": "minecraft:spruce_log", "displayName": "Spruce Log"},
    {"id": 1, "name": "minecraft:birch_log", "displayName": "Birch Log"},
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
    {"id": 1, "name": "minecraft:purpur_pillar", "displayName": "Purpur Pillar"},
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
        known = {s.name for s in bd.states}
        for k, _ in block.states:
            if k not in known:
                raise ValueError(
                    f"Block {block.name} has no state '{k}' in version {self.version}"
                )
        return block

    def resolve(self, block: Block) -> Block:
        """Validate and fill defaults: returns a Block with all states explicit."""
        bd = self[block.name]
        if not bd.states:
            return Block(name=bd.name)
        explicit = dict(block.states)
        for s in bd.states:
            if s.name not in explicit:
                if s.default is None:
                    raise ValueError(
                        f"Block {bd.name} requires state '{s.name}' "
                        f"(no default) for version {self.version}"
                    )
                explicit[s.name] = s.default
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
