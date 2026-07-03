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
| `add.cylinder` | `center`, `r`, `h`, `block`=`minecraft:stone`, `hollow`=`false` | | vertical (y) |
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
| `fill` | `block` | | fill entire grid |
| `clear` | | | all air |
| `mirror` | `axis`=`x\|y\|z` | | |
| `rotate` | `times`, `axes`=`xy` | | 90° * times |
| `undo` | | | |
| `redo` | | | |
| `stats` | | | shape/volume/solid/palette |
| `preview` | `out_dir`=`previews` | | top/front/right/iso PNGs |
| `export` | `path` | | Sponge .schem |
| `save` | `path` | | .schematica session JSON |
| `load` | `path` | | restore session |
| `help` | | | list commands (REPL only) |
| `exit` | | | quit (REPL only) |

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