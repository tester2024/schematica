# Architecture

The skill root is the directory containing `SKILL.md`. The Python toolkit lives
under `scripts/`. All paths below are relative to the skill root unless noted.

## Module layout

```
<skill-root>/
├── SKILL.md                         Skill entry (this skill)
├── .gitignore                       Ignores caches + build artifacts
├── README.md                        User-facing quickstart
├── references/                      This docs tree
├── scripts/                         Bundled toolkit (the Python package + tests)
│   ├── pyproject.toml               Deps, ruff, mypy, pytest config
│   ├── requirements.txt             Runtime deps (no extras)
│   ├── schematica/                  The importable Python package
│   │   ├── __init__.py              version
│   │   ├── __main__.py              `python -m schematica` -> repl
│   │   ├── blocks/
│   │   │   ├── block.py             Block dataclass (name + states)
│   │   │   └── registry.py          BlockRegistry (minecraft-data JSON)
│   │   ├── core/
│   │   │   ├── palette.py           Palette (deduped block list)
│   │   │   └── voxel.py             VoxelGrid (3D uint16 array)
│   │   ├── shapes/
│   │   │   ├── base.py              Shape protocol + coords_grid
│   │   │   ├── primitives.py        Box, Sphere, Ellipsoid, Cylinder, ...
│   │   │   ├── polygon.py           shapely Polygon extrude
│   │   │   ├── mesh.py              trimesh voxelization
│   │   │   ├── heightmap.py         Heightmap from array/image
│   │   │   ├── transforms.py        Translate, Mirror, Rotate90, Array, NoiseDeformed, Shell
│   │   │   └── boolean.py           Union, Intersect, Subtract, Xor
│   │   ├── generators/
│   │   │   ├── noise.py             Perlin/simplex (via `noise` pkg)
│   │   │   └── templates.py         terrain, tree applicators
│   │   ├── render/
│   │   │   └── preview.py           matplotlib voxels -> PNG
│   │   ├── export/
│   │   │   └── sponge.py            Sponge .schem v2 writer (nbtlib)
│   │   ├── session/
│   │   │   ├── session.py           Session orchestrator
│   │   │   ├── history.py           Delta-based undo/redo
│   │   │   └── commands.py          CommandSpec table for CLI
│   │   └── cli/
│   │       ├── parser.py            shlex tokenizer
│   │       ├── validation.py        Pre-execution checks (errors + warnings)
│   │       └── repl.py              REPL + --script runner
│   └── tests/                       developer test suite
└── references/                      This docs tree
    ├── architecture.md
    ├── agent_cli_guide.md
    ├── workflow_guide.md
    ├── library_api.md
    ├── cli_reference.md
    ├── shapes_catalog.md
    ├── generators.md
    ├── sponge_format.md
    ├── block_registry.md
    ├── preview_rendering.md
    └── roadmap.md
```

## Data model

### Block
- Frozen dataclass `(name: str, states: tuple[(str, object), ...])`.
- Serialized as `minecraft:name[k=v,...]` via `to_blockstate_str()`.
- `Block.parse(s)` round-trips the string form.
- `AIR = Block("minecraft:air")` singleton.

### Palette
- Ordered list of `Block`; index 0 is always air.
- `add(block) -> int` dedupes via a dict.
- `from_json(list[str])` / `to_json() -> list[str]` for session save/load.

### VoxelGrid
- `data: np.ndarray[uint16]` shape `(sx, sy, sz)`.
- `palette: Palette` shared with the grid.
- Mutators: `set, fill, apply_mask, erase_mask, paint_mask, replace`.
- Slices: `slice_x/y/z`, `subregion`.
- Transforms: `rotate(times, axes)`, `mirror(axis)`, `copy`.

### Session
- Holds `version, grid, palette, history, metadata, registry`.
- `new(shape, version, fill)`, `add/subtract/intersect/paint/replace`.
- `transform_rotate/mirror` reshape the grid (no history delta for shape change).
- `undo/redo` via `History` (delta = changed coords + old/new values).
- `snapshot/restore` -> JSON; `save/load(path)` for `.schematica` session files.

## Design choices

1. **nbtlib over amulet-core**: pure-Python, works on Python 3.14, no C++ build.
   amulet-core is an optional extra for 3.11-3.13.
2. **Synchronous**: numpy + nbtlib + matplotlib are all sync; no asyncio.
3. **Shape = pure geometry**: shapes produce boolean masks, never touch blocks.
   Session combines mask + block. Makes boolean ops and reuse trivial.
4. **Delta-based history**: storing full grids per undo step is O(N³) memory;
   deltas store only changed voxels, so undo of a 3³ edit on a 32³ grid is O(27).
5. **minecraft-data via filesystem**: load `data/pc/<ver>/blocks.json` from a
   vendored submodule or env var. Falls back to a tiny built-in catalog so the
   package is always importable.
6. **Palette index 0 = air**: matches Sponge convention; all-zero grid is empty.

## Dependency graph

```
Block ──> Palette ──> VoxelGrid ──> Session
                                │
BlockRegistry ──────────────────┘
Shape (mask) ──> Session.add
nbtlib ──> export.sponge
matplotlib ──> render.preview
shapely ──> shapes.polygon
trimesh ──> shapes.mesh
noise ──> generators.noise
prompt_toolkit (optional) ──> cli.repl
```

## What is NOT in scope

- Bedrock `.mcstructure` export.
- Runtime world editing via Minecraft protocol (use minecraft-protocol skill).
- Loading/saving `.mca` region files (use amulet-core directly for that).
- GUI; the interface is library + REPL only.