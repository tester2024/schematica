# Workflow guide: CLI vs code vs inline script

This document defines the agent's decision framework for choosing between the
three execution modes, with advanced recipes for each. **Read this before
building anything.**

## The three execution modes

| Mode | When | How | Pros | Cons |
|---|---|---|---|---|
| **CLI script** | Simple builds: <15 commands, only primitives in the command table | Write `.txt`, run `python -m schematica --script file.txt` | No Python boilerplate, validation layer catches mistakes, easy to verify | Limited to registered commands, no loops/conditionals, no procedural gen |
| **Python script** | Complex builds: loops, conditionals, procedural gen, custom shapes, mesh import | Write `.py`, run `python script.py` with `PYTHONPATH=scripts` | Full toolkit access, all shapes, all generators, arbitrary logic | More boilerplate, no auto-validation (must check manually) |
| **Inline `-c`** | One-liners, quick experiments, piping into export | `python -c "..."` with `PYTHONPATH=scripts` | Fastest, no temp file | Hard to read, no error recovery, limited to one expression block |

## Decision tree (follow in order)

1. **Can the build be expressed with only these commands?**
   `session.new, add.box, add.hbox, add.sphere, add.hsphere, add.cylinder,
   add.hcylinder, add.dome, add.hdome, add.cone, add.ellipsoid,
   add.hellipsoid, add.pyramid, add.torus, add.helix, add.arch,
   add.staircase, add.spiral, add.line, add.wedge, add.plane,
   subtract.box, subtract.sphere, subtract.cylinder, subtract.dome,
   subtract.pyramid, paint.box, paint.sphere, replace, fill, clear,
   mirror, rotate, undo, redo, stats, preview, export, save, load`
   → **YES → use CLI script** (mode 1). It's the fastest and gets validation.

2. **Does the build need loops, conditionals, math, or procedural generation?**
   (e.g. "place 20 trees at random positions", "for each floor add a window
   ring", "apply Perlin terrain then carve rivers")
   → **YES → use Python script** (mode 2).

3. **Is this a quick one-shot test or a single expression?**
   → **YES → use inline `-c`** (mode 3).

4. **Does the build need a custom shape not in the toolkit?**
   (e.g. a fractal, a custom mesh, a WFC pattern)
   → **Python script** that implements the `Shape` protocol and feeds it to
   `session.add`.

5. **Does the build need to import an OBJ/STL mesh?**
   → **Python script** using `schematica.shapes.mesh.load_mesh`.

**Default**: when in doubt, use **CLI script**. It's the mode with the most
guardrails. Only escalate to Python when the CLI can't express what's needed.

## Mode 1: CLI script (preferred for simple builds)

### Template

```
session.new size=WxHxD version=1.20.1
# ... add/subtract/paint commands ...
stats
preview out_dir=previews
export path=build.schem
```

### Advanced CLI recipe: castle keep

```
session.new size=32x32x32 version=1.20.1
# foundation
add.box frm=0,0,0 to=31,0,31 block=minecraft:stone
# walls (hollow box)
add.box frm=2,1,2 to=29,12,29 block=minecraft:stone hollow=true
# corner towers
add.cylinder center=2,1,2 r=2 h=16 block=minecraft:stone
add.cylinder center=29,1,2 r=2 h=16 block=minecraft:stone
add.cylinder center=2,1,29 r=2 h=16 block=minecraft:stone
add.cylinder center=29,1,29 r=2 h=16 block=minecraft:stone
# tower roofs
add.dome center=2,17,2 r=2 block=minecraft:purple_stained_glass
add.dome center=29,17,2 r=2 block=minecraft:purple_stained_glass
add.dome center=2,17,29 r=2 block=minecraft:purple_stained_glass
add.dome center=29,17,29 r=2 block=minecraft:purple_stained_glass
# gate arch
subtract.box frm=14,1,2 to=17,5,2
add.arch center=15,6,2 z0=2 z1=2 r=3 block=minecraft:stone
# interior staircase
add.staircase corner=4,1,4 y1=12 step_width=2 step_depth=1 axis=x block=minecraft:oak_planks
# windows
subtract.box frm=6,6,2 to=7,8,2
subtract.box frm=24,6,2 to=25,8,2
subtract.box frm=6,6,29 to=7,8,29
subtract.box frm=24,6,29 to=25,8,29
# battlements (merlons) on walls
add.box frm=2,12,2 to=29,13,2 block=minecraft:stone hollow=true
replace src=minecraft:stone dst=minecraft:cobblestone
stats
preview out_dir=castle_previews
export path=castle.schem
```

### Advanced CLI recipe: floating island with waterfall

```
session.new size=48x32x48 version=1.20.1
# island base (dome, upside down via mirror after)
add.dome center=24,16,24 r=12 block=minecraft:dirt
# mirror the dome to make a full sphere, then keep lower half
add.sphere center=24,16,24 r=12 block=minecraft:dirt hollow=true
subtract.sphere center=24,16,24 r=10
# grass top
paint.box frm=12,16,12 to=36,16,36 block=minecraft:grass_block
# waterfalls (cylinders from island edge down)
add.cylinder center=12,4,24 r=1 h=12 block=minecraft:glass
add.cylinder center=36,4,24 r=1 h=12 block=minecraft:glass
replace src=minecraft:glass dst=minecraft:sea_lantern
# tree trunk
add.cylinder center=24,17,24 r=1 h=6 block=minecraft:oak_log
add.sphere center=24,24,24 r=4 block=minecraft:glass
replace src=minecraft:glass dst=minecraft:oak_planks
stats
export path=island.schem
```

## Mode 2: Python script (for complex/procedural builds)

### Template

```python
#!/usr/bin/env python
"""Build description here."""
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere, Cylinder, Dome
from schematica.shapes.boolean import Union, Subtract
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview

s = Session.new((32, 32, 32), version="1.20.1")
# ... build logic ...
write_sponge(s.grid, "build.schem")
preview(s.grid, "previews")
print(s.stats())
```

### Advanced Python recipe: village with procedural placement

```python
import random
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Cylinder, Dome, Staircase
from schematica.shapes.boolean import Union, Subtract
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview

s = Session.new((64, 32, 64), version="1.20.1")
rng = random.Random(42)

# terrain
from schematica.generators.templates import apply_terrain
apply_terrain(s, seed=42, amplitude=4)

# village: 8 houses at random positions
for i in range(8):
    x = rng.randint(4, 56)
    z = rng.randint(4, 56)
    w = rng.randint(5, 8)
    d = rng.randint(5, 8)
    h = rng.randint(4, 6)
    # walls
    s.add(Box(x, 10, z, x + w, 10 + h, z + d), "minecraft:oak_planks")
    s.subtract(Box(x + 1, 10, z + 1, x + w - 1, 10 + h, z + d - 1))
    # roof
    s.add(Dome(x + w / 2, 10 + h, z + d / 2, max(w, d) / 2 + 1), "minecraft:bricks")
    # door
    s.subtract(Box(x + w // 2, 10, z, x + w // 2, 11, z))

# paths between houses (simple stone lines)
for i in range(4, 60, 3):
    s.paint(Box(i, 9, 30, i, 9, 30), "minecraft:cobblestone")

write_sponge(s.grid, "village.schem")
preview(s.grid, "village_previews")
print(s.stats())
```

### Advanced Python recipe: custom shape (fractal tree)

```python
import numpy as np
from schematica.shapes.base import Shape
from schematica.session.session import Session
from schematica.export.sponge import write_sponge

class FractalBranch(Shape):
    """A recursive L-system-style branch."""
    def __init__(self, x, y, z, length, angle, depth, seed=0):
        self.x, self.y, self.z = x, y, z
        self.length = length
        self.angle = angle
        self.depth = depth
        self.seed = seed

    def mask(self, shape):
        m = np.zeros(shape, dtype=bool)
        rng = np.random.default_rng(self.seed)
        self._grow(m, self.x, self.y, self.z, self.length, self.angle, self.depth, rng)
        return m

    def _grow(self, m, x, y, z, length, angle, depth, rng):
        if depth <= 0 or length < 1:
            return
        dx = int(length * np.cos(angle))
        dz = int(length * np.sin(angle))
        for t in np.linspace(0, 1, int(length)):
            px, py, pz = int(x + dx * t), int(y + t * length), int(z + dz * t)
            if 0 <= px < m.shape[0] and 0 <= py < m.shape[1] and 0 <= pz < m.shape[2]:
                m[px, py, pz] = True
        ny = int(y + length)
        if 0 <= ny < m.shape[1]:
            for da in (-0.6, 0.6):
                na = angle + da + rng.uniform(-0.2, 0.2)
                self._grow(m, int(x + dx), ny, int(z + dz),
                           length * 0.7, na, depth - 1, rng)

s = Session.new((32, 32, 32))
tree = FractalBranch(16, 0, 16, 8, 0.3, 4, seed=42)
s.add(tree, "minecraft:oak_log")
write_sponge(s.grid, "fractal_tree.schem")
```

### Advanced Python recipe: noise-deformed terrain

```python
from schematica.session.session import Session
from schematica.shapes.heightmap import Heightmap
from schematica.shapes.transforms import NoiseDeformed
from schematica.generators.noise import perlin2d
from schematica.export.sponge import write_sponge
import numpy as np

s = Session.new((48, 24, 48))
n = perlin2d((48, 48), scale=0.05, octaves=4, seed=42)
heights = np.rint(8 + n * 12).astype(np.int32)
hm = Heightmap(heights=heights, y_base=0, solid_below=True)
# Deform the edges for a more natural look
deformed = NoiseDeformed(hm, amplitude=3, scale=0.1, seed=99)
s.add(deformed, "minecraft:grass_block")
write_sponge(s.grid, "deformed_terrain.schem")
```

### Advanced Python recipe: mesh import + voxelization

```python
from schematica.session.session import Session
from schematica.shapes.mesh import load_mesh
from schematica.shapes.boolean import Union, Subtract
from schematica.shapes.primitives import Box
from schematica.export.sponge import write_sponge

s = Session.new((64, 64, 64))
# Import a 3D model and voxelize it
castle = load_mesh("castle.obj", origin=(0, 0, 0), scale=1.0)
s.add(castle, "minecraft:stone")
# Carve a doorway
s.subtract(Box(10, 0, 0, 14, 8, 2))
write_sponge(s.grid, "castle_from_mesh.schem")
```

## Mode 3: Inline `-c` (quick experiments)

```bash
# One-liner: 8³ stone cube, export
PYTHONPATH=scripts python -c "
from schematica.session.session import Session
from schematica.shapes.primitives import Box
from schematica.export.sponge import write_sponge
s = Session.new((8, 8, 8))
s.add(Box(0, 0, 0, 7, 7, 7), 'minecraft:stone')
write_sponge(s.grid, 'cube.schem')
print('done')
"
```

```bash
# Quick stats check on an existing session
PYTHONPATH=scripts python -c "
from schematica.session.session import Session
s = Session.load('build.schematica')
print(s.stats())
"
```

## Hybrid workflow: CLI for structure, Python for detail

The most powerful pattern: build the structural shell with the CLI (fast,
validated), save the session, then load it in Python for procedural detail.

**Step 1 — CLI script `structure.txt`:**
```
session.new size=48x48x48 version=1.20.1
add.box frm=0,0,0 to=47,0,47 block=minecraft:stone
add.box frm=2,1,2 to=45,20,45 block=minecraft:stone hollow=true
add.staircase corner=4,1,4 y1=20 step_width=3 step_depth=2 axis=x block=minecraft:oak_planks
save path=structure.schematica
```

**Step 2 — Python script `detail.py`:**
```python
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere
from schematica.generators.templates import apply_tree
from schematica.export.sponge import write_sponge
import random

s = Session.load("structure.schematica")
rng = random.Random(42)

# Add windows at regular intervals
for x in range(6, 44, 6):
    s.subtract(Box(x, 5, 2, x + 2, 8, 2))
    s.subtract(Box(x, 5, 45, x + 2, 8, 45))
    s.subtract(Box(2, 5, x, 2, 8, x + 2))
    s.subtract(Box(45, 5, x, 45, 8, x + 2))

# Add decorative pillars
for x, z in [(10, 10), (38, 10), (10, 38), (38, 38)]:
    s.add(Box(x, 1, z, x, 20, z), "minecraft:quartz_block")

# Trees on the roof
for _ in range(5):
    x = rng.randint(5, 42)
    z = rng.randint(5, 42)
    apply_tree(s, x=x, z=z, height=5)

write_sponge(s.grid, "detailed.schem")
print(s.stats())
```

## Sanity checks after building

Regardless of mode, confirm the build is non-empty before delivering:

1. Check `stats` output: `solid > 0` (non-empty build).
2. Run `preview` and confirm PNG files exist with size > 1KB.
3. Confirm the `.schem` file exists and is > 100 bytes.
4. For Python scripts, add assertions:
   ```python
   assert s.grid.nonempty_count() > 0, "build is empty!"
   from pathlib import Path
   p = write_sponge(s.grid, "build.schem")
   assert Path(p).stat().st_size > 100, "schem file too small"
   ```

## Common pitfalls by mode

### CLI pitfalls
- Backslashes in paths → use forward slashes.
- Inverted bounds (`frm > to`) → validator catches this now.
- Forgetting `session.new` → operates on default 32³ grid.
- No loops → if you need repetition, switch to Python.

### Python pitfalls
- Not validating block names → typos silently create palette entries that
  never match. Use `registry.validate(block)` or `registry.resolve(block)`.
- Not checking bounds → shapes clip silently. Check coords before construction.
- Using `add(shape, AIR)` → use `subtract(shape)` instead.
- Not pinning seeds → procedural gen becomes non-reproducible.

### Inline pitfalls
- Hard to debug → keep to one-liners only.
- No error recovery → a single exception kills the whole command.
- Quoting hell on Windows → prefer a temp `.py` file for anything >1 line.