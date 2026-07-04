# Agent guide: driving the Schematica CLI

This document teaches an AI agent how to use the Schematica CLI to build
Minecraft schematics. It is written for *execution*, not for humans.

## Mental model

The CLI is a **stateful session editor**. Every command mutates one `Session`
holding a 3D voxel grid. The grid starts as air; you add/subtract shapes, then
export. There is no persistent process — `python -m schematica --script FILE`
runs one script non-interactively and exits. The Session lives only for the
duration of the script. To persist work, use `save`; to resume, use `load`.

**Execution pattern (always):**

1. Write a `.txt` script file with one command per line.
2. Run `python -m schematica --script <path>` with `PYTHONPATH` set to the
   Schematica project root.
3. Parse stdout: each `> line` echo is followed by a status line. Check for
   `error:` or `missing arg:` to detect failures.
4. Read produced artifacts (`.schem`, PNGs, `.schematica` session) from disk.

Do **not** try to use the interactive REPL (`python -m schematica` without
`--script`) — it blocks on stdin and will hang. Always use `--script`.

## The mandatory environment

The Python toolkit lives under `scripts/` inside the skill root. Set
`PYTHONPATH` to the `scripts/` directory (or `pip install -e scripts/` first):

```bash
# Windows PowerShell
$env:PYTHONPATH = "<skill-root>/scripts"
python -m schematica --script <script.txt>

# POSIX
PYTHONPATH=<skill-root>/scripts python -m schematica --script <script.txt>
```

If installed via `pip install -e scripts/`, `PYTHONPATH` is unnecessary — just
run `python -m schematica --script <path>` from anywhere.

## Command cheat sheet (memorize this)

| Intent | Command |
|---|---|
| Start fresh | `session.new size=WxHxD version=V` |
| Fill a box | `add.box frm=x,y,z to=x,y,z block=B` |
| Hollow box (walls only) | `add.box ... hollow=true` |
| Sphere | `add.sphere center=x,y,z r=N block=B` |
| Hollow sphere (shell) | `add.sphere ... hollow=true` |
| Vertical pillar | `add.cylinder center=x,y,z r=N h=N block=B` |
| Carve space (set air) | `subtract.box frm=x,y,z to=x,y,z` |
| Swap all of one block | `replace src=B dst=B` |
| Fill whole grid | `fill block=B` |
| Clear to air | `clear` |
| Flip | `mirror axis=x\|y\|z` |
| Rotate 90° steps | `rotate times=N axes=xy\|xz\|yz` |
| Repeat a source box | `clone.translate frm=A to=B offset=dx,dy,dz count=N` |
| Four-way map symmetry | `clone.cardinal frm=A to=B center=x,z` |
| Undo / redo | `undo` / `redo` |
| Report state | `stats` |
| Render PNGs | `preview out_dir=DIR` |
| Write Sponge schem | `export path=FILE.schem` |
| Write legacy schematic | `export.mcedit path=FILE.schematic` |
| Write Litematica | `export.litematic path=FILE.litematic` |
| Persist session | `save path=FILE.schematica` |
| Resume session | `load path=FILE.schematica` |
| Generate terrain | `generate.terrain seed=N amplitude=N` |
| Generate tree | `generate.tree at=x,y,z height=N` |
| Generate WFC patch | `generate.wfc frm=x,y,z to=x,y,z tileset=mossy_ruins` |

## Argument syntax rules (critical)

1. **All args are `key=value` or positional.** `add.box frm=0,0,0 to=2,2,2 block=minecraft:stone` and `add.box 0,0,0 2,2,2 minecraft:stone` both work.
2. **Coords**: `x,y,z` (commas, no spaces) or `x y z` (quoted). Never `(x,y,z)` with parens alone — the parser strips parens but commas alone are safest.
3. **Size**: `WxHxD` (lowercase x) or `W,H,D`.
4. **Blocks**: `minecraft:stone` or bare `stone` (auto-prefixed). Blockstate: `minecraft:oak_log[axis=y]` — quote it if it contains `=`, else the parser treats it as a top-level key.
5. **Booleans**: `true/false/1/0/yes/no`.
6. **Numbers**: `int` and `float` are coerced from the string.
7. **Paths**: use forward slashes (`previews/out`), not backslashes — `\` is shlex's escape char and silently eats the next character. This is the #1 agent bug.
8. **Defaults**: `block` defaults to `minecraft:stone`; `hollow` defaults to `false`; `version` defaults to `1.20.1`; `out_dir` defaults to `previews`.

## Reading command output

Every command prints two lines:
```
> <echoed command>
<status>
```
Status conventions:
- Success: a short description like `box 0,0,0->2,2,2 minecraft:stone` or `replaced 256 minecraft:dirt->minecraft:grass_block`.
- Failure: starts with `error:` (exception in handler) or `missing arg:` (required arg not provided) or `unknown command:` (bad name).

**Recovery rules:**
- `missing arg: X` → re-issue the command with `X=value`.
- `error: "Unknown block '...' for version V"` → the block isn't in the fallback catalog; either pick a common vanilla block, or ensure the `minecraft_data/` submodule is vendored for the full catalog.
- `error: expected x,y,z got <s>` → coords were malformed; use `a,b,c` form.
- `unknown command: X` → check the dotted name (e.g. `subtract.box` not `subtract`).

## Coordinate system

- `x` = width (0..sx-1), `y` = height (0..sy-1, up), `z` = depth (0..sz-1).
- `grid[x, y, z]`. Box bounds are **inclusive** on both ends.
- Sphere `center=(cx,cy,cz)` uses float coords; `r` is a float radius.
- Cylinder `center=(x,y,z)` uses the (x, z) as the center column and `y` as the base; `h` is the height in blocks up from that base.

## A complete worked example (copy-paste ready)

Goal: a 16³ stone plaza with grass top, a hollow oak hut, a glass dome, and a log pillar, with a carved tunnel.

```
session.new size=16x16x16 version=1.20.1
add.box frm=0,0,0 to=15,0,15 block=minecraft:stone
add.box frm=0,1,0 to=15,1,15 block=minecraft:dirt
replace src=minecraft:dirt dst=minecraft:grass_block
add.box frm=2,2,2 to=4,5,4 block=minecraft:oak_planks hollow=true
add.sphere center=8,10,8 r=4 block=minecraft:glass hollow=true
add.cylinder center=8,2,8 r=1 h=6 block=minecraft:oak_log
subtract.box frm=7,6,7 to=9,9,9
stats
preview out_dir=previews
export path=build.schem
save path=build.schematica
```

Real output (captured from this script):

```
> session.new size=16x16x16 version=1.20.1
new session 16x16x16 v1.20.1
> add.box frm=0,0,0 to=15,0,15 block=minecraft:stone
box 0,0,0->15,0,15 minecraft:stone
> add.box frm=0,1,0 to=15,1,15 block=minecraft:dirt
box 0,1,0->15,1,15 minecraft:dirt
> replace src=minecraft:dirt dst=minecraft:grass_block
replaced 256 minecraft:dirt->minecraft:grass_block
> add.box frm=2,2,2 to=4,5,4 block=minecraft:oak_planks hollow=true
box 2,2,2->4,5,4 minecraft:oak_planks
> add.sphere center=8,10,8 r=4 block=minecraft:glass hollow=true
sphere @ 8,10,8 r=4.0
> add.cylinder center=8,2,8 r=1 h=6 block=minecraft:oak_log
cylinder 8,2,8 r=1.0 h=6
> subtract.box frm=7,6,7 to=9,9,9
subtracted box 7,6,7->9,9,9
> stats
shape=[16, 16, 16] vol=4096 solid=691 palette=7
> preview out_dir=previews
previews: preview_top.png, preview_front.png, preview_right.png, preview_iso.png
> export path=build.schem
exported build.schem
> save path=build.schematica
saved build.schematica
```

## Error and warning codes (the validation layer)

Every command runs through a validation layer before execution. **Errors**
refuse the command (nothing happens to the session). **Warnings** proceed but
print on `! `-prefixed lines after the status. Always check stdout for both.

### Error codes (command refused)

| Code | Trigger | Fix |
|---|---|---|
| `inverted_bounds` | `add.box`/`subtract.box`/`add.cone`/`add.pyramid`/`add.helix`/`add.spiral` with `frm > to` or `y_base >= y_apex` | Swap so each axis in `frm` ≤ `to`, or `y_base < y_apex` |
| `negative_radius` | Any shape with `r < 0` or `r_base < 0` | Use `r >= 0` (or `r > 0` for visible volume) |
| `nonpositive_height` | `add.cylinder` with `h <= 0` | Use `h >= 1` |
| `nonpositive_step` | `add.staircase` with `step_width/depth/height <= 0` | Use positive step dimensions |
| `bad_axis` | `mirror axis=q`, `add.plane axis=q`, `add.wedge split_axis=y` | Use valid axis values (x/y/z for most; x/z for wedge) |
| `bad_axes` | `rotate axes=XY` (uppercase or invalid pair) | Use lowercase `xy`, `xz`, or `yz` |
| `empty_path` | `export path=` or `save path=` | Provide a non-empty path |
| `bad_state_value` | `oak_log[axis=q]` (axis not x/y/z) | Use `axis=x`, `axis=y`, or `axis=z` |
| `unknown_block` | Block not in the catalog for this version | Use a block from the fallback list, or vendor `minecraft_data/` |
| `bad_coords` | `frm=1,2` (not 3 numbers) | Provide exactly 3 comma-separated ints |
| `bad_size` | `session.new size=16` (single number) | Use `WxHxD` or `W,H,D` form |
| `nonpositive_size` | `session.new size=0x8x8` | All axes must be ≥ 1 |
| `empty_block` | `add.box ... block=` | Provide a block name |
| `missing_file` | `load path=missing.json` | Check the path exists first |
| `missing arg: NAME` | Required arg not provided | Re-issue with `NAME=value` |
| `unknown command: X` | Command name not in table | Check `help` or the command table |

### Warning codes (command ran, but flagged)

| Code | Meaning | Recommended action |
|---|---|---|
| `zero_radius` | `r=0` yields at most 1 voxel | Intentional? If not, increase `r` |
| `hollow_tiny` | `hollow=true` with `r<1` collapses to nothing | Increase `r` or drop `hollow` |
| `hollow_zero` | `hollow=true` box with zero thickness on some axis | Increase box size or drop `hollow` |
| `partly_out_of_bounds` | Box extends past grid edge; will be clipped | Intentional clipping is fine; otherwise resize |
| `out_of_bounds` | Box/plane entirely outside grid; no effect | Fix coords or use `session.new` with bigger size |
| `center_outside` | Sphere/cylinder center is outside the grid | Move center inside the grid |
| `fill_air` | `fill block=minecraft:air` = same as `clear` | Use `clear` for intent clarity |
| `add_air` | `add.* block=minecraft:air` erases voxels | Use `subtract.*` to carve intentionally |
| `replace_same` | `replace src=X dst=X` is a no-op | Fix `src` or `dst` |
| `zero_turns` | `add.helix turns<=0` → vertical line | Increase `turns` for a spiral |
| `zero_thickness` | `add.arch thickness<=0` → invisible | Increase `thickness` |
| `torus_inverted_radii` | `add.torus r > R` → self-intersecting | Ensure minor `r` ≤ major `R` |
| `spiral_inverted_radii` | `add.spiral r_outer < r_inner` → shrinks inward | Swap or fix radii |
| `bad_extension` | `export path=foo` (no `.schem`) | Add `.schem` extension |
| `empty_outdir` | `preview out_dir=` | Provide a directory or accept the default |
| `backslash_path` | Line contains `\` which shlex may mangle | Use forward slashes in all paths |
| `huge_size` | Grid > 512 on any axis | May be slow; consider smaller grids |
| `unknown_version` | Requested MC version has no `blocks.json` | Vendor `minecraft_data/` or accept fallback |

### Output format (memorize this)

Success with no warnings:
```
> add.box frm=0,0,0 to=3,3,3 block=minecraft:stone
box 0,0,0->3,3,3 minecraft:stone
```

Error (command refused):
```
> add.box frm=3,3,3 to=2,2,2
error: [inverted_bounds] box frm=(3, 3, 3) to=(2, 2, 2) has inverted bounds; swap frm/to so each axis in frm <= to
```

Warning (command ran):
```
> add.sphere center=4,4,4 r=0 block=minecraft:stone
sphere @ 4,4,4 r=0.0
! [zero_radius] radius r=0 yields at most a single voxel
```

### Agent decision protocol (always follow this)

1. After every command, scan the status line for `error:` — if present, the
   session was **not** modified. Read the `[code]` and fix per the table above.
2. Scan for `! [code]` lines — these are warnings. If the warning indicates an
   unintended consequence (`add_air`, `replace_same`, `fill_air`, `inverted`-
   `bounds` would-have-been), `undo` immediately and re-issue correctly.
3. Run `stats` after nontrivial edits to confirm `solid` count matches
   expectations. A `solid=0` after an intended build means something silently
   failed (often out-of-bounds or inverted bounds that slipped through as
   warnings).
4. Run `preview` before `export` — the PNG file sizes are a sanity check that
   the build is non-empty. A <1KB PNG indicates an empty/near-empty grid.
5. **Never ignore an `error:` line.** Unlike warnings, errors mean the command
   had zero effect; proceeding as if it worked will compound mistakes.

## Common error patterns (real, captured)

```
> add.box
missing arg: frm
> add.sphere center=8,8,8
missing arg: r
> add.box frm=0,0,0 to=5,5,5 block=minecraft:nonexistent_block
error: "Unknown block 'minecraft:nonexistent_block' for version 1.20.1"
> session.new size=bad
error: expected x,y,z got bad
> unknown.command foo=bar
unknown command: unknown.command
> replace src=minecraft:stone
missing arg: dst
> subtract.box frm=0,0,0 to=999,999,999
subtracted box 0,0,0->999,999,999
```

Note the last one: out-of-bounds subtract **does not error** — it just clips to
the grid. The validation layer now emits a `[partly_out_of_bounds]` warning for
this case. Use `stats` afterwards to sanity-check.

## Block catalog caveats

The fallback catalog (used when `minecraft_data/` is not vendored) contains
common structural blocks plus all 16 colors of wool, stained glass, terracotta,
and concrete. Only `oak_log` has a state (`axis`, default `y`) in fallback
mode, so state-heavy blocks like stairs, doors, slabs, fences, and waterlogged
variants still need the full minecraft-data catalog.

Phase 12 enriched the fallback with the quartz family (smooth quartz, quartz
pillar, chiseled quartz, quartz slab/stairs, smooth quartz slab/stairs),
concrete slabs and stairs for all 16 colors, and ~40 stone-variant slabs/stairs
(deepslate, tuff, calcite, blackstone, prismarine, end stone brick, mossy
stone brick/cobblestone, granite, diorite, andesite, polished deepslate). So
common modern detailing now works without a vendored minecraft-data tree.

To get the full vanilla catalog per version, vendor the submodule into the
skill root or set `SCHEMATICA_MINECRAFT_DATA`:
```bash
git clone https://github.com/PrismarineJS/minecraft-data minecraft_data
```
Then `BlockRegistry.for_version("1.20.1")` reads `minecraft_data/data/pc/1.20.1/blocks.json`.

For 1.7-1.12 targets, prefer `export.mcedit` when colored wool/glass/terracotta
metadata matters. Sponge export warns if you pair a pre-1.13 `data_version`
with modern flattened block names.

## Python-only features (not exposed via CLI)

The CLI is a thin shell over the Session API, but some Phase 12 additions are
only reachable from Python because they need shapes or composition the command
table cannot express:

- **SDF smooth blending** — `schematica.shapes.sdf.SmoothUnion` /
  `SmoothIntersect` / `SmoothSubtract` (organic joins with `k`-voxel blend).
- **BezierCurve** — `schematica.shapes.primitives.BezierCurve` (quadratic /
  cubic 3D Bezier tubes).
- **Arbitrary-angle rotation** — `schematica.shapes.transforms.Rotated`
  (any `angle_deg`, not just 90° multiples).
- **SVG path voxelization** — `extrude_polygon("M 0 0 H 10 V 10 H 0 Z", ...)`.
- **Active symmetry decorator** — `Session.enable_symmetry(axis, center)` /
  `disable_symmetry()`.
- **Subregion resampling** — `Session.resample_subregion(frm, to, new_size,
  block, dest_origin=None)`.
- **Cone/Dome `axis` parameter** — `Cone(..., axis="x"|"z")` and
  `Dome(..., axis="x"|"z")` for horizontal cones and wall-mounted domes.
- **Arch `plane` parameter** — `Arch(..., plane="xy"|"xz"|"yz")` for arches in
  any coordinate plane.
- **Cylinder `start`/`end` aliases** — clearer along-axis extent for non-Y
  cylinders (`Cylinder(8, 8, 3, start=2, end=6, axis="x")`).

For these, write a Python script (mode 2 in `workflow_guide.md`):

```python
from schematica.session.session import Session
from schematica.shapes.primitives import BezierCurve
from schematica.shapes.sdf import SmoothUnion, SDFShape
from schematica.shapes.primitives import Sphere, Cylinder

s = Session.new((32, 32, 32))
s.enable_symmetry(axis="x")
s.add(SmoothUnion(Sphere(10, 10, 10, 5), Cylinder(10, 10, 5, 0, 10), k=2.0),
     "minecraft:stone")
s.disable_symmetry()
s.add(BezierCurve((0, 0, 0), (8, 15, 8), (15, 0, 15), thickness=1.0),
     "minecraft:oak_log")
```

## Procedural generation

The CLI exposes `generate.terrain`, `generate.tree`, and `generate.wfc` for
common cases:

```
session.new size=64x32x64 version=1.20.1
generate.terrain seed=42 amplitude=8 scale=0.06
generate.tree at=8,1,8 height=7
generate.wfc frm=20,1,20 to=30,6,30 tileset=mossy_ruins seed=7
preview out_dir=terrain_previews
export path=terrain.schem
```

For custom loops, placement rules, or generator parameters that the CLI does
not expose, switch to the library API from a Python script:

```python
from schematica.session.session import Session
from schematica.generators.templates import apply_terrain, apply_tree

s = Session.new((32, 32, 32))
apply_terrain(s, seed=42, amplitude=6)
apply_tree(s, x=8, z=8, height=7)
apply_tree(s, x=20, z=14, height=5)

from schematica.export.sponge import write_sponge
write_sponge(s.grid, "terrain.schem")
```

Run it with `PYTHONPATH` set to the `scripts/` directory (or after
`pip install -e scripts/`):
```bash
python build_terrain.py
```

## Anti-patterns (do NOT do these)

1. **Do not** invoke `python -m schematica` without `--script` — it blocks on stdin.
2. **Do not** use backslashes in paths (`path=C:\dir\build.schem`) — the validation layer now emits `[backslash_path]`, but shlex may still mangle the path. Use forward slashes.
3. **Do not** assume a command succeeded — always parse stdout for `error:` (refused) and `! [` (warning). Errors mean zero effect; warnings mean it ran but check your intent.
4. **Do not** ignore `! [add_air]` or `! [fill_air]` — these mean you're erasing instead of building. `undo` and use `subtract.*` / `clear` instead.
5. **Do not** ignore `! [replace_same]` — it's a no-op; fix `src` or `dst`.
6. **Do not** edit the grid's numpy array directly from agent code — go through `Session` so `History` captures deltas for undo.
7. **Do not** trust `subtract.box` with huge bounds to "do nothing" — it clips silently; the validator emits `[partly_out_of_bounds]` but the subtract still runs. Verify with `stats`.
8. **Do not** forget `session.new` at the top of every script — without it, you operate on a default 32³ air grid which may surprise you.
9. **Do not** mix REPL-only commands (`help`, `exit`) into `--script` files — `help` prints to stdout (harmless) but `exit` is ignored in script mode (the runner just stops at EOF anyway).
10. **Do not** proceed after an `error:` line without fixing the cause — the session is unchanged, so the next command will build on the pre-error state, compounding confusion.
11. **Do not** use `add.box frm=3,3,3 to=2,2,2` expecting an empty/air box — the validator refuses it with `[inverted_bounds]`. Swap the corners.

## Chaining: save → load → continue

Sessions persist the grid + palette + metadata, **not** the undo history (that
is intentional — history is for the live editing session). Pattern:

```
session.new size=32x32x32
add.box frm=0,0,0 to=31,0,31 block=minecraft:stone
save path=base.schematica
```

Later, in another script:

```
load path=base.schematica
add.sphere center=16,16,16 r=8 block=minecraft:glass
export path=final.schem
```

## Quick decision tree

- User wants a **single static build** → write one script, run once, export.
- User wants to **iterate** on a build → `save` between scripts, `load` to resume.
- User wants **terrain/villages** → use library API (Python script), not CLI.
- User wants **Bedwars / hub quadrant symmetry** → build one quadrant, then use `clone.cardinal frm=A to=B center=x,z`.
- User wants **previews** → always run `preview out_dir=...` last; read PNGs to verify visually (agents can't see them, but the file existing + non-trivial size is a sanity check).
- User wants **MCEdit / legacy 1.8-ish workflow** → use `export.mcedit path=build.schematic`.
- User wants **Litematica** → use `export.litematic path=build.litematic`.
- User wants a **specific MC version** → pass `version=1.21` to `session.new`; ensure `minecraft_data/data/pc/1.21/blocks.json` exists or use fallback common blocks.

## Best practices for code (library API)

When writing Python scripts that use `schematica` directly (not via the CLI),
follow these rules to avoid the same classes of bugs the CLI validator catches:

### 1. Always validate block names before `session.add`
```python
from schematica.blocks.block import Block
from schematica.blocks.registry import BlockRegistry

reg = BlockRegistry.for_version("1.20.1")
block = Block.parse("minecraft:oak_log[axis=y]")
reg.validate(block)            # raises ValueError on unknown state
block = reg.resolve(block)     # fills defaults; safe to use
```
Without this, typos like `minecraft:oak_lof` fail silently inside the session
(they become palette entries that never match anything for replace/count).

### 2. Check shape bounds before constructing
```python
sx, sy, sz = session.grid.shape
if not (0 <= x0 <= x1 < sx and 0 <= y0 <= y1 < sy and 0 <= z0 <= z1 < sz):
    raise ValueError(f"box {x0..x1} out of bounds for grid {session.grid.shape}")
```
`Box` clips silently — a typo'd coordinate yields a smaller box than intended
with no error. Catch it at construction time.

### 3. Never use `add(shape, AIR)` — use `subtract(shape)` instead
```python
# BAD: erases, but looks like "adding"
session.add(Box(0,0,0,3,3,3), Block.parse("minecraft:air"))

# GOOD: intent is explicit
session.subtract(Box(0,0,0,3,3,3))
```

### 4. Pin seeds for reproducibility
```python
apply_terrain(s, seed=42)      # deterministic across runs
```
Without a seed, Perlin noise uses `base=0` by default — always pass an
explicit seed for reproducible builds.

### 5. Check `nonempty_count()` after a batch of edits
```python
before = s.grid.nonempty_count()
s.add(Box(0,0,0,5,5,5), "minecraft:stone")
after = s.grid.nonempty_count()
assert after > before, f"add had no effect: {before} -> {after}"
```
This catches silent no-ops (out-of-bounds masks, inverted bounds, air blocks).

### 6. Use `undo()` defensively after a suspicious edit
```python
s.add(maybe_buggy_shape, "minecraft:stone")
if s.grid.nonempty_count() == 0:
    s.undo()                   # revert the no-op
```

### 7. Compose shapes with boolean ops instead of repeated `add`
```python
# BAD: three separate adds, three history deltas
s.add(Box(0,0,0,5,5,5), "minecraft:stone")
s.add(Sphere(2,2,2,3), "minecraft:stone")
s.add(Cylinder(2,2,2,2,0,5), "minecraft:stone")

# GOOD: one union, one delta, same result
from schematica.shapes.boolean import Union
combined = Union((Box(0,0,0,5,5,5), Sphere(2,2,2,3), Cylinder(2,2,2,2,0,5)))
s.add(combined, "minecraft:stone")
```

### 8. Export then immediately verify the file
```python
from pathlib import Path
p = write_sponge(s.grid, "build.schem")
assert Path(p).exists() and Path(p).stat().st_size > 100
```

### 9. Prefer `Block.parse` over `Block(name=..., states=...)` for string inputs
```python
# BAD: easy to miss a state or misorder
Block("minecraft:oak_log", (("axis", "y"),))

# GOOD: round-trips with the blockstate string format
Block.parse("minecraft:oak_log[axis=y]")
```

### 10. Run `stats()` and inspect before exporting
```python
st = s.stats()
if st["solid"] == 0:
    raise RuntimeError("grid is empty; nothing to export")
if st["palette_size"] > 100:
    print(f"warning: large palette ({st['palette_size']}); may bloat .schem")
```
