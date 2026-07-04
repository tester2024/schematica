# Block registry

## Sources of block data

1. **Vendored minecraft-data repo** (preferred for full vanilla catalogs).
   From the skill/repo root (the directory containing `SKILL.md`):
   ```
   git clone https://github.com/PrismarineJS/minecraft-data minecraft_data
   ```
   Then `BlockRegistry.for_version("1.20.1")` loads
   `minecraft_data/data/pc/1.20.1/blocks.json` (relative to the skill root).

2. **`SCHEMATICA_MINECRAFT_DATA` env var**: point to any minecraft-data clone.
   `BlockRegistry.for_version` checks this env var first.

3. **Built-in fallback catalog** (when neither of the above exists): a compact
   hardcoded list in `scripts/schematica/blocks/registry.py::_FALLBACK_BLOCKS`.
   Always importable; never throws on missing data.

The default loader checks `SCHEMATICA_MINECRAFT_DATA`, then
`<skill_root>/minecraft_data`, then `scripts/minecraft_data`.

## Block JSON shape (PrismarineJS)

Each entry in `data/pc/<version>/blocks.json`:
```json
{
  "id": 1,
  "name": "minecraft:stone",
  "displayName": "Stone",
  "states": [
    {"name": "axis", "type": "enum", "values": ["x","y","z"], "default": "y"}
  ]
}
```
Pre-1.13: numeric `id` + `variants`. 1.13+: `states` array, `id` is just a
sequential index (not the runtime blockstate id).

## BlockRegistry API

```python
from schematica.blocks.registry import BlockRegistry

reg = BlockRegistry.for_version("1.20.1")   # cached
reg["minecraft:stone"]        # BlockDef
reg["stone"]                  # same BlockDef; minecraft: is auto-normalized
reg.by_id(1)                  # BlockDef by numeric id
"minecraft:oak_log" in reg   # True
reg.validate(Block.parse("minecraft:oak_log[axis=y]"))   # raises on bad state
reg.resolve(Block.parse("minecraft:oak_log"))             # fills defaults -> axis=y
reg.search("oak")             # list[BlockDef] matching name/displayName
reg.all()                     # full catalog
BlockRegistry.list_versions()  # ["1.20.1", "1.21", ...] if minecraft_data vendored
```

## BlockDef / BlockStateSchema

```python
@dataclass(frozen=True)
class BlockStateSchema:
    name: str
    type: str            # "enum", "bool", "int"
    default: object
    values: tuple[object, ...]

@dataclass(frozen=True)
class BlockDef:
    id: int
    name: str
    display_name: str
    states: tuple[BlockStateSchema, ...]

    def default_block(self) -> Block: ...   # Block with default states filled
```

## Blockstate strings

Canonical serialization: `minecraft:name[k1=v1,k2=v2]`. Booleans render as
`true`/`false`. Insertion order of states is sorted for deterministic output.

```python
Block("minecraft:oak_log", (("axis", "y"),)).to_blockstate_str()
# "minecraft:oak_log[axis=y]"
Block("minecraft:stairs", (("facing", "north"), ("half", "top"))).to_blockstate_str()
# "minecraft:stairs[facing=north,half=top]"
Block.parse("minecraft:powered_rail[powered=true]").states
# (("powered", True),)
```

Names from minecraft-data are normalized to lowercase `minecraft:`-prefixed
forms on load. This matters for pre-1.13 catalogs whose JSON may use names like
`"wool"`; `reg["wool"]`, `reg["minecraft:wool"]`, and entries from `reg.all()`
now agree on `minecraft:wool`.

## Fallback catalog blocks

The fallback catalog includes common structural blocks such as `air`, `stone`,
`grass_block`, `dirt`, `cobblestone`, `oak_planks`, `bedrock`, `sand`,
`oak_log`, `glass`, `bricks`, `obsidian`, `oak_fence`, `glowstone`,
`end_stone`, `quartz_block`, `prismarine`, `sea_lantern`, `red_sand`, and
`packed_ice`. It also includes all 16 colors for wool, stained glass,
terracotta, and concrete so common team-color builds work offline.

Common resource and mapmaking blocks are also available offline: iron/gold/
diamond/emerald/coal/lapis/redstone blocks, beacon, chest, ender chest, ladder,
doors, trapdoors, slabs, stairs, fences, fence gates, walls, glass panes, beds,
carpets, barrier, torch, lantern, chain, signs, anvil, crafting table, and
furnace.

Fallback mode now carries compact schemas for common stateful blocks such as
logs, stairs, slabs, fences, walls, doors, trapdoors, beds, chests, panes,
furnaces, lanterns, signs, and waterlogged variants. For full fidelity across
every vanilla block and version-specific state, still vendor the minecraft-data
repo.

`BlockRegistry.resolve(block, strict=True)` rejects unknown explicit state keys,
invalid enum/bool/int values, repeated keys, and states on blocks with no known
schema. Pass `strict=False` only for compatibility with already-trusted palette
data.

Fallback `by_id()` values are unique so later entries cannot overwrite earlier
ones, but synthetic ids are used where no reliable legacy id is known. Use
`by_id()` for known vanilla ids only; prefer name lookup for new code.

## Version selection

- `BlockRegistry.for_version("1.20.1")` — cache keyed on `(version, data_root)`.
- `BlockRegistry.list_versions()` returns sorted version dirs found under
  `data_root/data/pc/` that contain `blocks.json`.
- The fallback catalog is used regardless of the requested version if no JSON
  file is found — so `for_version("1.21")` works offline but yields the same
  fallback blocks (the version string is stored on the registry but doesn't
  change block availability).

## Cross-version palette building

Sponge palette entries are blockstate strings, which are version-agnostic at
the file level. The `BlockRegistry`'s role is **validation** before writing:
ensure every block the agent emits exists in the target version. Without
vendored data, validation uses the fallback list and will reject unknown
blocks; with vendored data, it accepts the full vanilla set for that version.

For pre-1.13 targets, remember that Minecraft used numeric IDs plus metadata.
The registry can validate names, but it does not synthesize every legacy
metadata variant into a modern-style blockstate. Use `write_mcedit` for legacy
colored blocks when targeting 1.7-1.12 workflows.
