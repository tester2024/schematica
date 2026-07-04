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
reg["stone"]                  # same lookup; minecraft: prefix is normalized
reg.by_id(1)                  # BlockDef by numeric id
"minecraft:stone" in reg     # True
reg.validate(Block.parse("minecraft:oak_log[axis=y]"))   # raises on bad keys/values
reg.resolve(Block.parse("minecraft:oak_log"))             # validates + fills axis=y default
reg.search("oak")             # list[BlockDef]
reg.all()                     # list[BlockDef]
BlockRegistry.list_versions()  # ["1.20.1", "1.21", ...] if minecraft_data vendored
```

`resolve(block, strict=True)` is strict by default: explicit unknown state keys,
invalid enum/bool/int values, and states on stateless fallback blocks raise
`ValueError` instead of being silently dropped.

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

## `schematica.core.chunked`

### `ChunkedGrid(shape, palette=Palette(), chunk_size=16)`
Sparse chunk-backed 3D voxel grid. Only chunks containing non-air voxels are
allocated; untouched chunks are implicit air. Same read/write surface as
`VoxelGrid` (get/set/fill/apply_mask/erase_mask/paint_mask/replace/count/
nonempty_count/slice_x/slice_y/slice_z/subregion/copy/rotate/mirror) plus
chunk-specific helpers:

- `chunks_per_axis -> (ncx, ncy, ncz)` — chunk counts.
- `to_dense() -> VoxelGrid` — flatten into a contiguous grid (heavy for huge grids).
- `from_dense(grid, chunk_size=16)` classmethod — build a chunked grid from a dense one.
- `iter_chunks()` — yield `(cx, cy, cz, ndarray)` for every materialised chunk.
- `iter_chunks_in_box(x0,y0,z0, x1,y1,z1)` — yield chunks overlapping a world bbox.
- `chunk_count() -> int` — number of materialised chunks.
- `memory_estimate_bytes() -> int` — sum of allocated chunk array sizes.
- `DEFAULT_CHUNK_SIZE = 16` — default chunk edge length.

```python
from schematica.core.chunked import ChunkedGrid, DEFAULT_CHUNK_SIZE
g = ChunkedGrid(shape=(160, 64, 160), chunk_size=16)
g.set(10, 5, 10, Block.parse("minecraft:stone"))   # allocates 1 chunk (~98 KB)
g.chunk_count()   # 1
```

## `schematica.shapes.base`

### `Shape` (Protocol)
```python
class Shape(Protocol):
    def mask(self, shape: tuple[int,int,int]) -> np.ndarray: ...
```
Returns a boolean ndarray of `shape`.

### Helpers
- `coords_grid(shape) -> (X, Y, Z)` — meshgrid int index arrays (indexing="ij").
- `coords_grid_offset(shape, origin) -> (X, Y, Z)` — meshgrid of world coords for
  a sub-grid of `shape` offset by `origin` (local index i -> world `origin[i]+i`).
- `in_bounds(coord, shape) -> bool` — single (x, y, z) inside the grid?
- `bounds_default(shape) -> (x0,y0,z0,x1,y1,z1)` — full-grid inclusive bbox.
- `intersect_bbox(a, b) -> bbox | None` — inclusive-bbox intersection; `None` if disjoint.
- `mask_region(shape, grid_shape, origin, size) -> np.ndarray` — restrict a shape's
  mask to world region `[origin, origin+size)`; default computes the full-grid
  mask and slices.
- `shape_bounds(shape, grid_shape) -> bbox` — the inclusive bbox where the shape
  could be True, or the full grid if the shape has no `bounds()` method.

### `coords_grid(shape) -> (X, Y, Z)`
Meshgrid int index arrays (indexing="ij").

### `in_bounds(coord, shape) -> bool`
Check if a single (x, y, z) coordinate is inside the grid.

## `schematica.shapes.primitives`
All are frozen dataclasses implementing `Shape`.

- `Box(x0,y0,z0, x1,y1,z1, hollow=False, wall_thickness=1)` — inclusive bounds.
- `Sphere(cx,cy,cz, r, hollow=False, shell_thickness=1.0)`.
- `Ellipsoid(cx,cy,cz, rx,ry,rz, hollow=False, shell_thickness=1.0)`.
- `Cylinder(cx,cz, r, y0,y1, axis="y", hollow=False, shell_thickness=1.0, start=None, end=None)`.
  `start`/`end` are explicit aliases for the along-axis extent (they override
  `y0`/`y1`) so non-Y cylinders read naturally:
  `Cylinder(8, 8, 3, start=2, end=6, axis="x")`.
- `Cone(cx,cz, r_base, y_base, y_apex, axis="y")` — supports `axis="x"|"z"`.
- `Pyramid(x0,z0, base_half, y_base, y_apex)`.
- `Torus(cx,cy,cz, R, r)` — R major, r minor.
- `Dome(cx,cy,cz, r, hollow=False, shell_thickness=1.0, axis="y")` — supports
  `axis="x"|"z"` for wall-mounted caps.
- `Helix(cx,cy,cz, r, y0,y1, turns=3.0, thickness=1.0)` — spiral curve around y axis.
- `Arch(cx,cy, z0,z1, r, thickness=1.0, plane="xy")` — semicircular arch in
  plane `"xy"` (default), `"xz"` or `"yz"`, extruded along the third axis.
- `Spiral(cx,cz, y0,y1, r_inner,r_outer, turns=2.0, thickness=1.0)` — flat spiral extruded vertically.
- `Staircase(x0,y0,z0, y1, step_width=3, step_depth=2, step_height=1, axis="x")` — straight stairs.
- `Plane(axis, coord, thickness=1)` — axis-aligned slab perpendicular to axis.
- `Wedge(x0,y0,z0, x1,y1,z1, split_axis="x"|"z")` — triangular prism (half a box).
- `Line(x0,y0,z0, x1,y1,z1)` — 1-voxel Bresenham line.
- `BezierCurve(p0,p1,p2, p3=None, thickness=0.5, samples=128)` — quadratic or
  cubic 3D Bezier curve extruded as a tube.

See `references/shapes_catalog.md` for arg semantics and examples.

## `schematica.shapes.boolean`
- `Union(shapes: tuple[Shape, ...])`.
- `Intersect(shapes: tuple[Shape, ...])`.
- `Subtract(a, b)`.
- `Xor(a, b)`.

## `schematica.shapes.sdf`
Signed-distance-field shapes for organic smooth blending. Each takes the
inner/outer SDF of its input shapes and applies a polynomial smooth-min/max
so joins round over `k` voxels. `k=0` reduces to the hard boolean op.

- `SDFShape(shape)` — wrap a binary shape as an SDF via distance transform.
- `SmoothUnion(a, b, k=1.0)` — blend two shapes with a smooth minimum.
- `SmoothIntersect(a, b, k=1.0)` — smooth intersection.
- `SmoothSubtract(a, b, k=1.0)` — smooth subtraction.

```python
from schematica.shapes.primitives import Sphere, Cylinder
from schematica.shapes.sdf import SmoothUnion
# Organic terrain-to-structure transition: 2-voxel blend.
blend = SmoothUnion(Sphere(10, 10, 10, 5), Cylinder(10, 10, 5, 0, 10), k=2.0)
```

## `schematica.shapes.transforms`
- `Translated(shape, dx, dy, dz)` — np.roll based (wraps at grid edges).
- `Mirror(shape, axis)` — axis 0/1/2.
- `Rotated90(shape, times=1, axes="xy"|"xz"|"yz")` — 90° multiples via
  `np.rot90` (exact rotation about the array centre `(N-1)/2`). Used
  internally by `Session.enable_radial_symmetry` / `enable_quad_symmetry`
  for the default-centre case.
- `Rotated(shape, angle_deg=0.0, axes="xy"|"xz"|"yz", order=0)` — arbitrary
  angle rotation via nearest-neighbour resampling.
- `Array(shape, count, axis, spacing)` — repeat along an axis.
- `NoiseDeformed(shape, amplitude=2, scale=0.1, seed=0)` — perturb edges with Perlin noise. Requires scipy for best results (falls back without it).
- `Shell(shape, thickness=1)` — keep only the outer N-voxel shell of any shape.

## `schematica.shapes.polygon`

### `extrude_polygon(polygon, origin=(0,0,0), extrude_axis="z", length=1) -> Extrude`
`polygon` accepts a `shapely.geometry.Polygon`, WKT string, GeoJSON dict,
path to a `.json` GeoJSON file, or an SVG path ``d`` string (e.g.
``"M 0 0 H 10 V 10 H 0 Z"`` — supports ``M``/``L``/``H``/``V``/``C``/``Q``/``Z``
commands, absolute and relative). The polygon's (u, v) maps to (X, Y) of the
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

## `schematica.generators.replace`
Advanced block replacement. All functions work on both `VoxelGrid` and
`ChunkedGrid`.

- `replace_bulk(grid, mapping) -> int` — replace many sources at once in a
  single pass. `mapping` is `{src_block_or_str: dst_block_or_str}`. Returns
  count rewritten.
- `replace_filtered(grid, src, dst, *, where=None) -> int` — replace `src`
  with `dst` only where `where(block)` is True (predicate receives the source
  block). If `where` is None, behaves like plain `grid.replace`.
- `replace_by_name(grid, src_name, dst, *, where=None) -> int` — replace
  every block whose name matches `src_name` regardless of state. Optionally
  filter via `where(block)`; the predicate is evaluated per palette entry, so
  it is efficient even on large grids.
- `replace_in_mask(grid, src, dst, mask) -> int` — replace `src` with `dst`
  only within the True cells of `mask`. Useful for "replace stone with
  mossy_cobblestone only inside this box / sphere / noise region".
- `replace_pattern(grid, src, dst, *, neighbours=None) -> int` — replace
  `src` with `dst` where all neighbour constraints hold. See `NeighbourSpec`.
- `NeighbourSpec(offset, block)` dataclass — describes a relative offset and
  the block that must be at that offset (`"*"` = any non-air, `"air"` = air).
  Convenience constructors: `NeighbourSpec.above(block="*")`,
  `.below(block="*")`, `.side(block="*")`.

## `schematica.generators.retexture`
Swap blockstate properties in-place without changing block names.

- `retexture(grid, property, value, *, name=None, where=None) -> int` — set
  `property` = `value` on every block that has that property. `name` filters by
  block name; `where(block)` is an optional predicate.
- `retexture_map(grid, property, mapping, *, name=None, where=None) -> int` —
  remap a state property across many values (e.g. `{"x":"y","y":"z","z":"x"}`
  to rotate axes).
- `retexture_random(grid, property, values, *, name=None, seed=0) -> int` —
  assign `property` a random value from `values` per voxel. Deterministic
  given `seed`. Useful for randomising wall post orientations, stair facings,
  or mossy-vs-clean patterns.

## `schematica.generators.texture`
Noise-driven block distribution for organic texture variation.

- `perlin_field(shape, scale=0.1, octaves=4, seed=0) -> np.ndarray` — 2D/3D
  Perlin noise normalised to `[0, 1]`. For 3D it stacks 2D planes along the
  third axis using offset seeds.
- `worley_field(shape, num_points=16, seed=0) -> np.ndarray` — Worley/Voronoi
  noise (distance to nearest random point, normalised to `[0, 1]`). Pure
  numpy, no extra deps. Produces cell-like patches — good for cracked stone
  or tiled mosaic textures.
- `TexturePalette(blocks, weights, noise, scale, octaves, seed,
  worley_points)` dataclass — a weighted block palette driven by a noise
  field. `noise` is `"perlin"` or `"worley"`. `.sample(shape) -> np.ndarray`
  returns an int array of palette indices; `.blockstate_grid(shape) -> np.ndarray`
  returns an object array of blockstate strings.
- `apply_texture(session, palette, frm, to) -> int` — paint a region with
  blocks sampled from `palette`; only fills existing solid voxels (like
  `paint`). Returns count painted.
- `apply_texture_fill(session, palette, frm, to) -> int` — fill a region
  (overwriting air too) with blocks sampled from `palette`. Returns count
  written.

## `schematica.generators.wfc`
Wave function collapse over a 3D voxel grid.

- `Tile(block, edges)` dataclass — a 1-voxel WFC tile. `block` is the
  blockstate string placed when observed; `edges` is a 6-tuple of edge labels
  `(+x, -x, +y, -y, +z, -z)`. `.rotated()` returns the tile rotated 90° about Y.
- `TileSet(tiles)` dataclass — collection of tiles + adjacency table.
  `.compatible(a, b, face) -> bool`, `.block_for(idx) -> str`.
- `WFC(shape, tileset)` dataclass — the wave state. `.seed(seed)`,
  `.step() -> bool` (collapse one cell), `.run(max_iter=10000) -> np.ndarray`
  (returns a `(sx,sy,sz)` int array of tile indices).
- `ContradictionError` — raised when a cell has no compatible tile or the
  wave cannot converge.
- `run_wfc(shape, tileset, *, seed=0, max_iter=10000) -> np.ndarray` —
  convenience: run WFC and return a `(sx,sy,sz)` object array of blockstate
  strings ready to feed into `Session.set`.
- `tileset_wildcard(tiles) -> TileSet` — build a permissive tileset where
  every tile is compatible with every other (all-`"*` edges). Useful for
  project-specific generated palettes without fixed bundled templates.

## `schematica.render.preview`

### `preview(grid, out_dir, views=("top","front","right","iso")) -> list[Path]`
Writes `preview_<view>.png` files. Small dense grids use matplotlib
`Axes3D.voxels` under Agg. Large dense grids switch to downsampled projected
views and warn; `ChunkedGrid` previews use projected views without dense
materialisation. Projected fallback `iso` writes `preview_iso_projected.png` to
avoid implying a true 3D isometric render. Colors come from `_BLOCK_COLORS` map
in `preview.py`.

### `preview_chunked(grid, out_dir, views=...) -> list[Path]`
Explicit entry point for `ChunkedGrid` previews — uses projected rendering
without ever materialising a full dense array. Called automatically by
`preview()` when the grid is chunked; exposed so callers can force the
chunked path.

### `preview_region(grid, corner, size, out_dir, views=...) -> list[Path]`
Extract `grid[corner .. corner+size]` as a small dense sub-grid and render it
with the standard pipeline. Useful for reviewing one team base or focal
structure on large maps. Raises `ValueError` if the region is outside the grid.

## `schematica.export.sponge`

### `write_sponge(grid, path, data_version=3465, offset=(0,0,0), metadata=None) -> Path`
Writes gzip-compressed Sponge v2 `.schem`. `data_version=3465` ≈ MC 1.20.1.
Block ordering: `index = (y*length + z)*width + x`, varint-encoded.
Warns when a pre-1.13 `data_version` is paired with modern flattened names or
blockstate properties.

## `schematica.export.mcedit`

### `write_mcedit(grid, path, legacy_ids=None, block_meta=None, strict=False) -> Path`
Writes gzip-compressed legacy MCEdit `.schematic` with `Blocks` and `Data` byte
arrays. The default mapping covers common legacy blocks and metadata for all 16
colors of wool, stained glass, terracotta, and concrete, plus common stone,
plank, log, sand, resource, and mapmaking variants. Non-air blocks without a
legacy mapping warn because they become air. Set `strict=True` to raise instead,
or call `legacy_unmapped_blocks(grid, legacy_ids=None) -> list[str]` before export.

### `legacy_unmapped_blocks(grid, legacy_ids=None) -> list[str]`
Return the list of non-air palette blockstate strings that have no legacy ID
mapping and would become air in MCEdit export. Use this to decide whether to
call `apply_substitutions` or switch to Sponge/Litematica.

## `schematica.export.litematic`

### `write_litematic(grid, path, region_name="Main", origin=(0,0,0), data_version=3465) -> Path`
Writes a single-region Litematica `.litematic` with palette and packed
`BlockStates`. Dense and chunked grids are both supported.

## `schematica.session.session`

### `Session.new(shape, version="1.20.1", fill=AIR, chunked=False, chunk_size=16) -> Session`
### `Session.load(path) -> Session`, `Session.restore(snap) -> Session`

Properties:
- `is_chunked -> bool` — True when the backend is `ChunkedGrid`.
- `symmetry_active -> bool` — True when `enable_symmetry` is currently in effect.

Methods (all return `self` for chaining unless noted):
- `add(shape, block, **shape_kwargs)`, `subtract(shape, **shape_kwargs)`,
  `intersect(shape, block, **shape_kwargs)`, `paint(shape, block, **shape_kwargs)`.
  The `**shape_kwargs` are forwarded to the shape's dataclass fields via
  `dataclasses.replace` — e.g. `s.add(Sphere(...), "stone", hollow=True)`
  works. Unknown kwargs raise `TypeError` with a clear message.
- `enable_symmetry(axis, center=None)`, `disable_symmetry()` — live mirror:
  when enabled, every subsequent `add`/`subtract`/`paint` is automatically
  unioned with its mirror image about `center` (grid middle by default)
  along `axis` (0/1/2 or "x"/"y"/"z"). `symmetry_active` is a read-only property.
- `enable_radial_symmetry(folds=4, plane="xz", center=None)`,
  `enable_quad_symmetry(center=None)` — live rotational cloning: every
  subsequent `add`/`subtract`/`paint` is unioned with its rotations about
  `center` (grid middle by default) in the named plane (`"xz"` for horizontal
  rotation, `"xy"`/`"yz"` for vertical). `folds=4` gives quad symmetry,
  `folds=8` octo symmetry, `folds=2` a half-turn mirror. For the default
  centre the rotations use the cheap exact `Rotated90` transform; for an
  explicit offset centre an exact index-map rotation is used.
- `resample_subregion(frm, to, new_size, block=..., dest_origin=None) -> int`
  — nearest-neighbour resample of a source box to `new_size`, written at
  `dest_origin` (defaults to `frm`'s min corner).
- `set_box(frm, to, block, history=True, clip=True) -> int` — fast inclusive cuboid write.
- `set_many(coords, block, history=True, skip_out_of_bounds=True) -> int` — fast point writes.
- `replace(src, dst) -> int`, `fill_all(block)`, `clear()`.
- `clone_translate(frm, to, offset, count=1, include_air=False) -> int`.
- `clone_cardinal(frm, to, center, include_air=False) -> int`.
- `transform_rotate(times, axes)`, `transform_mirror(axis)`.
- `undo() -> bool`, `redo() -> bool`.
- `snapshot() -> dict`, `save(path)`, `load(path)` classmethod.
- `stats() -> dict` (includes `markers` and `regions` counts).
- `marker(name, x, y, z, kind="point") -> self` — add a named marker.
- `region(name, corner, size, kind="area") -> self` — add a named bounding-box annotation.
- `markers() -> list[dict]`, `regions() -> list[dict]`.
- `export_markers(path) -> Path` — write markers+regions+shape JSON.
- `paint_gradient(frm, to, blocks, axis, blend, seed) -> int` — gradient paint.
- `edge_wear(blocks, min_exposure, max_exposure, noise, seed) -> int` — weathering.
- `surface_scatter(block, density, ...) -> int` — surface scatter.
- `walkable_at(x, y, z) -> bool`, `clearance_at(x, y, z, height) -> int`.
- `is_connected(a, b) -> bool`, `reachable_area(start) -> int`.
- `shortest_path(a, b) -> list | None`.

## `schematica.export.report`
Pre-export compatibility reports.

- `palette_report(grid, registry=None) -> dict` — returns `palette_size`,
  `block_count`, `unknown_blocks` (not in registry), `mcedit_unmapped` (would
  become air in MCEdit), and `sponge_ok`.
- `format_report(report) -> str` — one-line human-readable summary.

## `schematica.procedural.detail`
Procedural micro-detail tools for organic weathering and variation. All operate
on existing solid voxels only (never fill empty space).

- `paint_gradient(grid, frm, to, blocks, axis="y", blend=0.0, seed=0) -> int` —
  paint a linear gradient of blocks along an axis. Returns voxels painted.
- `edge_wear(grid, blocks, min_exposure=1, max_exposure=6, noise=0.0, seed=0) -> int` —
  apply weathering blocks to voxels with exposed air faces. More exposed = more
  weathered (earlier block in list). Returns voxels weathered.
- `surface_scatter(grid, block, density=0.1, min_exposure=1, max_exposure=6, seed=0, on_blocks=None) -> int` —
  probabilistically scatter a block on exposed surfaces. `on_blocks` restricts
  to specific source blocks. Returns voxels scattered.

## `schematica.analysis.spatial`
Spatial planning and walkability analysis. Read-only on the grid.

- `walkable_at(grid, x, y, z) -> bool` — can a player stand here? (passable +
  headroom + solid floor below).
- `clearance_at(grid, x, y, z, height=2) -> int` — vertical free blocks above.
- `walkable_map(grid, floor_y=None) -> np.ndarray` — 2D (x,z) boolean map of
  walkable positions.
- `reachable_area(grid, start, max_steps=0) -> np.ndarray` — 3D boolean
  flood-fill of walkable positions reachable by walking from `start`.
- `is_connected(grid, a, b) -> bool` — can a player walk from a to b?
- `shortest_path(grid, a, b) -> list | None` — BFS shortest walking path.

## `schematica.export.validation`
Cross-format round-trip validation.

- `validate_export(grid, path, fmt="sponge", data_version=3465) -> ValidationResult` —
  write a file and read it back, checking palette + voxel integrity.
- `validate_all(grid, dir_path, data_version=3465) -> list[ValidationResult]` —
  validate all three formats (sponge, litematic, mcedit).
- `ValidationResult` — dataclass with `ok`, `format`, `path`, `issues`,
  `missing_blocks`, `extra_blocks`, `voxel_mismatches`, `total_voxels`.

## `schematica.constraints`
Declarative build constraint system.

- `Constraint` (Protocol) — `name: str` + `check(grid) -> list[str]` (empty = OK).
- `ConstraintSet(constraints)` — collection with `add(c)`, `check_all(grid) ->
  dict`, `check_or_raise(grid)`, `attach(session)`, `detach()`.
- `HeightLimit(max_y)` — no solid above Y.
- `BlockBan(banned)` — forbidden block names.
- `BlockAllowlist(allowed)` — only these block names allowed (air always OK).
- `Symmetry(axis)` — require mirror symmetry about axis 0/1/2.
- `BoxBounds(min_corner, max_corner)` — no solid outside the box.
- `MaxBlockCount(block_name, max_count)` — limit voxels of a block.
- `PaletteLimit(max_size)` — palette entry cap.
- `SolidRatio(min_frac, max_frac)` — volume fraction bounds.
- `ConstraintViolation` — exception raised on violation (carries
  `.constraint_name` and `.message`).

## `schematica.export.materials`
Material intelligence: automatic legacy block substitutions for MCEdit export.

- `suggest_substitutions(grid) -> dict[str, str]` — for each unmapped palette
  block, suggest the closest legacy-compatible substitute.
- `apply_substitutions(grid, subs=None) -> int` — replace unmapped blocks with
  their substitutes. Returns voxels substituted.
- `substitution_report(grid) -> dict` — detailed report with counts.

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere
s = Session.new((16,16,16)).add(Box(0,0,0,15,15,15), "minecraft:stone").subtract(Sphere(8,8,8,5))
s.undo()
```

## `schematica.session.history`
Internal. `History(limit=100)` with `push(delta)`, `can_undo() -> bool`,
`can_redo() -> bool`, `apply_inverse(target)`, `apply_redo(target)`,
`clear()`. `diff_delta(data, new) -> Delta`. Callers normally use
`Session.undo()` / `Session.redo()` instead of touching `History` directly.

## `schematica.session.commands`
The CLI command table. Each `CommandSpec(name, args, handler, help)`.
`ArgSpec(name, kind, required=True, default=None)` describes one argument
(`kind` ∈ `int, float, str, bool, coords, block, shape`). Handlers take
`(session, **kwargs)` and return a string. See `references/cli_reference.md`
for the full table.

## `schematica.cli.parser`

### `ParsedCommand(name, args)` dataclass
The result of parsing one command line: `name` is the dotted command name,
`args` is a dict of `key=value` pairs plus an `__positional__` key holding the
concatenated positional tokens.

### `parse_line(line) -> ParsedCommand | None`
Tokenize a command line via `shlex.split`. Returns `None` for blank lines and
`#`-comments. Otherwise returns a `ParsedCommand`. Positional tokens are
matched to `ArgSpec`s in spec order at dispatch time (see `cli.repl.dispatch`).

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
`check_mirror`, `check_rotate`, `check_clone_translate`, `check_clone_cardinal`,
`check_generate_tree`, `check_generate_wfc`, `check_export`, `check_save`,
`check_load`, `check_preview`

**add.*:** `check_add_box`, `check_add_sphere`, `check_add_cylinder`,
`check_add_dome`, `check_add_cone`, `check_add_ellipsoid`, `check_add_pyramid`,
`check_add_torus`, `check_add_helix`, `check_add_arch`, `check_add_staircase`,
`check_add_spiral`, `check_add_line`, `check_add_wedge`, `check_add_plane`

**subtract.*:** `check_subtract_box`, `check_subtract_sphere`,
`check_subtract_cylinder`, `check_subtract_dome`, `check_subtract_pyramid`

**paint.*:** `check_paint_box`, `check_paint_sphere`

h-prefix commands (`add.hbox`, `add.hsphere`, etc.) route to the same
validators as their non-hollow counterparts with `hollow=True` forced.

### `CheckResult.is_error() -> bool`
Convenience: returns `True` when `severity == "error"` (the command should be
refused). Equivalent to `r.severity == "error"`.
