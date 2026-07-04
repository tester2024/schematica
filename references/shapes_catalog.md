# Shapes catalog

All shapes implement the `Shape` protocol from `schematica.shapes.base`:

```python
class Shape(Protocol):
    def mask(self, shape: tuple[int, int, int]) -> np.ndarray: ...  # bool
```

`shape` is the target grid's `(sx, sy, sz)`. The mask is True at voxels the
shape occupies. Shapes are pure geometry — they never reference blocks.

## Primitives (`schematica.shapes.primitives`)

### `Box(x0, y0, z0, x1, y1, z1, hollow=False, wall_thickness=1)`
Axis-aligned filled box, inclusive bounds. `hollow=True` keeps only a shell of
`wall_thickness` voxels.

```python
Box(0,0,0, 3,3,3).mask((5,5,5)).sum()            # 64
Box(0,0,0, 4,4,4, hollow=True).mask((6,6,6)).sum()  # 125 - 27 = 98
```

### `Sphere(cx, cy, cz, r, hollow=False, shell_thickness=1.0)`
Voxels within Euclidean distance `r` of center. `hollow` keeps a shell.

### `Ellipsoid(cx, cy, cz, rx, ry, rz, hollow=False, shell_thickness=1.0)`
Anisotropic sphere. `(X-cx)/rx)² + ... <= 1`.

### `Cylinder(cx, cz, r, y0, y1, axis="y", hollow=False, shell_thickness=1.0, start=None, end=None)`
Right circular cylinder along ``axis`` (``"y"`` default, ``"x"`` or ``"z"``).
``cx``/``cz`` are the cross-section center coords and ``y0``/``y1`` are the
along-axis extent (inclusive). For ``axis="x"`` the cross-section is in (Y, Z)
centered at ``(cx, cz)`` and the long axis runs along X from ``y0`` to ``y1``;
for ``axis="z"`` the cross-section is in (X, Y) centered at ``(cx, cz)`` and the
long axis runs along Z. ``hollow=True`` keeps a tube shell of
``shell_thickness`` voxels.

The ``start``/``end`` aliases are explicit, axis-agnostic names for the
along-axis extent — when provided they override ``y0``/``y1`` and make
non-Y cylinders read naturally:

```python
Cylinder(8, 8, 3, start=2, end=6, axis="x")   # horizontal along X, cross-section in (Y,Z)
Cylinder(8, 8, 3, start=2, end=6, axis="z")   # horizontal along Z, cross-section in (X,Y)
```

### `Cone(cx, cz, r_base, y_base, y_apex, axis="y")`
Radius shrinks linearly from `r_base` at `y_base` to 0 at `y_apex`. The cone
runs along `axis` (``"y"`` default, ``"x"`` or ``"z"``); ``y_base``/``y_apex``
are interpreted as coordinates along that axis.

### `Pyramid(x0, z0, base_half, y_base, y_apex)`
Square pyramid centered at `(x0, z0)`.

### `Torus(cx, cy, cz, R, r)`
Donut: major radius `R` (ring center distance), minor radius `r` (tube).

### `Plane(axis, coord, thickness=1)`
Slab perpendicular to `axis` (`"x"|"y"|"z"`) at integer `coord`. `thickness`
spans `coord - thickness//2` to `coord + thickness//2 + (thickness%2)`.

### `Wedge(x0, y0, z0, x1, y1, z1, split_axis="x"|"z")`
Triangular prism: half of a box cut by a diagonal. With `split_axis="x"`, the
diagonal runs in the (x, y) plane so the apex sits at `x=x1, y=y0`.

### `Line(x0, y0, z0, x1, y1, z1)`
1-voxel-thick line via 3D lerp.

### `Dome(cx, cy, cz, r, hollow=False, shell_thickness=1.0, axis="y")` (advanced)
Half-sphere along ``axis`` (``"y"`` default, ``"x"`` or ``"z"``). For
``axis="y"`` keeps the upper hemisphere (y >= cy); for ``axis="x"`` keeps
X >= cx; for ``axis="z"`` keeps Z >= cz. Great for roofs, hills, wall caps,
and horizontal apses without needing ``Rotated90``.

### `Helix(cx, cy, cz, r, y0, y1, turns=3.0, thickness=1.0)` (advanced)
A helical curve winding `turns` times around the vertical (y) axis from `y0`
to `y1`, at radius `r`. Useful for spiral staircases, DNA strands, decorative
columns.

### `Arch(cx, cy, z0, z1, r, thickness=1.0, plane="xy")` (advanced)
A semicircular arch in the coordinate plane ``plane`` (``"xy"`` default,
``"xz"`` or ``"yz"``), extruded along the third axis. For ``plane="xy"`` the
ring lies in (X, Y) centered at (cx, cy) and extrudes along Z from ``z0`` to
``z1`` (the legacy behavior). For ``plane="xz"`` the ring lies in (X, Z)
centered at (cx, cy) and extrudes along Y; for ``plane="yz"`` the ring lies
in (Y, Z) centered at (cx, cy) and extrudes along X. The half-ring spans
angle 0 to pi on the +side of the in-plane axis.

### `Spiral(cx, cz, y0, y1, r_inner, r_outer, turns=2.0, thickness=1.0)` (advanced)
A flat 2D spiral in the (x, z) plane, extruded vertically from `y0` to `y1`.
Radius grows from `r_inner` to `r_outer` over `turns` revolutions. Useful for
nautilus shells, labyrinth floors.

### `Staircase(x0, y0, z0, y1, step_width=3, step_depth=2, step_height=1, axis="x")` (advanced)
A straight staircase rising from `(x0, y0, z0)` to height `y1`. Each step is
`step_width` wide, `step_depth` deep, rising `step_height` per step. `axis`
is `"x"` or `"z"` for the direction of travel.

## Boolean ops (`schematica.shapes.boolean`)

```python
Union((a, b)).mask(shape)
Intersect((a, b)).mask(shape)
Subtract(a, b).mask(shape)
Xor(a, b).mask(shape)
```

All return bool ndarrays. `Subtract` and `Xor` take exactly two shapes; `Union`
and `Intersect` take any number.

## Transforms (`schematica.shapes.transforms`)

### `Translated(shape, dx, dy, dz)`
np.roll-based shift within the grid. Wraps around boundaries.

### `Mirror(shape, axis)`
Flip along axis 0/1/2.

### `Rotated90(shape, times=1, axes="xy"|"xz"|"yz")`
Rotate by `90*times` degrees. `axes` names the two axes of the rotation plane.
Implemented via `np.rot90`, so the rotation is exact about the array centre
`((N-1)/2, (M-1)/2)` for the two named axes; the third axis is left unchanged.
Used internally by `Session.enable_radial_symmetry` and
`enable_quad_symmetry` when the rotation centre coincides with the grid
centre (the default). For an explicit offset centre, the symmetry pipeline
falls back to an exact index-map rotation.

```python
from schematica.shapes.primitives import Box
from schematica.shapes.transforms import Rotated90
# 90° rotation of a box in the xz plane.
rot = Rotated90(Box(0, 0, 0, 3, 3, 3), times=1, axes="xz")
```

### `Array(shape, count, axis, spacing)`
Repeat the shape `count` times along `axis` with `spacing` between copies.

### `NoiseDeformed(shape, amplitude=2, scale=0.1, seed=0)` (advanced)
Perturbs the edges of any base shape with Perlin noise. `amplitude` controls
how many voxels of deformation are possible; `scale` is the noise frequency.
Requires `scipy` for edge detection (falls back to a simpler method without it).

```python
from schematica.shapes.primitives import Sphere
from schematica.shapes.transforms import NoiseDeformed
boulder = NoiseDeformed(Sphere(8, 8, 8, 5), amplitude=3, scale=0.15, seed=42)
s.add(boulder, "minecraft:stone")
```

### `Shell(shape, thickness=1)` (advanced)
Keeps only the outer N-voxel shell of any shape — hollows it out regardless of
whether the base shape supports `hollow=True`.

```python
from schematica.shapes.primitives import Box
from schematica.shapes.transforms import Shell
s.add(Shell(Box(0, 0, 0, 10, 10, 10), thickness=2), "minecraft:stone")
```

## Polygon (`schematica.shapes.polygon`)

### `Extrude(polygon, x0, y0, z0, extrude_axis, length)`
2D polygon in (u, v) plane where u -> X, v -> Y. Extrude along `extrude_axis`
(`"x"|"y"|"z"`) for `length` voxels. The polygon's integer cells are sampled
via point-in-polygon tests.

Construct via the `extrude_polygon` helper:

```python
from shapely.geometry import Polygon
from schematica.shapes.polygon import extrude_polygon

poly = Polygon([(0,0),(4,0),(4,4),(0,4)])
shape = extrude_polygon(poly, origin=(2,2,2), extrude_axis="y", length=10)
```

Accepts WKT strings, GeoJSON dicts, or `.json` file paths.

## Mesh (`schematica.shapes.mesh`)

### `MeshShape(mesh, origin=(0,0,0), scale=1.0)`
Voxelizes a trimesh via `trimesh.voxelize.VoxelGrid(pitch=1.0)`. The mesh is
scaled and translated before voxelization. `load_mesh(path, origin, scale)`
loads OBJ/STL/glTF.

## Heightmap (`schematica.shapes.heightmap`)

### `Heightmap(heights, y_base=0, solid_below=True)`
- `heights`: int ndarray shape `(sx, sz)` — height of the surface at each (x,z).
- `solid_below=True`: fill `y_base <= y < y_base + heights[x,z]`.
- `solid_below=False`: 1-voxel-thick shell at `y = y_base + heights[x,z] - 1`.

### `from_image(path, max_height=64)`
Grayscale image -> heights. PIL-backed.