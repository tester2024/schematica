# Generators

Procedural and AI generators. Terrain, tree, and WFC helpers are available
through both the library API and CLI commands (`generate.terrain`,
`generate.tree`, `generate.wfc`). Use Python when you need loops, custom
placement rules, or generator parameters that the CLI does not expose.

This document also covers the Phase 12 additions: SDF smooth blending,
Bezier-curve tubes, SVG path voxelization, the active symmetry decorator, and
the subregion resampling utility.

## `schematica.generators.noise`

### `perlin2d(shape, scale=0.05, octaves=4, persistence=0.5, lacunarity=2.0, seed=0) -> np.ndarray`
Returns a `(w, h)` float32 array normalized to `[0, 1]`. Wraps the `noise`
package's `snoise2` (simplex). `fbm2d` is an alias.

- `scale`: frequency multiplier; smaller = larger features.
- `octaves`: layer count for fractal Brownian motion.
- `seed`: deterministic; same seed -> identical output across runs.

```python
from schematica.generators.noise import perlin2d
n = perlin2d((64, 64), scale=0.05, octaves=4, seed=42)
```

## `schematica.generators.templates`

### `terrain_heightmap(shape, seed=0, base_height=None, amplitude=8, scale=0.06) -> Heightmap`
Builds a `Heightmap` from Perlin noise. `base_height` defaults to `sy // 2`.

### `apply_terrain(session, seed=0, amplitude=8, scale=0.06, top=..., filler=..., bedrock=...)`
Fills the session grid with terrain: `filler` below the surface, `top` on the
topmost layer. Skips `bedrock` by default (not applied; reserved for future).

```python
from schematica.session.session import Session
from schematica.generators.templates import apply_terrain

s = Session.new((32, 32, 32))
apply_terrain(s, seed=42, amplitude=6,
              top="minecraft:grass_block", filler="minecraft:dirt")
```

### `apply_tree(session, x, z, height=6, trunk=..., leaves=...)`
Adds a trunk (oak_log by default) of `height` blocks and a leaf canopy (sphere
r=3 centered at the top). No random variation — deterministic given args.

```python
apply_tree(s, x=8, z=8, height=7)
apply_tree(s, x=20, z=14, height=5)
```

## Wave function collapse

`schematica.generators.wfc` provides tile-based wave function collapse over
block palettes. The CLI exposes a `mossy_ruins` tileset and a small wildcard
tileset:

```
generate.wfc frm=4,1,4 to=12,6,12 tileset=mossy_ruins seed=42
```

More templates such as village, temple, tower, and dungeon remain roadmap
items.

## SDF smooth blending (Phase 12)

`schematica.shapes.sdf` provides signed-distance-field shapes that compose
with smooth-minimum / smooth-maximum for organic transitions between shapes.
Use these where strict binary `Union` / `Subtract` produce hard, mechanical
joins — for example, melting a stone boulder into a dirt hillside, or blending
a glass dome smoothly into a stone tower.

- `SDFShape(shape)` — wrap a binary shape as an SDF via distance transform.
  Uses `scipy.ndimage.distance_transform_edt` when available; falls back to a
  pure-numpy iterative-erosion BFS so it works without scipy.
- `SmoothUnion(a, b, k=1.0)` — blend two shapes with a polynomial smooth-min.
  `k=0` reduces to the hard boolean `Union` (byte-identical; verified by
  `test_smooth_union_hard_k0_matches_union`).
- `SmoothIntersect(a, b, k=1.0)` — smooth intersection (smooth-max of SDFs).
- `SmoothSubtract(a, b, k=1.0)` — smooth subtraction: `smooth-max(a, -b)`.

```python
from schematica.shapes.primitives import Sphere, Cylinder
from schematica.shapes.sdf import SmoothUnion

# Organic terrain-to-structure transition: 2-voxel blend.
blend = SmoothUnion(Sphere(10, 10, 10, 5), Cylinder(10, 10, 5, 0, 10), k=2.0)
s.add(blend, "minecraft:stone")
```

Larger `k` widens the blend region; `k=0` is the hard boolean op. SDF evaluation
is O(N³) per shape so prefer it for medium grids (≤ ~64³) or use the chunked
backend to limit touched chunks.

## Bezier curves and tubes (Phase 12)

`schematica.shapes.primitives.BezierCurve` draws a 1-voxel-thick 3D Bezier
curve and extrudes it into a tube of `thickness` voxels. Supports quadratic
(3 control points) and cubic (4 control points) curves. Useful for organic
paths, winding rivers, custom bridge cables, and decorative arches that
Bresenham lines cannot express.

```python
from schematica.shapes.primitives import BezierCurve

# Quadratic Bezier: arc from (0,0,0) through (8,15,8) to (15,0,15), tube radius 1.0.
curve = BezierCurve((0, 0, 0), (8, 15, 8), (15, 0, 15), thickness=1.0)
s.add(curve, "minecraft:oak_log")

# Cubic Bezier: S-curve from (0,0,0) to (15,0,0) bowing up and back down.
s_curve = BezierCurve((0, 0, 0), (0, 15, 15), (15, 15, 15), (15, 0, 0),
                     thickness=1.5, samples=200)
s.add(s_curve, "minecraft:smooth_quartz")
```

## SVG path voxelization (Phase 12)

`extrude_polygon` now accepts an SVG path `d`-string. The parser supports
`M`/`L`/`H`/`V`/`C`/`Q`/`Z` (absolute and lowercase relative); curved `C`/`Q`
segments are flattened into polylines, then closed and converted to a shapely
polygon via `buffer(0)`. This lets you take a decorative SVG silhouette and
extrude it into a prism without an external SVG library.

```python
from schematica.shapes.polygon import extrude_polygon

# A 10x10 square via SVG path: M 0 0 H 10 V 10 H 0 Z
shape = extrude_polygon("M 0 0 H 10 V 10 H 0 Z", origin=(0, 0, 0),
                        extrude_axis="z", length=4)
s.add(shape, "minecraft:quartz_block")

# A path with a quadratic curve: M 0 0 Q 5 10 10 0 Z
curved = extrude_polygon("M 0 0 Q 5 10 10 0 Z", origin=(0, 0, 0),
                        extrude_axis="z", length=3)
s.add(curved, "minecraft:smooth_quartz")
```

## Active symmetry decorator (Phase 12)

`Session.enable_symmetry(axis, center=None)` turns on live mirroring: every
subsequent `add` / `subtract` / `paint` is automatically unioned with its
mirror image about `center` (grid middle by default) along `axis` (0/1/2 or
`"x"`/`"y"`/`"z"`). `disable_symmetry()` turns it off; `symmetry_active` is a
read-only property. This is the dynamic brush the review asked for — much
faster than manually wrapping each shape in `Union((shape, Mirror(...)))`.

```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box

s = Session.new((16, 16, 16))
s.enable_symmetry(axis="x")  # mirror about x = 7.5 (grid middle)
s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
# Both (1,1,1) and (14,1,1) are now stone.
s.disable_symmetry()
assert not s.symmetry_active
```

## Subregion resampling (Phase 12)

`Session.resample_subregion(frm, to, new_size, block, dest_origin=None)`
resamples a source box `[frm, to]` (inclusive) to `new_size` using nearest-
neighbour interpolation, then writes the non-air voxels at `dest_origin`
(defaults to `frm`'s min corner) as the given `block`. Useful for upscaling a
detailed $10^3$ pillar into a $15^3$ space or shrinking a build into a thumbnail.

```python
s = Session.new((32, 32, 32))
s.add(Box(0, 0, 0, 9, 9, 9), "minecraft:stone")  # 10x10x10 source
# Downscale to a 4x4x4 thumbnail at (24, 24, 24).
s.resample_subregion((0, 0, 0), (9, 9, 9), new_size=(4, 4, 4),
                    block="minecraft:cobblestone", dest_origin=(24, 24, 24))
# Upscale the same source to 20x20x20 at (12, 0, 12).
s.resample_subregion((0, 0, 0), (9, 9, 9), new_size=(20, 20, 20),
                    block="minecraft:smooth_stone", dest_origin=(12, 0, 12))
```

## Texture hacks

Use texture tools to make surfaces read like veteran Minecraft builds instead
of flat fills. A texture hack must still be a real block or valid blockstate for
the target version.

- `texture.palette` / `TexturePalette` applies a weighted, noise-driven material
  mix to existing solids. Use it for stone gradients, dirt/grass variation,
  mossy ruin patches, cracked floors, or subtle roof variation.
- `retexture` changes a supported blockstate property such as `axis`, `facing`,
  `half`, or `waterlogged` on existing palette entries that already carry that
  state.
- `retexture.map` remaps state values across a region, useful for alternating
  log axes, rotated stairs, or repeated trim details.
- `replace.bulk`, `replace.by_name`, and `replace.pattern` are useful for
  weathering passes: turn exposed stone into mossy blocks, darken edges, or
  vary blocks only near air, water, plants, or structural joints.

CLI example:

```
texture.palette frm=0,1,0 to=63,8,63 blocks=minecraft:stone+minecraft:cobblestone+minecraft:mossy_cobblestone+minecraft:stone_bricks weights=0.50+0.25+0.15+0.10 noise=perlin scale=0.12 seed=42
retexture property=axis value=x name=minecraft:oak_log
generate.wfc frm=8,1,8 to=24,6,24 tileset=mossy_ruins seed=9
```

## Recipe: terrain + trees + export

```python
from schematica.session.session import Session
from schematica.generators.templates import apply_terrain, apply_tree
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview
import random

s = Session.new((48, 32, 48), version="1.20.1")
apply_terrain(s, seed=42, amplitude=6)

rng = random.Random(42)
for _ in range(12):
    x = rng.randint(2, 45)
    z = rng.randint(2, 45)
    apply_tree(s, x=x, z=z, height=rng.randint(5, 8))

write_sponge(s.grid, "forest.schem")
preview(s.grid, "forest_previews")
```

## How the AI agent drives generation

This skill does not call an LLM internally. The agent loading this skill IS
the creative driver. Typical agent workflow for a "build me a floating
temple" request:

1. Plan the structure mentally (platform, columns, roof, waterfalls).
2. Compose `Session.add(...)` calls with shapes from `schematica.shapes` and
   blocks from the registry.
3. Use procedural helpers (`apply_terrain`, `apply_tree`) for naturalistic
   fill, then layer bespoke geometry on top.
4. Run `preview` and inspect file sizes / counts; iterate with `undo`/`redo`.
5. `export` to `.schem` and hand the file to the user.

The toolkit provides the primitives; the agent provides the design.
