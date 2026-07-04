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
│   │   │   ├── primitives.py        Box, Sphere, Ellipsoid, Cylinder, Cone, Pyramid, Torus, Plane, Wedge, Line, Dome, Helix, Arch, Spiral, Staircase, BezierCurve
│   │   │   ├── polygon.py           shapely Polygon extrude + SVG path d-string voxelization
│   │   │   ├── mesh.py              trimesh voxelization
│   │   │   ├── heightmap.py         Heightmap from array/image
│   │   │   ├── transforms.py        Translate, Mirror, Rotated90, Rotated (any angle), Array, NoiseDeformed, Shell
│   │   │   ├── boolean.py           Union, Intersect, Subtract, Xor
│   │   │   └── sdf.py               SDFShape, SmoothUnion, SmoothIntersect, SmoothSubtract
│   │   ├── generators/
│   │   │   ├── noise.py             Perlin/simplex (via `noise` pkg)
│   │   │   ├── templates.py         terrain, tree applicators
│   │   │   ├── replace.py            replace / replace_bulk / replace_by_name / replace_pattern
│   │   │   ├── retexture.py         blockstate property remap
│   │   │   ├── texture.py           TexturePalette (noise-driven material mix)
│   │   │   └── wfc.py               wave function collapse tilesets
│   │   ├── procedural/
│   │   │   └── detail.py            paint_gradient, edge_wear, surface_scatter
│   │   ├── analysis/
│   │   │   └── spatial.py           walkable_at, clearance_at, reachable_area, is_connected, shortest_path
│   │   ├── render/
│   │   │   └── preview.py           matplotlib voxels -> PNG (top/front/right/iso + region)
│   │   ├── export/
│   │   │   ├── sponge.py            Sponge .schem v2 writer (nbtlib)
│   │   │   ├── mcedit.py            legacy MCEdit .schematic writer
│   │   │   ├── litematic.py         Litematica .litematic writer
│   │   │   ├── report.py            palette compatibility report
│   │   │   ├── validation.py        cross-format round-trip validation
│   │   │   └── materials.py         legacy substitution suggestions + apply
│   │   ├── constraints.py           HeightLimit, BlockBan, Symmetry, BoxBounds, MaxBlockCount, PaletteLimit, SolidRatio, ConstraintSet
│   │   ├── session/
│   │   │   ├── session.py           Session orchestrator (add/subtract/paint/intersect + kwargs delegation + active symmetry + resample_subregion)
│   │   │   ├── history.py           Delta-based undo/redo
│   │   │   └── commands.py          CommandSpec table for CLI (40+ commands)
│   │   └── cli/
│   │       ├── parser.py            shlex tokenizer
│   │       ├── validation.py        Pre-execution checks (errors + warnings)
│   │       └── repl.py              REPL + --script runner
│   └── tests/                       developer test suite (320+ tests)
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
- Holds `version, grid, palette, history, metadata, registry` and an optional
  `_active_symmetry` dict used by the live mirror / radial decorators.
  Recognised modes: `{"mode":"mirror","axis":int,"center":float|None}`,
  `{"mode":"radial","plane":"xz"|"xy"|"yz","center":(a,b)|None,"folds":int}`,
  `{"mode":"quad","center":(a,b)|None}` (shorthand for radial folds=4 plane=xz).
- `new(shape, version, fill)`, `add/subtract/intersect/paint/replace`. The four
  shape-accepting methods accept `**shape_kwargs` which are forwarded to the
  shape's dataclass fields via `dataclasses.replace` — so
  `s.add(Sphere(...), "stone", hollow=True)` works without surprises. Unknown
  kwargs raise `TypeError` listing the valid fields.
- `enable_symmetry(axis, center=None)` / `disable_symmetry()`: when enabled,
  every subsequent `add`/`subtract`/`paint` is automatically unioned with its
  mirror image about `center` (grid middle by default) along `axis`. The
  `symmetry_active` property reflects state.
- `enable_radial_symmetry(folds=4, plane="xz", center=None)` /
  `enable_quad_symmetry(center=None)`: when enabled, every subsequent
  `add`/`subtract`/`paint` is unioned with its rotations about `center` in the
  named plane. For the default centre (grid middle) the rotations use the exact
  `Rotated90` transform; for an explicit offset centre an exact index-map
  rotation is used. `disable_symmetry()` turns off any active symmetry.
- `resample_subregion(frm, to, new_size, block, dest_origin=None)`: nearest-
  neighbour rescale of a sub-box to `new_size`, written at `dest_origin`.
- `transform_rotate/mirror` reshape the grid (no history delta for shape change).
- `undo/redo` via `History` (delta = changed coords + old/new values).
- `snapshot/restore` -> JSON; `save/load(path)` for `.schematica` session files.
- `marker(name, x, y, z, kind)` and `region(name, corner, size, kind)` annotate
  the build; `export_markers(path)` writes them to JSON.
- `paint_gradient`, `edge_wear`, `surface_scatter` apply organic detail to
  existing solid voxels only (never fill empty space).
- `walkable_at`, `clearance_at`, `is_connected`, `reachable_area`,
  `shortest_path` provide spatial / walkability analysis (read-only on grid).

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
Shape (mask) ──> Session.add         (with **shape_kwargs delegation)
SDFShape ──> SmoothUnion/Intersect/Subtract ──> Session.add
nbtlib ──> export.sponge / mcedit / litematic
matplotlib ──> render.preview
shapely ──> shapes.polygon          (also SVG path d-string parsing)
trimesh ──> shapes.mesh
noise ──> generators.noise
scipy (optional) ──> shapes.sdf (distance transform; pure-numpy fallback)
prompt_toolkit (optional) ──> cli.repl
```

## What is NOT in scope

- Bedrock `.mcstructure` export.
- Runtime world editing via Minecraft protocol (use minecraft-protocol skill).
- Loading/saving `.mca` region files (use amulet-core directly for that).
- GUI; the interface is library + REPL only.