# Generators

Procedural and AI generators. Terrain, tree, and WFC helpers are available
through both the library API and CLI commands (`generate.terrain`,
`generate.tree`, `generate.wfc`). Use Python when you need loops, custom
placement rules, or generator parameters that the CLI does not expose.

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
