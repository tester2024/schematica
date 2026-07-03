# Library API reference

All public symbols live under `schematica.*`. Import paths shown inline.

## `schematica.blocks.block`

### `Block(name, states=())`
Frozen dataclass. Accepts `"stone"` (auto-prefixed to `minecraft:stone`) or
full `"minecraft:stone"`. `states` is a tuple of `(name, value)` pairs.

```python
from schematica.blocks.block import Block, AIR

b = Block("minecraft:oak_log", (("axis", "y"),))
b.name           # "minecraft:oak_log"
b.to_blockstate_str()   # "minecraft:oak_log[axis=y]"
Block.parse("minecraft:oak_log[axis=y]") == b   # True
AIR.to_blockstate_str() # "minecraft:air"
```

Class methods:
- `Block.parse(s: str) -> Block` — parse a blockstate string.
- `Block.from_mapping(name, states: Mapping) -> Block` — sorted states.

The `AIR` singleton is pre-built.

## `schematica.blocks.registry`

### `BlockRegistry.for_version(version, data_root=None) -> BlockRegistry`
Cached. Loads `data/pc/<version>/blocks.json` from `data_root` (or env
`SCHEMATICA_MINECRAFT_DATA`, or sibling `minecraft_data/` dir, or built-in
fallback catalog).

```python
from schematica.blocks.registry import BlockRegistry
reg = BlockRegistry.for_version("1.20.1")
reg["minecraft:stone"]        # BlockDef(id, name, display_name, states)
reg.by_id(1)                  # BlockDef by numeric id
"minecraft:stone" in reg     # True
reg.validate(Block.parse("minecraft:oak_log[axis=y]"))   # raises on bad state
reg.resolve(Block.parse("minecraft:oak_log"))             # fills axis=y default
reg.search("oak")             # list[BlockDef]
reg.all()                     # list[BlockDef]
BlockRegistry.list_versions()  # ["1.20.1", "1.21", ...] if minecraft_data vendored
```

### `BlockDef(id, name, display_name, states: tuple[BlockStateSchema])`
- `bd.default_block()` — `Block` with all default states filled.

### `BlockStateSchema(name, type, default, values)`
Mirror of minecraft-data's state entries.

## `schematica.core.palette`

### `Palette()`
- `add(block) -> int` — dedupe insert, returns index.
- `index_of(block) -> int | None`.
- `__getitem__(idx) -> Block`, `__len__`, `__iter__`.
- `blocks() -> list[Block]`.
- `to_json() -> list[str]`, `from_json(list[str]) -> Palette`.
- Index 0 is always `AIR`.

## `schematica.core.voxel`

### `VoxelGrid(shape, palette=Palette(), data=None)`
- `data: np.ndarray[uint16]` shape `(sx, sy, sz)`.
- `from_array(data, palette=None)` classmethod.
- `get(x,y,z) -> Block`, `set(x,y,z, block)`.
- `fill(block)`, `fill_air()`.
- `apply_mask(mask, block)` — set all True voxels to block.
- `erase_mask(mask)` — set True voxels to air.
- `paint_mask(mask, block)` — repaint only already-solid voxels.
- `replace(src, dst) -> int` — returns count replaced (accepts str or Block).
- `count(block) -> int` (accepts str or Block).
- `nonempty_count() -> int`.
- `slice_x/y/z(i) -> np.ndarray`.
- `subregion(corner, size) -> VoxelGrid`.
- `rotate(times, axes="xy") -> VoxelGrid` (90° steps).
- `mirror(axis) -> VoxelGrid` (axis 0/1/2).
- `copy() -> VoxelGrid`.

```python
from schematica.core.voxel import VoxelGrid
g = VoxelGrid(shape=(8, 8, 8))
g.fill("minecraft:stone") if False else g.fill(Block.parse("minecraft:stone"))
g.count("minecraft:stone")   # 512
```

## `schematica.shapes.base`

### `Shape` (Protocol)
```python
class Shape(Protocol):
    def mask(self, shape: tuple[int,int,int]) -> np.ndarray: ...
```
Returns a boolean ndarray of `shape`.

### `coords_grid(shape) -> (X, Y, Z)`
Meshgrid int index arrays (indexing="ij").

### `in_bounds(coord, shape) -> bool`
Check if a single (x, y, z) coordinate is inside the grid.

## `schematica.shapes.primitives`
All are frozen dataclasses implementing `Shape`.

- `Box(x0,y0,z0, x1,y1,z1, hollow=False, wall_thickness=1)` — inclusive bounds.
- `Sphere(cx,cy,cz, r, hollow=False, shell_thickness=1.0)`.
- `Ellipsoid(cx,cy,cz, rx,ry,rz, hollow=False, shell_thickness=1.0)`.
- `Cylinder(cx,cz, r, y0,y1, axis="y", hollow=False, shell_thickness=1.0)`.
- `Cone(cx,cz, r_base, y_base, y_apex)`.
- `Pyramid(x0,z0, base_half, y_base, y_apex)`.
- `Torus(cx,cy,cz, R, r)` — R major, r minor.
- `Dome(cx,cy,cz, r, hollow=False, shell_thickness=1.0)` — upper hemisphere (y >= cy).
- `Helix(cx,cy,cz, r, y0,y1, turns=3.0, thickness=1.0)` — spiral curve around y axis.
- `Arch(cx,cy, z0,z1, r, thickness=1.0)` — semicircular arch extruded along z.
- `Spiral(cx,cz, y0,y1, r_inner,r_outer, turns=2.0, thickness=1.0)` — flat spiral extruded vertically.
- `Staircase(x0,y0,z0, y1, step_width=3, step_depth=2, step_height=1, axis="x")` — straight stairs.
- `Plane(axis, coord, thickness=1)` — axis-aligned slab perpendicular to axis.
- `Wedge(x0,y0,z0, x1,y1,z1, split_axis="x"|"z")` — triangular prism (half a box).
- `Line(x0,y0,z0, x1,y1,z1)` — 1-voxel Bresenham line.

See `references/shapes_catalog.md` for arg semantics and examples.

## `schematica.shapes.boolean`
- `Union(shapes: tuple[Shape, ...])`.
- `Intersect(shapes: tuple[Shape, ...])`.
- `Subtract(a, b)`.
- `Xor(a, b)`.

## `schematica.shapes.transforms`
- `Translated(shape, dx, dy, dz)` — np.roll based (wraps at grid edges).
- `Mirror(shape, axis)` — axis 0/1/2.
- `Rotated90(shape, times=1, axes="xy"|"xz"|"yz")`.
- `Array(shape, count, axis, spacing)` — repeat along an axis.
- `NoiseDeformed(shape, amplitude=2, scale=0.1, seed=0)` — perturb edges with Perlin noise. Requires scipy for best results (falls back without it).
- `Shell(shape, thickness=1)` — keep only the outer N-voxel shell of any shape.

## `schematica.shapes.polygon`

### `extrude_polygon(polygon, origin=(0,0,0), extrude_axis="z", length=1) -> Extrude`
`polygon` accepts a `shapely.geometry.Polygon`, WKT string, GeoJSON dict, or
path to a `.json` GeoJSON file. The polygon's (u, v) maps to (X, Y) of the
grid; extrude along the third axis.

```python
from shapely.geometry import Polygon
from schematica.shapes.polygon import extrude_polygon
hexagon = Polygon([(2,0),(4,0),(5,2),(4,4),(2,4),(1,2)])
shape = extrude_polygon(hexagon, origin=(0,0,0), extrude_axis="z", length=8)
```

## `schematica.shapes.mesh`

### `load_mesh(path, origin=(0,0,0), scale=1.0) -> MeshShape`
Loads OBJ/STL/glTF via trimesh and voxelsizes it into a boolean mask. Pitch is
1.0 voxel.

```python
from schematica.shapes.mesh import load_mesh
shape = load_mesh("castle.obj", scale=2.0)
```

## `schematica.shapes.heightmap`

### `Heightmap(heights, y_base=0, solid_below=True)`
- `heights`: `np.ndarray` shape `(sx, sz)` of int heights.
- `solid_below=True` fills `0 <= y < y_base+heights[x,z]`; `False` is a 1-voxel shell.

### `from_image(path, max_height=64) -> Heightmap`
Luminance -> height. PIL-backed.

## `schematica.generators.noise`

### `perlin2d(shape, scale=0.05, octaves=4, persistence=0.5, lacunarity=2.0, seed=0) -> np.ndarray`
Returns normalized `[0,1]` float32 via the `noise` package's `snoise2`.

### `fbm2d(shape, scale=0.05, octaves=4, seed=0) -> np.ndarray`
Alias for `perlin2d`.

## `schematica.generators.templates`

### `terrain_heightmap(shape, seed=0, base_height=None, amplitude=8, scale=0.06) -> Heightmap`
`base_height` defaults to `sy // 2`.

### `apply_terrain(session, seed=0, amplitude=8, scale=0.06, top=..., filler=..., bedrock=...)`
Fills terrain, paints top layer with `top` block.

### `apply_tree(session, x, z, height=6, trunk=..., leaves=...)`
Trunk + leaf canopy sphere.

## `schematica.render.preview`

### `preview(grid, out_dir, views=("top","front","right","iso")) -> list[Path]`
Writes `preview_<view>.png` files. Uses matplotlib `Axes3D.voxels` under Agg.
Colors come from `_BLOCK_COLORS` map in `preview.py`.

## `schematica.export.sponge`

### `write_sponge(grid, path, data_version=3465, offset=(0,0,0), metadata=None) -> Path`
Writes gzip-compressed Sponge v2 `.schem`. `data_version=3465` ≈ MC 1.20.1.
Block ordering: `index = (y*length + z)*width + x`, varint-encoded.

## `schematica.session.session`

### `Session.new(shape, version="1.20.1", fill=AIR) -> Session`
### `Session.load(path) -> Session`, `Session.restore(snap) -> Session`

Methods (all return `self` for chaining unless noted):
- `add(shape, block)`, `subtract(shape)`, `intersect(shape, block)`, `paint(shape, block)`.
- `replace(src, dst) -> int`, `fill_all(block)`, `clear()`.
- `transform_rotate(times, axes)`, `transform_mirror(axis)`.
- `undo() -> bool`, `redo() -> bool`.
- `snapshot() -> dict`, `save(path)`, `load(path)` classmethod.
- `stats() -> dict`.

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere
s = Session.new((16,16,16)).add(Box(0,0,0,15,15,15), "minecraft:stone").subtract(Sphere(8,8,8,5))
s.undo()
```

## `schematica.session.history`
Internal. `History(limit=100)` with `push(delta)`, `apply_inverse(data)`,
`apply_redo(data)`. `diff_delta(data, new) -> Delta`.

## `schematica.session.commands`
The CLI command table. Each `CommandSpec(name, args, handler, help)`.
Handlers take `(session, **kwargs)` and return a string. See
`references/cli_reference.md` for the full table.

## `schematica.cli.repl`

### `dispatch(session, line) -> str`
Parse + validate + run one command line. Returns a status string. May contain
`\n! [code] message` warning lines after the status. Errors start with
`error: [code]`. See `references/agent_cli_guide.md` for the full code table.

### `run_script(session, script_path) -> list[str]`
Run a script file non-interactively. Each command produces a `> line` echo
followed by its status/warnings.

### `repl_main(argv=None) -> int`
Entry point for `python -m schematica`. `--script path` for batch mode.

## `schematica.cli.validation`

Pre-execution checks returning `CheckResult(severity, code, message)` tuples.
`severity` is `"error"` (refuses the command) or `"warn"` (proceeds). Use these
directly from library code to validate before constructing shapes:

```python
from schematica.cli.validation import check_add_box, check_export
from schematica.session.session import Session

s = Session.new((16, 16, 16))
results = check_add_box("0,0,0", "20,20,20", "minecraft:stone", False, s, s.registry)
for r in results:
    print(r.severity, r.code, r.message)
```

Available check functions (all return `list[CheckResult]`):

**Session & general:** `check_session_new`, `check_replace`, `check_fill`,
`check_mirror`, `check_rotate`, `check_export`, `check_save`, `check_load`,
`check_preview`

**add.*:** `check_add_box`, `check_add_sphere`, `check_add_cylinder`,
`check_add_dome`, `check_add_cone`, `check_add_ellipsoid`, `check_add_pyramid`,
`check_add_torus`, `check_add_helix`, `check_add_arch`, `check_add_staircase`,
`check_add_spiral`, `check_add_line`, `check_add_wedge`, `check_add_plane`

**subtract.*:** `check_subtract_box`, `check_subtract_sphere`,
`check_subtract_cylinder`, `check_subtract_dome`, `check_subtract_pyramid`

**paint.*:** `check_paint_box`, `check_paint_sphere`

h-prefix commands (`add.hbox`, `add.hsphere`, etc.) route to the same
validators as their non-hollow counterparts with `hollow=True` forced.