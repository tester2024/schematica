# Schematica

Python toolkit and interactive REPL for building Minecraft Java Edition
schematics, packaged as an AI skill. Compose geometry primitives, shapely
polygons, trimesh meshes, heightmaps, boolean ops, and procedural generators
into structures, with session-based editing (undo/redo), multi-view PNG
previews, and Sponge `.schem`, MCEdit `.schematic`, and Litematica `.litematic`
export. The AI agent is the creative driver: it uses this toolkit to realize
the user's request.

## Install

The toolkit lives under `scripts/`. Install from there:

```bash
cd scripts
pip install -e .[dev]
```

Or runtime deps only:

```bash
pip install -r scripts/requirements.txt
```

For minecraft-data block catalogs, vendor the PrismarineJS repo at the repo or
skill root, or point `SCHEMATICA_MINECRAFT_DATA` at any clone:

```bash
git clone https://github.com/PrismarineJS/minecraft-data minecraft_data
```

Without it, a built-in fallback block list is used. The fallback covers common
structural blocks plus colored wool, stained glass, terracotta, and concrete,
but it is not a full per-version catalog.

## Quick start (library)

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere, Cylinder

s = Session.new((32, 32, 32), version="1.20.1")
s.add(Box(0, 0, 0, 31, 0, 31), "minecraft:stone")          # floor
s.add(Box(2, 1, 2, 6, 5, 6), "minecraft:oak_planks")      # hut walls
s.add(Sphere(16, 18, 16, 6), "minecraft:glass")           # dome
s.subtract(Cylinder(16, 1, 16, 2, 0, 20))                 # carve a shaft
s.replace("minecraft:stone", "minecraft:polished_andesite")

from schematica.export.sponge import write_sponge
write_sponge(s.grid, "build.schem")

from schematica.render.preview import preview
preview(s.grid, "previews")  # writes top/front/right/iso PNGs
```

## Quick start (REPL)

Set `PYTHONPATH=scripts` (or `pip install -e scripts/` first):

```bash
python -m schematica
```

Or run a script non-interactively:

```bash
python -m schematica --script build.txt
```

Example script:

```
session.new size=24x24x24 version=1.20.1
add.box frm=0,0,0 to=23,0,23 block=minecraft:stone
add.box frm=0,0,0 to=23,8,23 block=minecraft:dirt
replace src=minecraft:dirt dst=minecraft:grass_block
add.sphere center=12,14,12 r=5 block=minecraft:glass hollow=true
add.cylinder center=12,1,12 r=1 h=8 block=minecraft:oak_log
subtract.box frm=11,9,11 to=13,12,13
stats
export path=build.schem
preview out_dir=previews
```

## Commands

| Command | Args | Notes |
|---|---|---|
| `session.new` | `size=WxHxD version=V fill=B` | start fresh |
| `add.box` | `frm=x,y,z to=x,y,z block=B hollow=true` | filled or shell |
| `add.sphere` | `center=x,y,z r=N block=B hollow=true` | |
| `add.cylinder` | `center=x,y,z r=N h=N block=B hollow=true` | vertical (y) axis |
| `subtract.box` | `frm=x,y,z to=x,y,z` | carve air |
| `replace` | `src=B dst=B` | global find/replace |
| `paint` | (mask) `block=B` | repaint existing solids |
| `fill` | `block=B` | fill entire grid |
| `clear` | | all air |
| `mirror` | `axis=x\|y\|z` | |
| `rotate` | `times=N axes=xy\|xz\|yz` | 90° increments |
| `undo` / `redo` | | history |
| `stats` | | shape/volume/solid/palette |
| `preview` | `out_dir=DIR` | top/front/right/iso PNG |
| `export` | `path=FILE.schem` | Sponge v2 |
| `export.mcedit` | `path=FILE.schematic` | legacy 1.12-era MCEdit |
| `export.litematic` | `path=FILE.litematic` | Litematica |
| `save` / `load` | `path=FILE.json` | native session |
| `help` | | list commands |
| `exit` | | quit REPL |

## Shape toolkit

Primitives: `Box, Sphere, Ellipsoid, Cylinder, Cone, Pyramid, Torus, Plane,
Wedge, Line`.

Boolean: `Union, Intersect, Subtract, Xor`.

Polygon (shapely): `Extrude` a 2D polygon into a prism along x/y/z. Load from
WKT, GeoJSON, or a `.json` file.

Mesh (trimesh): `MeshShape` voxelizes any OBJ/STL/glTF into the grid.

Heightmap: `Heightmap` from a 2D array or `from_image(path)`.

Transforms: `Translated, Mirror, Rotated90, Array` (repeat).

## Generators

- `terrain_heightmap(shape, seed, amplitude, scale)` — Perlin-based surface.
- `apply_terrain(session, ...)` — fills stone+dirt+grass top layer.
- `apply_tree(session, x, z, height)` — trunk + leaf canopy.

## Architecture

```
scripts/
  schematica/
    blocks/      Block, BlockRegistry (minecraft-data JSON)
    core/        VoxelGrid, Palette
    shapes/      primitives, polygon, mesh, heightmap, transforms, boolean
    generators/  noise, templates
    render/      matplotlib voxel preview -> PNG
    export/      Sponge .schem, MCEdit .schematic, Litematica .litematic
    session/     Session, History, Commands
    cli/         REPL, parser, validation
  tests/         developer test suite
references/       docs loaded on demand
```

## Developer notes

### Internal conventions

- **Sponge block ordering**: `index = (y*length + z)*width + x`, varint-encoded.
- **History**: deltas store only changed voxels (coords + old/new), so undo of
  a 32³ grid where a 3³ box was added touches only 27 voxels.
- **Preview color map**: hand-picked for common blocks; others hashed from name.
  Edit `scripts/schematica/render/preview.py::_BLOCK_COLORS` to extend.
- **Determinism**: all procedural generators take a `seed`; pin it in tests.

### Failure modes to watch

- **Python 3.14 + amulet-core**: amulet-core's C++ extensions may lack wheels on
  very new Python. The default backend is `nbtlib` (pure Python) which works on
  3.11-3.14. Install `amulet-core` only on 3.11-3.13.
- **Large grids**: matplotlib 3D voxel preview is comfortable around ~32³.
  Larger dense grids automatically use downsampled 2D projected previews;
  chunked grids render projected previews without materialising dense arrays.
- **Backslashes in REPL scripts**: shlex treats `\` as escape. Use forward
  slashes in `path=` arguments, or quote the whole path.
- **minecraft-data submodule missing**: the registry falls back to a small
  built-in block list. Validate real builds against a vendored `minecraft_data/`.
- **Legacy versions**: for 1.7-1.12 colored blocks, prefer MCEdit `.schematic`.
  Sponge export warns when a pre-1.13 `data_version` is paired with modern
  flattened blockstate names.

### Extending the toolkit

- **Add a shape**: implement the `Shape` protocol (`def mask(shape) -> ndarray`)
  in a new file under `scripts/schematica/shapes/`.
- **Add a generator**: add a function in `scripts/schematica/generators/templates.py`
  that takes a `Session` and applies shapes. Pin a `seed` for determinism.
- **Add an exporter**: add `scripts/schematica/export/<format>.py` mirroring `sponge.py`.
- **Add a CLI command**: register a `CommandSpec` in `scripts/schematica/session/commands.py`
  with arg specs and a handler that calls a `Session` method.

### Testing

```bash
cd scripts
python -m pytest tests -q
python -m ruff check schematica
```

## License

MIT
