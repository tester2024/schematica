"""Command spec table: name, arg kinds, handler -> Session method.

Used by the REPL for parsing + completion. Each entry maps a command name to a
list of (keyword, type) specs and a function that mutates the session.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .session import Session


@dataclass
class ArgSpec:
    name: str
    kind: str  # 'int','float','str','coords','bool','block','shape'
    required: bool = True
    default: Any = None


@dataclass
class CommandSpec:
    name: str
    args: tuple[ArgSpec, ...]
    handler: Callable[..., Any]
    help: str = ""


def _coord_tuple(s: str) -> tuple[int, int, int]:
    if isinstance(s, (tuple, list)):
        return tuple(int(p) for p in s)
    s = s.strip().lstrip("(").rstrip(")")
    parts = s.replace(",", " ").split()
    if len(parts) != 3:
        raise ValueError(f"expected x,y,z got {s}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _size_tuple(s: str) -> tuple[int, int, int]:
    return _coord_tuple(s.replace("x", ","))


def cmd_session_new(s: Session, size: str, version: str = "1.20.1",
                    fill: str = "minecraft:air", chunked: bool = False,
                    chunk_size: int = 16) -> str:
    from ..blocks.block import Block as _Block
    new = Session.new(_size_tuple(size), version=version,
                      fill=_Block.parse(fill), chunked=chunked,
                      chunk_size=chunk_size)
    s.__dict__.update(new.__dict__)
    mode = "chunked" if chunked else "dense"
    return f"new session {size} v{version} ({mode})"


def cmd_add_box(s: Session, frm: str, to: str, block: str = "minecraft:stone",
                hollow: bool = False) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Box(x0, y0, z0, x1, y1, z1, hollow=hollow), block)
    return f"box {frm}->{to} {block}"


def cmd_add_sphere(s: Session, center: str, r: float, block: str = "minecraft:stone",
                   hollow: bool = False) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.add(Sphere(cx, cy, cz, r, hollow=hollow), block)
    return f"sphere @ {center} r={r}"


def cmd_add_cylinder(s: Session, center: str, r: float, h: int, block: str = "minecraft:stone",
                     hollow: bool = False) -> str:
    from ..shapes.primitives import Cylinder
    cx, _, cz = _coord_tuple(center)
    y0 = _coord_tuple(center)[1]
    s.add(Cylinder(cx, cz, r, y0, y0 + h - 1, hollow=hollow), block)
    return f"cylinder {center} r={r} h={h}"


def cmd_add_dome(s: Session, center: str, r: float, block: str = "minecraft:stone",
                 hollow: bool = False) -> str:
    from ..shapes.primitives import Dome
    cx, cy, cz = _coord_tuple(center)
    s.add(Dome(cx, cy, cz, r, hollow=hollow), block)
    return f"dome @ {center} r={r}"


def cmd_add_helix(s: Session, center: str, r: float, y0: int, y1: int,
                  turns: float = 3.0, block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Helix
    cx, _, cz = _coord_tuple(center)
    cy = _coord_tuple(center)[1]
    s.add(Helix(cx, cy, cz, r, y0, y1, turns=turns), block)
    return f"helix @ {center} r={r} y={y0}->{y1} turns={turns}"


def cmd_add_arch(s: Session, center: str, z0: int, z1: int, r: float,
                 thickness: float = 1.0, block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Arch
    cx, cy, _ = _coord_tuple(center)
    s.add(Arch(cx, cy, z0, z1, r, thickness=thickness), block)
    return f"arch @ {center} r={r} z={z0}->{z1}"


def cmd_add_staircase(s: Session, corner: str, y1: int, step_width: int = 3,
                      step_depth: int = 2, step_height: int = 1,
                      axis: str = "x", block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Staircase
    x0, y0, z0 = _coord_tuple(corner)
    s.add(Staircase(x0, y0, z0, y1, step_width=step_width,
                    step_depth=step_depth, step_height=step_height, axis=axis), block)
    return f"staircase @ {corner} y1={y1} axis={axis}"


def cmd_subtract_sphere(s: Session, center: str, r: float) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.subtract(Sphere(cx, cy, cz, r))
    return f"subtracted sphere @ {center} r={r}"


def cmd_subtract_cylinder(s: Session, center: str, r: float, h: int) -> str:
    from ..shapes.primitives import Cylinder
    cx, _, cz = _coord_tuple(center)
    y0 = _coord_tuple(center)[1]
    s.subtract(Cylinder(cx, cz, r, y0, y0 + h - 1))
    return f"subtracted cylinder @ {center} r={r} h={h}"


def cmd_paint_box(s: Session, frm: str, to: str, block: str) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.paint(Box(x0, y0, z0, x1, y1, z1), block)
    return f"painted box {frm}->{to} {block}"


# WorldEdit-style hollow shortcuts (h-prefix = hollow=True forced)
def cmd_add_hbox(s: Session, frm: str, to: str, block: str = "minecraft:stone") -> str:
    return cmd_add_box(s, frm, to, block=block, hollow=True).replace("box", "hbox", 1)


def cmd_add_hsphere(s: Session, center: str, r: float, block: str = "minecraft:stone") -> str:
    return cmd_add_sphere(s, center, r, block=block, hollow=True).replace("sphere", "hsphere", 1)


def cmd_add_hcylinder(s: Session, center: str, r: float, h: int,
                      block: str = "minecraft:stone") -> str:
    return cmd_add_cylinder(s, center, r, h, block=block, hollow=True).replace("cylinder", "hcylinder", 1)


def cmd_add_hdome(s: Session, center: str, r: float, block: str = "minecraft:stone") -> str:
    return cmd_add_dome(s, center, r, block=block, hollow=True).replace("dome", "hdome", 1)


def cmd_add_hellipsoid(s: Session, center: str, rx: float, ry: float, rz: float,
                       block: str = "minecraft:stone") -> str:
    return cmd_add_ellipsoid(s, center, rx, ry, rz, block=block, hollow=True).replace("ellipsoid", "hellipsoid", 1)


def cmd_add_cone(s: Session, center: str, r_base: float, y_base: int, y_apex: int,
                 block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Cone
    cx, _, cz = _coord_tuple(center)
    s.add(Cone(cx, cz, r_base, y_base, y_apex), block)
    return f"cone @ {center} r={r_base} y={y_base}->{y_apex}"


def cmd_add_ellipsoid(s: Session, center: str, rx: float, ry: float, rz: float,
                      block: str = "minecraft:stone",
                      hollow: bool = False) -> str:
    from ..shapes.primitives import Ellipsoid
    cx, cy, cz = _coord_tuple(center)
    s.add(Ellipsoid(cx, cy, cz, rx, ry, rz, hollow=hollow), block)
    return f"ellipsoid @ {center} rx={rx} ry={ry} rz={rz}"


def cmd_add_pyramid(s: Session, center: str, base_half: int, y_base: int, y_apex: int,
                    block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Pyramid
    cx, _, cz = _coord_tuple(center)
    s.add(Pyramid(cx, cz, base_half, y_base, y_apex), block)
    return f"pyramid @ {center} half={base_half} y={y_base}->{y_apex}"


def cmd_add_torus(s: Session, center: str, R: float, r: float,
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Torus
    cx, cy, cz = _coord_tuple(center)
    s.add(Torus(cx, cy, cz, R, r), block)
    return f"torus @ {center} R={R} r={r}"


def cmd_add_line(s: Session, frm: str, to: str,
                 block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Line
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Line(x0, y0, z0, x1, y1, z1), block)
    return f"line {frm}->{to}"


def cmd_add_wedge(s: Session, frm: str, to: str, split_axis: str = "x",
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Wedge
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Wedge(x0, y0, z0, x1, y1, z1, split_axis=split_axis), block)
    return f"wedge {frm}->{to} split={split_axis}"


def cmd_add_spiral(s: Session, center: str, r_inner: float, r_outer: float,
                   y0: int, y1: int, turns: float = 2.0,
                   block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Spiral
    cx, _, cz = _coord_tuple(center)
    s.add(Spiral(cx, cz, y0, y1, r_inner, r_outer, turns=turns), block)
    return f"spiral @ {center} r={r_inner}->{r_outer} y={y0}->{y1} turns={turns}"


def cmd_add_plane(s: Session, axis: str, coord: int, thickness: int = 1,
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Plane
    s.add(Plane(axis, coord, thickness=thickness), block)
    return f"plane axis={axis} coord={coord} thickness={thickness}"


def cmd_subtract_dome(s: Session, center: str, r: float) -> str:
    from ..shapes.primitives import Dome
    cx, cy, cz = _coord_tuple(center)
    s.subtract(Dome(cx, cy, cz, r))
    return f"subtracted dome @ {center} r={r}"


def cmd_subtract_pyramid(s: Session, center: str, base_half: int,
                         y_base: int, y_apex: int) -> str:
    from ..shapes.primitives import Pyramid
    cx, _, cz = _coord_tuple(center)
    s.subtract(Pyramid(cx, cz, base_half, y_base, y_apex))
    return f"subtracted pyramid @ {center} half={base_half}"


def cmd_paint_sphere(s: Session, center: str, r: float, block: str) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.paint(Sphere(cx, cy, cz, r), block)
    return f"painted sphere @ {center} r={r} {block}"


def cmd_subtract_box(s: Session, frm: str, to: str) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.subtract(Box(x0, y0, z0, x1, y1, z1))
    return f"subtracted box {frm}->{to}"


def cmd_replace(s: Session, src: str, dst: str) -> str:
    n = s.replace(src, dst)
    return f"replaced {n} {src}->{dst}"


def cmd_replace_bulk(s: Session, mapping: str) -> str:
    """mapping is comma-separated 'src=dst' pairs, e.g. 'stone=diorite,dirt=grass_block'."""
    from ..generators.replace import replace_bulk
    pairs: dict[str, str] = {}
    for part in mapping.split(","):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        pairs[k.strip()] = v.strip()
    n = replace_bulk(s.grid, pairs)
    return f"bulk replaced {n} ({len(pairs)} mappings)"


def cmd_replace_by_name(s: Session, src_name: str, dst: str) -> str:
    """Replace every block with name == src_name regardless of state."""
    from ..generators.replace import replace_by_name
    n = replace_by_name(s.grid, src_name, dst)
    return f"replaced-by-name {n} {src_name}->{dst}"


def cmd_replace_pattern(s: Session, src: str, dst: str,
                        neighbours: str = "") -> str:
    """Replace src with dst where neighbour constraints hold.

    neighbours is a ';'-separated list of 'dx,dy,dz=block' specs, e.g.
    '0,1,0=minecraft:air;0,-1,0=*' meaning "air above, any-solid below".
    """
    from ..generators.replace import NeighbourSpec, replace_pattern
    specs: list[NeighbourSpec] = []
    if neighbours:
        for part in neighbours.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            offset_s, _, block = part.partition("=")
            dx, dy, dz = (int(v) for v in offset_s.split(","))
            specs.append(NeighbourSpec((dx, dy, dz), block.strip()))
    n = replace_pattern(s.grid, src, dst, neighbours=specs or None)
    return f"pattern-replaced {n} {src}->{dst}"


def cmd_retexture(s: Session, property: str, value: str,
                  name: str = "") -> str:
    """Set a blockstate property on all blocks that have it.

    e.g. retexture property=axis value=x name=minecraft:oak_log
    """
    from ..generators.retexture import retexture
    n = retexture(s.grid, property, value, name=name or None)
    return f"retextured {n} ({property}={value})"


def cmd_retexture_map(s: Session, property: str, mapping: str,
                      name: str = "") -> str:
    """Remap a state property across many values. mapping is 'x=y,y=z,z=x'."""
    from ..generators.retexture import retexture_map
    pairs: dict[object, object] = {}
    for part in mapping.split(","):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        pairs[k.strip()] = v.strip()
    n = retexture_map(s.grid, property, pairs, name=name or None)
    return f"retextured {n} ({property} remap)"


def cmd_texture_palette(s: Session, frm: str, to: str,
                        blocks: str, weights: str = "",
                        noise: str = "perlin", scale: float = 0.15,
                        seed: int = 0) -> str:
    """Paint a region with a noise-driven texture palette.

    blocks is '+ -separated list of blockstate strings.
    weights is optional '+ -separated list of relative weights.
    """
    from ..generators.texture import TexturePalette, apply_texture
    bl = [b.strip() for b in blocks.split("+") if b.strip()]
    w = [float(x) for x in weights.split("+") if x.strip()] if weights else []
    tp = TexturePalette(blocks=bl, weights=w or [1.0] * len(bl),
                        noise=noise, scale=scale, seed=seed)  # type: ignore[arg-type]
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    n = apply_texture(s, tp, (x0, y0, z0), (x1, y1, z1))
    return f"texture-painted {n} ({len(bl)} blocks, {noise})"


def cmd_undo(s: Session) -> str:
    return "undo ok" if s.undo() else "nothing to undo"


def cmd_redo(s: Session) -> str:
    return "redo ok" if s.redo() else "nothing to redo"


def cmd_clear(s: Session) -> str:
    s.clear()
    return "cleared"


def cmd_stats(s: Session) -> str:
    st = s.stats()
    base = (f"shape={st['shape']} vol={st['volume']} solid={st['solid']} "
            f"palette={st['palette_size']}")
    if st.get("chunked"):
        base += (f" chunks={st['chunks']} chunk_size={st['chunk_size']} "
                 f"mem={st['memory_bytes']}B")
    return base


def cmd_preview(s: Session, out_dir: str = "previews") -> str:
    from ..render.preview import preview
    paths = preview(s.grid, out_dir)
    return "previews: " + ", ".join(p.name for p in paths)


def cmd_export(s: Session, path: str) -> str:
    from ..export.sponge import write_sponge
    p = write_sponge(s.grid, path)
    return f"exported {p}"


def cmd_export_mcedit(s: Session, path: str) -> str:
    from ..export.mcedit import write_mcedit
    p = write_mcedit(s.grid, path)
    return f"exported (mcedit) {p}"


def cmd_export_litematic(s: Session, path: str) -> str:
    from ..export.litematic import write_litematic
    p = write_litematic(s.grid, path)
    return f"exported (litematic) {p}"


def cmd_save(s: Session, path: str) -> str:
    p = s.save(path)
    return f"saved {p}"


def cmd_load(s: Session, path: str) -> str:
    new = Session.load(path)
    s.__dict__.update(new.__dict__)
    return f"loaded {path}"


def cmd_fill(s: Session, block: str) -> str:
    s.fill_all(block)
    return f"filled {block}"


def cmd_mirror(s: Session, axis: str) -> str:
    amap = {"x": 0, "y": 1, "z": 2}
    s.transform_mirror(amap[axis])
    return f"mirrored {axis}"


def cmd_rotate(s: Session, times: int, axes: str = "xy") -> str:
    s.transform_rotate(times, axes)
    return f"rotated {times} {axes}"


def cmd_generate_terrain(s: Session, seed: int = 0, amplitude: int = 8,
                         scale: float = 0.06,
                         top: str = "minecraft:grass_block",
                         filler: str = "minecraft:dirt") -> str:
    from ..generators.templates import apply_terrain
    apply_terrain(s, seed=seed, amplitude=amplitude, scale=scale,
                  top=top, filler=filler)
    return f"terrain seed={seed} amp={amplitude}"


def cmd_generate_tree(s: Session, at: str, height: int = 6,
                      trunk: str = "minecraft:oak_log",
                      leaves: str = "minecraft:oak_leaves") -> str:
    from ..generators.templates import apply_tree
    x, y, z = _coord_tuple(at)
    apply_tree(s, x=x, z=z, height=height, trunk=trunk, leaves=leaves)
    return f"tree @ {at} h={height}"


def cmd_generate_wfc(s: Session, frm: str, to: str,
                     tileset: str = "mossy_ruins",
                     seed: int = 0) -> str:
    """Run WFC over a sub-box and place the resulting blocks."""
    from ..generators.wfc import run_wfc, tileset_mossy_ruins
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
    if any(d <= 0 for d in shape):
        return "error: wfc box must have positive volume"
    if tileset == "mossy_ruins":
        ts = tileset_mossy_ruins()
    elif tileset == "wildcard":
        # Wildcard needs a block list; pick a sensible default palette.
        from ..generators.wfc import Tile, TileSet
        ts = TileSet([Tile("minecraft:stone"), Tile("minecraft:cobblestone"),
                       Tile("minecraft:dirt")])
    else:
        return f"error: unknown tileset {tileset!r}"
    blocks = run_wfc(shape, ts, seed=seed)
    from ..blocks.block import Block
    for xx in range(shape[0]):
        for yy in range(shape[1]):
            for zz in range(shape[2]):
                b = blocks[xx, yy, zz]
                if b != "minecraft:air":
                    s.grid.set(x0 + xx, y0 + yy, z0 + zz, Block.parse(b))
    return f"wfc {frm}->{to} tileset={tileset} seed={seed}"


COMMANDS: dict[str, CommandSpec] = {
    "session.new": CommandSpec("session.new", (
        ArgSpec("size", "str"), ArgSpec("version", "str", default="1.20.1", required=False),
        ArgSpec("fill", "block", default="minecraft:air", required=False),
        ArgSpec("chunked", "bool", default=False, required=False),
        ArgSpec("chunk_size", "int", default=16, required=False),
    ), cmd_session_new, "create a new session: size=16x16x16 version=1.20.1 chunked=true chunk_size=16"),
    "add.box": CommandSpec("add.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_box, "add a box from=A to=B block=X hollow=true"),
    "add.hbox": CommandSpec("add.hbox", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hbox, "hollow box (walls only) from=A to=B"),
    "add.sphere": CommandSpec("add.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_sphere, "add sphere center=X r=N block=X"),
    "add.hsphere": CommandSpec("add.hsphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hsphere, "hollow sphere (shell only) center=X r=N"),
    "add.cylinder": CommandSpec("add.cylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_cylinder, "add cylinder center=X r=N h=N"),
    "add.hcylinder": CommandSpec("add.hcylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hcylinder, "hollow cylinder (tube only) center=X r=N h=N"),
    "add.dome": CommandSpec("add.dome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_dome, "add dome center=X r=N block=X hollow=true"),
    "add.hdome": CommandSpec("add.hdome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hdome, "hollow dome (shell only) center=X r=N"),
    "add.helix": CommandSpec("add.helix", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("y0", "int"), ArgSpec("y1", "int"),
        ArgSpec("turns", "float", default=3.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_helix, "add helix center=X r=N y0=A y1=B turns=N"),
    "add.arch": CommandSpec("add.arch", (
        ArgSpec("center", "coords"), ArgSpec("z0", "int"), ArgSpec("z1", "int"),
        ArgSpec("r", "float"),
        ArgSpec("thickness", "float", default=1.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_arch, "add arch center=X z0=A z1=B r=N thickness=N"),
    "add.staircase": CommandSpec("add.staircase", (
        ArgSpec("corner", "coords"), ArgSpec("y1", "int"),
        ArgSpec("step_width", "int", default=3, required=False),
        ArgSpec("step_depth", "int", default=2, required=False),
        ArgSpec("step_height", "int", default=1, required=False),
        ArgSpec("axis", "str", default="x", required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_staircase, "add staircase corner=X y1=N axis=x|z"),
    "add.cone": CommandSpec("add.cone", (
        ArgSpec("center", "coords"), ArgSpec("r_base", "float"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_cone, "add cone center=X r_base=N y_base=A y_apex=B"),
    "add.ellipsoid": CommandSpec("add.ellipsoid", (
        ArgSpec("center", "coords"), ArgSpec("rx", "float"),
        ArgSpec("ry", "float"), ArgSpec("rz", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_ellipsoid, "add ellipsoid center=X rx=N ry=N rz=N"),
    "add.hellipsoid": CommandSpec("add.hellipsoid", (
        ArgSpec("center", "coords"), ArgSpec("rx", "float"),
        ArgSpec("ry", "float"), ArgSpec("rz", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hellipsoid, "hollow ellipsoid (shell only)"),
    "add.pyramid": CommandSpec("add.pyramid", (
        ArgSpec("center", "coords"), ArgSpec("base_half", "int"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_pyramid, "add pyramid center=X half=N y_base=A y_apex=B"),
    "add.torus": CommandSpec("add.torus", (
        ArgSpec("center", "coords"), ArgSpec("R", "float"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_torus, "add torus center=X R=major r=minor"),
    "add.line": CommandSpec("add.line", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_line, "add 1-voxel line from=A to=B"),
    "add.wedge": CommandSpec("add.wedge", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("split_axis", "str", default="x", required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_wedge, "add wedge from=A to=B split_axis=x|z"),
    "add.spiral": CommandSpec("add.spiral", (
        ArgSpec("center", "coords"), ArgSpec("r_inner", "float"),
        ArgSpec("r_outer", "float"), ArgSpec("y0", "int"), ArgSpec("y1", "int"),
        ArgSpec("turns", "float", default=2.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_spiral, "add spiral center=X r_inner=A r_outer=B y0=C y1=D"),
    "add.plane": CommandSpec("add.plane", (
        ArgSpec("axis", "str"), ArgSpec("coord", "int"),
        ArgSpec("thickness", "int", default=1, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_plane, "add plane axis=x|y|z coord=N thickness=N"),
    "subtract.box": CommandSpec("subtract.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
    ), cmd_subtract_box, "carve a box"),
    "subtract.sphere": CommandSpec("subtract.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
    ), cmd_subtract_sphere, "carve a sphere"),
    "subtract.cylinder": CommandSpec("subtract.cylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
    ), cmd_subtract_cylinder, "carve a cylinder"),
    "subtract.dome": CommandSpec("subtract.dome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
    ), cmd_subtract_dome, "carve a dome"),
    "subtract.pyramid": CommandSpec("subtract.pyramid", (
        ArgSpec("center", "coords"), ArgSpec("base_half", "int"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
    ), cmd_subtract_pyramid, "carve a pyramid"),
    "paint.box": CommandSpec("paint.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"), ArgSpec("block", "block"),
    ), cmd_paint_box, "repaint existing solid voxels in a box"),
    "paint.sphere": CommandSpec("paint.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("block", "block"),
    ), cmd_paint_sphere, "repaint existing solid voxels in a sphere"),
    "replace": CommandSpec("replace", (
        ArgSpec("src", "block"), ArgSpec("dst", "block"),
    ), cmd_replace, "replace src dst"),
    "replace.bulk": CommandSpec("replace.bulk", (
        ArgSpec("mapping", "str"),
    ), cmd_replace_bulk, "bulk replace mapping=stone=diorite,dirt=grass_block"),
    "replace.by_name": CommandSpec("replace.by_name", (
        ArgSpec("src_name", "str"), ArgSpec("dst", "block"),
    ), cmd_replace_by_name, "replace all blocks named src_name regardless of state"),
    "replace.pattern": CommandSpec("replace.pattern", (
        ArgSpec("src", "block"), ArgSpec("dst", "block"),
        ArgSpec("neighbours", "str", default="", required=False),
    ), cmd_replace_pattern, "replace src with dst where neighbours match (dx,dy,dz=block;...)"),
    "retexture": CommandSpec("retexture", (
        ArgSpec("property", "str"), ArgSpec("value", "str"),
        ArgSpec("name", "str", default="", required=False),
    ), cmd_retexture, "set a blockstate property on all blocks that have it"),
    "retexture.map": CommandSpec("retexture.map", (
        ArgSpec("property", "str"), ArgSpec("mapping", "str"),
        ArgSpec("name", "str", default="", required=False),
    ), cmd_retexture_map, "remap a state property (x=y,y=z,z=x)"),
    "texture.palette": CommandSpec("texture.palette", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("blocks", "str"),
        ArgSpec("weights", "str", default="", required=False),
        ArgSpec("noise", "str", default="perlin", required=False),
        ArgSpec("scale", "float", default=0.15, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_texture_palette, "paint a region with a noise-driven texture palette"),
    "undo": CommandSpec("undo", (), cmd_undo, "undo last op"),
    "redo": CommandSpec("redo", (), cmd_redo, "redo"),
    "clear": CommandSpec("clear", (), cmd_clear, "clear grid"),
    "stats": CommandSpec("stats", (), cmd_stats, "show stats"),
    "preview": CommandSpec("preview", (
        ArgSpec("out_dir", "str", default="previews", required=False),
    ), cmd_preview, "render preview PNGs"),
    "export": CommandSpec("export", (ArgSpec("path", "str"),), cmd_export,
                          "export Sponge .schem"),
    "export.mcedit": CommandSpec("export.mcedit", (ArgSpec("path", "str"),),
                                  cmd_export_mcedit, "export legacy MCEdit .schematic"),
    "export.litematic": CommandSpec("export.litematic", (ArgSpec("path", "str"),),
                                      cmd_export_litematic, "export Litematica .litematic"),
    "save": CommandSpec("save", (ArgSpec("path", "str"),), cmd_save,
                       "save session"),
    "load": CommandSpec("load", (ArgSpec("path", "str"),), cmd_load,
                        "load session"),
    "fill": CommandSpec("fill", (ArgSpec("block", "block"),), cmd_fill, "fill all"),
    "mirror": CommandSpec("mirror", (ArgSpec("axis", "str"),), cmd_mirror,
                           "mirror x/y/z"),
    "rotate": CommandSpec("rotate", (
        ArgSpec("times", "int"), ArgSpec("axes", "str", default="xy", required=False),
    ), cmd_rotate, "rotate 90*times in xy/xz/yz plane"),
    "generate.terrain": CommandSpec("generate.terrain", (
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("amplitude", "int", default=8, required=False),
        ArgSpec("scale", "float", default=0.06, required=False),
        ArgSpec("top", "block", default="minecraft:grass_block", required=False),
        ArgSpec("filler", "block", default="minecraft:dirt", required=False),
    ), cmd_generate_terrain, "generate terrain seed=N amplitude=N"),
    "generate.tree": CommandSpec("generate.tree", (
        ArgSpec("at", "coords"), ArgSpec("height", "int", default=6, required=False),
        ArgSpec("trunk", "block", default="minecraft:oak_log", required=False),
        ArgSpec("leaves", "block", default="minecraft:oak_leaves", required=False),
    ), cmd_generate_tree, "generate a tree at=X height=N"),
    "generate.wfc": CommandSpec("generate.wfc", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("tileset", "str", default="mossy_ruins", required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_generate_wfc, "wave function collapse fill frm=A to=B tileset=name"),
}
