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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .block import AIR, Block

_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)+$")


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
]


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
        id=int(raw["id"]),
        name=str(raw["name"]),
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
        self._by_name: dict[str, BlockDef] = {b.name: b for b in blocks}
        self._by_id: dict[int, BlockDef] = {b.id: b for b in blocks}

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
        key = name.lower()
        if ":" not in key:
            key = f"minecraft:{key}"
        if key not in self._by_name:
            raise KeyError(f"Unknown block '{name}' for version {self.version}")
        return self._by_name[key]

    def by_id(self, block_id: int) -> BlockDef:
        return self._by_id[block_id]

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        key = name.lower()
        if ":" not in key:
            key = f"minecraft:{key}"
        return key in self._by_name

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
    """Locate the minecraft-data tree: env var > sibling submodule > fallback."""
    import os

    env = os.environ.get("SCHEMATICA_MINECRAFT_DATA")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent.parent.parent
    cand = here / "minecraft_data"
    if cand.exists():
        return cand
    return Path()  # triggers fallback in for_version


def air() -> Block:
    return AIR
