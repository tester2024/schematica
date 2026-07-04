# CLI reference

## Running

The toolkit lives under `scripts/`. Set `PYTHONPATH` to `scripts/` or
`pip install -e scripts/` first.

```bash
python -m schematica                    # interactive REPL
python -m schematica --script build.txt # batch run
```

In the REPL, type `help` to list commands, `exit` to quit.

## Syntax

- Commands are `dotted.name` (e.g. `add.box`) or space-separated alias
  (`add box` -> `add.box`).
- Arguments are `key=value` or positional (matched in spec order).
- Strings with spaces or commas: quote them, e.g. `block="minecraft:oak_log[axis=y]"`.
- Paths: use forward slashes (shlex treats `\` as escape).
- Booleans: `true/false/1/0/yes/no`.
- Coords: `x,y,z` or `x y z` (quoted).
- Sizes: `WxHxD` or `W,H,D`.
- Comments: lines starting with `#` are skipped in `--script` mode.

## Command table

| Command | Args | Default | Notes |
|---|---|---|---|
| `session.new` | `size`, `version`=`1.20.1`, `fill`=`minecraft:air` | | reset grid |
| `add.box` | `frm`, `to`, `block`=`minecraft:stone`, `hollow`=`false` | | inclusive bounds |
| `add.hbox` | `frm`, `to`, `block`=`minecraft:stone` | | hollow box (walls only) |
| `add.sphere` | `center`, `r`, `block`=`minecraft:stone`, `hollow`=`false` | | |
| `add.hsphere` | `center`, `r`, `block`=`minecraft:stone` | | hollow sphere (shell only) |
| `add.cylinder` | `center`, `r`, `h`, `block`=`minecraft:stone`, `hollow`=`false` | | vertical (y); for `axis="x"\|"z"` use Python with `start`/`end` |
| `add.hcylinder` | `center`, `r`, `h`, `block`=`minecraft:stone` | | hollow cylinder (tube only) |
| `add.dome` | `center`, `r`, `block`=`minecraft:stone`, `hollow`=`false` | | upper hemisphere |
| `add.hdome` | `center`, `r`, `block`=`minecraft:stone` | | hollow dome (shell only) |
| `add.cone` | `center`, `r_base`, `y_base`, `y_apex`, `block`=`minecraft:stone` | | radius shrinks to apex |
| `add.ellipsoid` | `center`, `rx`, `ry`, `rz`, `block`=`minecraft:stone`, `hollow`=`false` | | anisotropic sphere |
| `add.hellipsoid` | `center`, `rx`, `ry`, `rz`, `block`=`minecraft:stone` | | hollow ellipsoid (shell only) |
| `add.pyramid` | `center`, `base_half`, `y_base`, `y_apex`, `block`=`minecraft:stone` | | square pyramid |
| `add.torus` | `center`, `R`, `r`, `block`=`minecraft:stone` | | R=major, r=minor |
| `add.helix` | `center`, `r`, `y0`, `y1`, `turns`=`3.0`, `block`=`minecraft:stone` | | spiral curve |
| `add.arch` | `center`, `z0`, `z1`, `r`, `thickness`=`1.0`, `block`=`minecraft:stone` | | semicircular arch |
| `add.staircase` | `corner`, `y1`, `step_width`=`3`, `step_depth`=`2`, `step_height`=`1`, `axis`=`x`, `block`=`minecraft:stone` | | straight stairs |
| `add.spiral` | `center`, `r_inner`, `r_outer`, `y0`, `y1`, `turns`=`2.0`, `block`=`minecraft:stone` | | flat spiral extruded |
| `add.line` | `frm`, `to`, `block`=`minecraft:stone` | | 1-voxel Bresenham line |
| `add.wedge` | `frm`, `to`, `split_axis`=`x`, `block`=`minecraft:stone` | | triangular prism |
| `add.plane` | `axis`, `coord`, `thickness`=`1`, `block`=`minecraft:stone` | | axis-aligned slab |
| `subtract.box` | `frm`, `to` | | carve air |
| `subtract.sphere` | `center`, `r` | | carve a sphere |
| `subtract.cylinder` | `center`, `r`, `h` | | carve a cylinder |
| `subtract.dome` | `center`, `r` | | carve a dome |
| `subtract.pyramid` | `center`, `base_half`, `y_base`, `y_apex` | | carve a pyramid |
| `paint.box` | `frm`, `to`, `block` | | repaint existing solids |
| `paint.sphere` | `center`, `r`, `block` | | repaint existing solids |
| `replace` | `src`, `dst` | | global find/replace |
| `replace.bulk` | `mapping` | | bulk replacements, e.g. `stone=andesite,dirt=grass_block` |
| `replace.by_name` | `src_name`, `dst` | | replace all blocks with a name, ignoring state |
| `replace.pattern` | `src`, `dst`, `neighbours` | | replace only when neighbor rules match |
| `retexture` | `property`, `value`, `name` | | set a blockstate property where supported |
| `retexture.map` | `property`, `mapping`, `name` | | remap blockstate values, e.g. `x=y,y=z,z=x` |
| `texture.palette` | `frm`, `to`, `blocks`, `weights`, `noise`, `scale`, `seed` | | noise-driven material mix on existing solids |
| `fill` | `block` | | fill entire grid |
| `clear` | | | all air |
| `mirror` | `axis`=`x\|y\|z` | | |
| `rotate` | `times`, `axes`=`xy` | | 90° * times |
| `clone.translate` | `frm`, `to`, `offset`, `count`=`1`, `include_air`=`false` | | copy a box by offset, repeated |
| `clone.cardinal` | `frm`, `to`, `center`, `include_air`=`false` | | copy a box to other 3 Y-axis cardinal rotations |
| `undo` | | | |
| `redo` | | | |
| `stats` | | | shape/volume/solid/palette + marker/region counts |
| `report` | | | palette compatibility report across export formats |
| `marker` | `name`, `x`, `y`, `z`, `kind`=`point` | | add a named marker (any kind label) |
| `region` | `name`, `corner_x`, `corner_y`, `corner_z`, `sx`, `sy`, `sz`, `kind`=`area` | | add a named bounding-box annotation |
| `export.markers` | `path` | | write markers+regions JSON |
| `preview` | `out_dir`=`previews` | | top/front/right/iso PNGs |
| `preview.region` | `corner_x`, `corner_y`, `corner_z`, `sx`, `sy`, `sz`, `out_dir`=`previews` | | cropped sub-region render |
| `export` | `path` | | Sponge .schem |
| `export.mcedit` | `path` | | legacy MCEdit .schematic |
| `export.litematic` | `path` | | Litematica .litematic |
| `save` | `path` | | .schematica session JSON |
| `load` | `path` | | restore session |
| `generate.terrain` | `seed`, `amplitude`, `scale`, `top`, `filler` | | Perlin terrain |
| `generate.tree` | `at`, `height`, `trunk`, `leaves` | | tree template |
| `generate.wfc` | `frm`, `to`, `tileset`, `seed` | | WFC fill |
| `constraint.add` | `kind`, `a`=``, `b`=`` | | add constraint kind=height a=10 / kind=ban a=minecraft:bedrock / kind=symmetry a=x / kind=bounds a=0,0,0 b=7,7,7 / kind=palette a=256 / kind=solid_ratio a=0.1 b=0.9 / kind=max_count a=minecraft:stone b=1000 |
| `constraint.check` | | | check all constraints against current grid |
| `validate` | `path`, `fmt`=`sponge` | | validate export round-trip |
| `validate.all` | `dir_path` | | validate all 3 formats |
| `substitutions` | | | show suggested legacy substitutions for unmapped blocks |
| `apply.substitutions` | | | replace unmapped blocks with legacy-compatible substitutes |
| `paint.gradient` | `frm`, `to`, `blocks`, `axis`=`y`, `blend`=`0.0`, `seed`=`0` | | paint linear gradient along axis |
| `edge.wear` | `blocks`, `min_exposure`=`1`, `max_exposure`=`6`, `noise`=`0.0`, `seed`=`0` | | weather exposed surfaces |
| `surface.scatter` | `block`, `density`=`0.1`, `min_exposure`=`1`, `max_exposure`=`6`, `seed`=`0`, `on_blocks`=`` | | scatter block on exposed surfaces |
| `walkable` | `x`, `y`, `z` | | check if position is walkable |
| `connected` | `a`, `b` | | check walkability between two points |
| `reachable` | `x`, `y`, `z` | | flood-fill reachable walkable area |
| `path` | `a`, `b` | | shortest walking path |
| `help` | | | list commands (REPL only) |
| `exit` | | | quit (REPL only) |

## Python-only features (not in the CLI table)

The CLI is a thin shell over the Session API. These Phase 12 additions are only
reachable from Python because they need shapes or composition the command
table cannot express. See `references/workflow_guide.md` for recipes and
`references/generators.md` for the SDF/Bezier/SVG/symmetry/resample reference.

- `SmoothUnion` / `SmoothIntersect` / `SmoothSubtract` — SDF smooth blending.
- `BezierCurve` — quadratic / cubic 3D Bezier tubes.
- `Rotated(angle_deg=...)` — arbitrary-angle rotation (not just 90° multiples).
- `extrude_polygon("M 0 0 H 10 V 10 H 0 Z", ...)` — SVG path `d`-string voxelization.
- `Session.enable_symmetry(axis, center)` / `disable_symmetry()` — live mirror.
- `Session.resample_subregion(frm, to, new_size, block, dest_origin=None)`.
- `Cone(..., axis="x"|"z")` and `Dome(..., axis="x"|"z")` — horizontal cones /
  wall-mounted domes (the CLI's `add.cone` / `add.dome` are Y-axis only).
- `Arch(..., plane="xy"|"xz"|"yz")` — arches in any coordinate plane (the CLI's
  `add.arch` is XY-plane only).
- `Cylinder(..., start=..., end=..., axis="x"|"z")` — clearer along-axis extent
  for non-Y cylinders (the CLI's `add.cylinder` is Y-axis only).
- `Session.add(shape, block, hollow=True, ...)` — kwargs delegation forwards
  extra kwargs to the shape's dataclass fields via `dataclasses.replace`.

## Examples

```
session.new size=32x32x32 version=1.20.1
add.box frm=0,0,0 to=31,0,31 block=minecraft:stone
add.box frm=0,0,0 to=31,8,31 block=minecraft:dirt
replace src=minecraft:dirt dst=minecraft:grass_block
add.box frm=2,1,2 to=6,5,6 block=minecraft:oak_planks hollow=true
add.sphere center=16,16,16 r=8 block=minecraft:glass hollow=true
add.cylinder center=16,1,16 r=1 h=10 block=minecraft:oak_log
subtract.box frm=14,9,14 to=18,12,18
undo
redo
stats
clone.translate frm=2,1,2 to=6,5,6 offset=10,0,0 count=2
clone.cardinal frm=20,1,20 to=28,8,28 center=16,16
export path=build.schem
preview out_dir=previews
save path=build.schematica
```

## Extending the CLI

Add a `CommandSpec` in `scripts/schematica/session/commands.py`:

```python
def cmd_my_op(s: Session, x: int, block: str = "minecraft:stone") -> str:
    ...
    return "done"

COMMANDS["my.op"] = CommandSpec(
    "my.op",
    (ArgSpec("x", "int"), ArgSpec("block", "block", default="minecraft:stone", required=False)),
    cmd_my_op,
    "does X",
)
```

The dispatch in `cli/repl.py` auto-binds positional args and coerces types via
`_coerce(value, kind)` where kind ∈ `int, float, bool, coords, block, str`.
