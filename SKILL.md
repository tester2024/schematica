---
name: schematica
description: "Schematica is a Python toolkit and interactive REPL for building Minecraft Java Edition schematics, exposed as an AI skill. Use this skill when the user asks to build, generate, design, or export Minecraft structures, schematics, .schem files, voxel maps, or 3D builds programmatically; when the user wants a procedural or creative toolkit for Minecraft builds; when the user mentions shapes, polygons, geometry, heightmaps, meshes, sessions, previews, or Sponge schematics; or when the user wants to script Minecraft map construction from Python or a REPL with undo/redo, block palettes, and multi-view PNG previews. Also use for tasks involving minecraft-data block catalogs, blockstate validation, trimesh/shapely geometry voxelization, or Perlin terrain. The AI agent is the creative driver: it composes shapes, blocks, and generators from this toolkit to realize the user's request."
---

# Schematica - Minecraft Schematic Toolkit (AI Skill)

## Purpose

Schematica is a Python 3.11+ toolkit and interactive REPL for constructing
Minecraft Java Edition structures as 3D voxel grids and exporting them as
Sponge `.schem` schematic files. It is packaged as an AI skill: the agent
loading this skill becomes the creative director, composing the toolkit's
geometry primitives, shapely polygons, trimesh meshes, heightmaps, boolean
ops, transforms, and procedural generators into the build the user asked for.
A session model supports incremental appends, undo/redo, block palettes,
versioned block catalogs, and multi-view PNG previews for the agent to verify
its work.

## When to use this skill

Trigger this skill whenever the user:

- Asks to "build", "generate", "design", or "export" a Minecraft structure, schematic, `.schem`, or voxel map.
- Wants a programmatic / scripted Minecraft map builder.
- Mentions shapes: box, sphere, cylinder, dome, cone, pyramid, torus, ellipsoid, helix, arch, staircase, spiral, line, wedge, plane, polygon, mesh, heightmap.
- Mentions hollow shapes or WorldEdit-style `hsphere`/`hcyl`/`hbox` shortcuts.
- Mentions booleans (union/subtract/intersect/xor) or transforms (rotate/mirror/array/noise-deform/shell).
- Wants previews / screenshots of a build from top/front/right/iso views.
- Wants to use minecraft-data block catalogs with per-version blockstate validation.
- Asks for procedural terrain, trees, villages, or other generated structures.
- Needs a session-based workflow: "create session, append shape, undo, export".

Do **not** use this skill for Minecraft Bedrock, runtime world editing via
protocol packets, or rendering/export of `.mcstructure` (Bedrock) — only Java
Sponge `.schem` is supported on day one.

## How to use this skill

### Install the toolkit (bundled)

The skill ships the `scripts/schematica/` Python package as its bundled
toolkit, with install metadata in `scripts/pyproject.toml`. From the
`scripts/` directory, install it editable plus dev deps:

```bash
cd scripts
pip install -e ".[dev]"
```

Or install runtime deps only from `scripts/requirements.txt`:

```bash
pip install -r scripts/requirements.txt
```

Optional extra (amulet-core multi-format backend, Python 3.11-3.13 only):

```bash
cd scripts
pip install -e ".[amulet]"
```

For full per-version block catalogs (instead of the built-in fallback), vendor
the PrismarineJS minecraft-data repo into the skill root:

```bash
git clone https://github.com/PrismarineJS/minecraft-data minecraft_data
# or set SCHEMATICA_MINECRAFT_DATA env var to the repo path
```

### Two entry points

1. **Library API** — import and script directly. See `references/library_api.md`.
2. **REPL / script mode** — `python -m schematica` for interactive, or
   `python -m schematica --script build.txt` for batch. See `references/cli_reference.md`.
   Set `PYTHONPATH=scripts` (or `pip install -e scripts/`) so the package resolves.

### Choosing CLI vs code (read `references/workflow_guide.md` for detail)

**Prefer the CLI** when the build uses only registered commands (box, sphere,
cylinder, dome, helix, arch, staircase, subtract, paint, replace, etc.). The
CLI has a validation layer that catches inverted bounds, negative radii,
unknown blocks, and other common mistakes before they execute. It is the
fastest and safest path for structural builds.

**Switch to Python** when the build needs:
- Loops or conditionals (e.g. "place 20 trees at random positions")
- Procedural generation (`apply_terrain`, `apply_tree`, Perlin noise)
- Custom shapes not in the command table (fractals, WFC, `NoiseDeformed`)
- Mesh import (`load_mesh("model.obj")`)
- Polygon extrusion (`extrude_polygon(shapely_polygon, ...)`)

**Use inline `-c`** only for quick one-liners and sanity checks.

**Hybrid**: build structure in CLI → `save` session → `load` in Python for
procedural detail. This combines CLI validation with Python flexibility.

### Core workflow

1. Create a `Session` with a target grid size and MC version.
2. Append/erase shapes via `session.add(shape, block)` / `session.subtract(shape)`.
3. Replace, paint, transform, undo/redo as needed.
4. Render previews with `preview(grid, out_dir)`.
5. Export Sponge schematics with `write_sponge(grid, path)`.
6. Save/load the full session (grid + palette + history) as JSON.

### Key references

Load these on demand for detailed information:

- `references/workflow_guide.md` — **read this first before building**: CLI vs Python vs inline decision tree, advanced recipes for each mode, hybrid workflow, verification steps.
- `references/agent_cli_guide.md` — **read this if driving the CLI**: execution pattern, argument rules, real captured output, error recovery, anti-patterns, validation codes.
- `references/architecture.md` — full module layout, data model, design choices.
- `references/library_api.md` — every public class/method with examples.
- `references/cli_reference.md` — full command table and REPL usage.
- `references/shapes_catalog.md` — every shape, its args, and mask semantics.
- `references/generators.md` — procedural generator recipes (terrain, trees).
- `references/sponge_format.md` — Sponge `.schem` v2 NBT layout and encoder details.
- `references/block_registry.md` — minecraft-data loading, fallback catalog, blockstate strings.
- `references/preview_rendering.md` — matplotlib voxel renderer and per-block colors.
- `references/roadmap.md` — phases done vs remaining (WFC, litematic).

### Bundled toolkit (scripts/)

`scripts/schematica/` is the toolkit (not a reference doc). Run it; do not read
it into context unless patching. Key modules:

- `schematica.blocks` — `Block`, `BlockRegistry`, `BlockDef`, `BlockStateSchema`
- `schematica.core` — `VoxelGrid`, `Palette`
- `schematica.shapes.primitives` — `Box`, `Sphere`, `Ellipsoid`, `Cylinder`, `Cone`, `Pyramid`, `Torus`, `Dome`, `Helix`, `Arch`, `Spiral`, `Staircase`, `Plane`, `Wedge`, `Line` (15 shapes)
- `schematica.shapes.boolean` — `Union`, `Intersect`, `Subtract`, `Xor`
- `schematica.shapes.transforms` — `Translated`, `Mirror`, `Rotated90`, `Array`, `NoiseDeformed`, `Shell`
- `schematica.shapes.polygon` — `Extrude`, `extrude_polygon` (shapely-backed)
- `schematica.shapes.mesh` — `MeshShape`, `load_mesh` (trimesh-backed)
- `schematica.shapes.heightmap` — `Heightmap`, `from_image`
- `schematica.generators` — `perlin2d`, `fbm2d`, `apply_terrain`, `apply_tree`, `terrain_heightmap`
- `schematica.render.preview` — `preview` (PNG previews)
- `schematica.export.sponge` — `write_sponge` (`.schem` writer)
- `schematica.session` — `Session`, `History`, `CommandSpec` (40+ commands)
- `schematica.cli.repl` — `dispatch`, `run_script`, `repl_main`
- `schematica.cli.validation` — `CheckResult` + 29 `check_*` functions

### Concrete examples

#### Example 1 — "Build a 24x24 stone plaza with a glass dome and a log pillar"

Library:

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere, Cylinder

s = Session.new((24, 24, 24), version="1.20.1")
s.add(Box(0, 0, 0, 23, 0, 23), "minecraft:stone")
s.add(Sphere(12, 14, 12, 5), "minecraft:glass", )  # dome
s.add(Cylinder(12, 1, 12, 1.0, 0, 8), "minecraft:oak_log")
from schematica.export.sponge import write_sponge
write_sponge(s.grid, "plaza.schem")
```

REPL script (`plaza.txt`):

```
session.new size=24x24x24 version=1.20.1
add.box frm=0,0,0 to=23,0,23 block=minecraft:stone
add.sphere center=12,14,12 r=5 block=minecraft:glass
add.cylinder center=12,1,12 r=1 h=8 block=minecraft:oak_log
export path=plaza.schem
preview out_dir=previews
```

Run: `python -m schematica --script plaza.txt`

#### Example 2 — "Carve a tunnel through a hill and replace dirt with grass"

```python
s = Session.new((32, 32, 32))
from schematica.shapes.primitives import Box
from schematica.generators.templates import apply_terrain
apply_terrain(s, seed=42, amplitude=6)
s.subtract(Box(0, 8, 15, 31, 14, 17))   # horizontal tunnel
s.replace("minecraft:dirt", "minecraft:grass_block")
```

#### Example 3 — "Extrude a star polygon into a brick tower"

```python
from shapely.geometry import Polygon
from schematica.shapes.polygon import extrude_polygon
from schematica.session.session import Session

star = Polygon([(5,0),(6,3),(10,3),(7,5),(8,9),(5,7),(2,9),(3,5),(0,3),(4,3)])
shape = extrude_polygon(star, origin=(0,0,0), extrude_axis="y", length=12)
s = Session.new((12, 12, 12))
s.add(shape, "minecraft:bricks")
```

#### Example 4 — "Voxelize an OBJ model into the grid"

```python
from schematica.shapes.mesh import load_mesh
from schematica.session.session import Session
shape = load_mesh("castle.obj", origin=(0,0,0), scale=1.0)
s = Session.new((64, 64, 64))
s.add(shape, "minecraft:stone_bricks")
```

#### Example 5 — "Build a castle with hollow walls, towers, and staircase (CLI)"

```
session.new size=32x32x32
add.hbox frm=2,1,2 to=29,12,29 block=minecraft:stone
add.hcylinder center=2,1,2 r=2 h=16 block=minecraft:stone
add.hcylinder center=29,1,2 r=2 h=16 block=minecraft:stone
add.hcylinder center=2,1,29 r=2 h=16 block=minecraft:stone
add.hcylinder center=29,1,29 r=2 h=16 block=minecraft:stone
add.dome center=2,17,2 r=2 block=minecraft:purple_stained_glass
add.dome center=29,17,2 r=2 block=minecraft:purple_stained_glass
add.dome center=2,17,29 r=2 block=minecraft:purple_stained_glass
add.dome center=29,17,29 r=2 block=minecraft:purple_stained_glass
add.staircase corner=4,1,4 y1=12 step_width=2 step_depth=1 axis=x block=minecraft:oak_planks
subtract.box frm=14,1,2 to=17,5,2
add.arch center=15,6,2 z0=2 z1=2 r=3 block=minecraft:stone
stats
export path=castle.schem
preview out_dir=castle_previews
```

#### Example 6 — "Noise-deformed boulder and hollow shell (Python)"

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Sphere
from schematica.shapes.transforms import NoiseDeformed, Shell
from schematica.export.sponge import write_sponge

s = Session.new((24, 24, 24))
boulder = NoiseDeformed(Sphere(12, 12, 12, 6), amplitude=3, scale=0.15, seed=42)
s.add(boulder, "minecraft:stone")
# Add a hollow obsidian shell around it
shell = Shell(Sphere(12, 12, 12, 8), thickness=1)
s.add(shell, "minecraft:obsidian")
write_sponge(s.grid, "boulder.schem")
```

### Important conventions

- **Coordinate system**: `grid[x, y, z]` with `y` up. Shape `mask(shape)`
  returns a boolean numpy array of the target grid's shape.
- **Palette index 0 is always air**; an all-zero grid is empty.
- **Blockstate strings**: `minecraft:oak_log[axis=y]`. `Block.parse` round-trips
  them. `BlockRegistry.resolve` fills defaults; `validate` rejects unknown states.
- **No async**: the whole pipeline is synchronous (numpy + nbtlib + matplotlib).