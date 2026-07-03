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
        return tuple(int(p) for p in s)  # type: ignore[return-value]
    s = s.strip().lstrip("(").rstrip(")")
    parts = s.replace(",", " ").split()
    if len(parts) != 3:
        raise ValueError(f"expected x,y,z got {s}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _size_tuple(s: str) -> tuple[int, int, int]:
    return _coord_tuple(s.replace("x", ","))


def cmd_session_new(s: Session, size: str, version: str = "1.20.1",
                    fill: str = "minecraft:air") -> str:
    new = Session.new(_size_tuple(size), version=version, fill=__import__("schematica.blocks.block", fromlist=["Block"]).Block.parse(fill))
    s.__dict__.update(new.__dict__)
    return f"new session {size} v{version}"


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


def cmd_undo(s: Session) -> str:
    return "undo ok" if s.undo() else "nothing to undo"


def cmd_redo(s: Session) -> str:
    return "redo ok" if s.redo() else "nothing to redo"


def cmd_clear(s: Session) -> str:
    s.clear()
    return "cleared"


def cmd_stats(s: Session) -> str:
    st = s.stats()
    return (f"shape={st['shape']} vol={st['volume']} solid={st['solid']} "
            f"palette={st['palette_size']}")


def cmd_preview(s: Session, out_dir: str = "previews") -> str:
    from ..render.preview import preview
    paths = preview(s.grid, out_dir)
    return "previews: " + ", ".join(p.name for p in paths)


def cmd_export(s: Session, path: str) -> str:
    from ..export.sponge import write_sponge
    p = write_sponge(s.grid, path)
    return f"exported {p}"


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


COMMANDS: dict[str, CommandSpec] = {
    "session.new": CommandSpec("session.new", (
        ArgSpec("size", "str"), ArgSpec("version", "str", default="1.20.1", required=False),
        ArgSpec("fill", "block", default="minecraft:air", required=False),
    ), cmd_session_new, "create a new session: size=16x16x16 version=1.20.1"),
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
    "undo": CommandSpec("undo", (), cmd_undo, "undo last op"),
    "redo": CommandSpec("redo", (), cmd_redo, "redo"),
    "clear": CommandSpec("clear", (), cmd_clear, "clear grid"),
    "stats": CommandSpec("stats", (), cmd_stats, "show stats"),
    "preview": CommandSpec("preview", (
        ArgSpec("out_dir", "str", default="previews", required=False),
    ), cmd_preview, "render preview PNGs"),
    "export": CommandSpec("export", (ArgSpec("path", "str"),), cmd_export,
                          "export Sponge .schem"),
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
}
