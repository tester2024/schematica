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
| `clone.translate` | `frm=A to=B offset=dx,dy,dz count=N` | repeat a source box |
| `clone.cardinal` | `frm=A to=B center=x,z` | copy a quadrant/corner to the other 3 rotations |
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
Wedge, Line, Dome, Helix, Arch, Spiral, Staircase, BezierCurve` (16 shapes).

Cylinder, Cone, and Dome accept an `axis` argument (`"x"|"y"|"z"`) so horizontal
cones / wall-mounted domes are one-liners; `Cylinder` also accepts `start`/`end`
aliases for the along-axis extent (clearer than `y0`/`y1` for non-Y axes). `Arch`
accepts a `plane` argument (`"xy"|"xz"|"yz"`) so an arch can lie in any
coordinate plane.

Boolean: `Union, Intersect, Subtract, Xor`.

SDF smooth blending: `SDFShape, SmoothUnion, SmoothIntersect, SmoothSubtract`
(signed-distance-field composition with a `k`-voxel blend radius; `k=0` is the
hard boolean op). Uses scipy when available, pure-numpy fallback otherwise.

Polygon (shapely + SVG): `Extrude` a 2D polygon into a prism along x/y/z. Load
from WKT, GeoJSON, a `.json` file, or an SVG path `d`-string
(e.g. `"M 0 0 H 10 V 10 H 0 Z"` — supports `M`/`L`/`H`/`V`/`C`/`Q`/`Z`).

Mesh (trimesh): `MeshShape` voxelizes any OBJ/STL/glTF into the grid.

Heightmap: `Heightmap` from a 2D array or `from_image(path)`.

Transforms: `Translated, Mirror, Rotated90, Rotated` (any angle, not just 90°),
`Array` (repeat), `NoiseDeformed, Shell`.

## Session features

- `add` / `subtract` / `intersect` / `paint` forward `**shape_kwargs` to the
  shape's dataclass fields via `dataclasses.replace` — so
  `s.add(Sphere(...), "stone", hollow=True)` works. Unknown kwargs raise
  `TypeError` listing the valid fields.
- `enable_symmetry(axis, center=None)` / `disable_symmetry()`: live mirror
  decorator. When enabled, every subsequent add/subtract/paint is automatically
  unioned with its mirror image about `center` (grid middle by default) along
  `axis`. `symmetry_active` is a read-only property.
- `enable_radial_symmetry(folds=4, plane="xz", center=None)` /
  `enable_quad_symmetry(center=None)`: live rotational cloning. Every
  subsequent add/subtract/paint is unioned with its rotations about `center`
  (grid middle by default) in the named plane. `folds=4` → quad, `folds=8` →
  octo, `folds=2` → half-turn. Uses the exact `Rotated90` transform for the
  default centre; falls back to an exact index-map rotation for offset centres.
- `resample_subregion(frm, to, new_size, block, dest_origin=None)`: nearest-
  neighbour rescale of a sub-box to `new_size`, written at `dest_origin`.
- `set_box` / `set_many`: fast bulk write paths for procedural detail.
- `undo` / `redo` (delta-based history), `save` / `load` session JSON.
- `marker(name, x, y, z, kind)` / `region(name, corner, size, kind)` /
  `export_markers(path)` for annotations.
- `paint_gradient`, `edge_wear`, `surface_scatter` for organic detail.
- `walkable_at`, `clearance_at`, `is_connected`, `reachable_area`,
  `shortest_path` for spatial / walkability analysis.

## Generators

- `terrain_heightmap(shape, seed, amplitude, scale)` — Perlin-based surface.
- `apply_terrain(session, ...)` — fills stone+dirt+grass top layer.
- `apply_tree(session, x, z, height)` — trunk + leaf canopy.
- `generate.wfc` — wave function collapse from a caller-provided block palette.
- `texture.palette` — noise-driven material mix on existing solids.

## Architecture

```
scripts/
  schematica/
    blocks/      Block, BlockRegistry (minecraft-data JSON + enriched fallback)
    core/        VoxelGrid, Palette, ChunkedGrid (sparse big-map backend)
    shapes/      primitives, polygon (shapely+SVG), mesh, heightmap,
                 transforms, boolean, sdf (smooth blending)
    generators/  noise, templates, replace, retexture, texture, wfc
    procedural/  detail (gradient / edge wear / surface scatter)
    analysis/    spatial (walkability / pathfinding)
    render/      matplotlib voxel preview -> PNG
    export/      Sponge .schem, MCEdit .schematic, Litematica .litematic,
                 report, validation, materials
    constraints.py  declarative build constraints
    session/     Session, History, Commands (40+ commands)
    cli/         REPL, parser, validation
  tests/         developer test suite (320+ tests)
references/       docs loaded on demand
```

## Developer notes

### Internal conventions

- **Sponge block ordering**: `index = (y*length + z)*width + x`, varint-encoded.
- **History**: deltas store only changed voxels (coords + old/new), so undo of
  a 32³ grid where a 3³ box was added touches only 27 voxels.
- **Preview color map**: hand-picked for common blocks; others hashed from name.
  Edit `scripts/schematica/render/preview.py::_BLOCK_COLORS` to extend.
- **Bulk procedural writes**: use `Session.set_box(...)` and `Session.set_many(...)`
  for high-volume generated detail instead of thousands of tiny shape masks.
- **Determinism**: all procedural generators take a `seed`; pin it in tests.
- **Kwargs delegation**: `Session.add/subtract/paint/intersect` forward
  `**shape_kwargs` to the shape via `dataclasses.replace`. Unknown kwargs
  raise `TypeError` with a clear list of valid fields.
- **Active symmetry**: `enable_symmetry` wraps each shape in a
  `Union((shape, Translated(Mirror(shape), ...)))` automatically; the wrapper
  is rebuilt on every op so the mirror follows the current grid shape.
- **SDF distance transform**: `schematica.shapes.sdf._mask_to_sdf` uses
  `scipy.ndimage.distance_transform_edt` when available; otherwise a pure-numpy
  iterative-erosion BFS. Fully-filled masks get a constant negative distance
  so `SmoothSubtract` on a fully-filled box doesn't hang.

### Failure modes to watch

- **Python 3.14 + amulet-core**: amulet-core's C++ extensions may lack wheels on
  very new Python. The default backend is `nbtlib` (pure Python) which works on
  3.11-3.14. Install `amulet-core` only on 3.11-3.13.
- **Large grids**: matplotlib 3D voxel preview is comfortable around ~32³.
  Larger dense grids automatically use downsampled 2D projected previews;
  chunked grids render projected previews without materialising dense arrays.
  Projected fallback `iso` writes `preview_iso_projected.png`.
- **Backslashes in REPL scripts**: shlex treats `\` as escape. Use forward
  slashes in `path=` arguments, or quote the whole path.
- **minecraft-data submodule missing**: the registry falls back to a compact
  built-in block list with common structural, resource, mapmaking, colored, and
  stateful detail blocks, plus the Phase 12 quartz family, concrete slabs/stairs
  for all 16 colors, and ~40 stone-variant slabs/stairs (deepslate, tuff,
  calcite, blackstone, prismarine, end stone brick, mossy stone brick/cobble-
  stone, granite, diorite, andesite, polished deepslate). Validate full-fidelity
  builds against a vendored `minecraft_data/`.
- **Legacy versions**: for 1.7-1.12 colored blocks, prefer MCEdit `.schematic`.
  Sponge export warns when a pre-1.13 `data_version` is paired with modern
  flattened blockstate names. MCEdit export warns when a non-air block has no
  legacy ID mapping; use `strict=True` to fail instead.

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
python -m mypy schematica
```

The suite has 320+ tests covering shapes, boolean ops, transforms, SDF smooth
blending, Bezier curves, SVG path voxelization, active symmetry, subregion
resampling, session history, chunked backend, export round-trips for all three
formats, spatial analysis, constraints, and CLI dispatch.

## License

MIT
