"""Interactive REPL driving a Session via the command table.

Also doubles as a batch runner: pipe a script file through stdin or pass
`--script path` to execute commands non-interactively.

Every command is validated before execution. Errors refuse the command;
warnings print on a `! ` line after the status so the agent can detect
suspicious usage without it being fatal.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..session.commands import COMMANDS
from ..session.session import Session
from . import validation as v
from .parser import parse_line


def _coerce(value: str, kind: str) -> object:
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "bool":
        return value.lower() in ("1", "true", "yes", "y")
    if kind == "coords":
        return value  # handlers parse via _coord_tuple
    if kind == "block":
        return value
    return value


def _run_checks(name: str, kwargs: dict[str, Any], session: Session) -> list[v.CheckResult]:
    """Dispatch to the per-command validator. Returns a list of CheckResult."""
    reg = getattr(session, "registry", None)
    if name == "session.new":
        return v.check_session_new(kwargs.get("size", ""),
                                   kwargs.get("version", "1.20.1"), reg)
    if name == "add.box":
        return v.check_add_box(kwargs["frm"], kwargs["to"],
                               kwargs.get("block", "minecraft:stone"),
                               kwargs.get("hollow", False), session, reg)
    if name == "add.hbox":
        return v.check_add_box(kwargs["frm"], kwargs["to"],
                               kwargs.get("block", "minecraft:stone"),
                               True, session, reg)
    if name == "subtract.box":
        return v.check_subtract_box(kwargs["frm"], kwargs["to"], session)
    if name == "add.sphere":
        return v.check_add_sphere(kwargs["center"], kwargs["r"],
                                  kwargs.get("block", "minecraft:stone"),
                                  kwargs.get("hollow", False), session, reg)
    if name == "add.hsphere":
        return v.check_add_sphere(kwargs["center"], kwargs["r"],
                                  kwargs.get("block", "minecraft:stone"),
                                  True, session, reg)
    if name == "add.cylinder":
        return v.check_add_cylinder(kwargs["center"], kwargs["r"], kwargs["h"],
                                    kwargs.get("block", "minecraft:stone"),
                                    kwargs.get("hollow", False), session, reg)
    if name == "add.hcylinder":
        return v.check_add_cylinder(kwargs["center"], kwargs["r"], kwargs["h"],
                                    kwargs.get("block", "minecraft:stone"),
                                    True, session, reg)
    if name == "add.dome":
        return v.check_add_dome(kwargs["center"], kwargs["r"],
                                kwargs.get("block", "minecraft:stone"),
                                kwargs.get("hollow", False), session, reg)
    if name == "add.hdome":
        return v.check_add_dome(kwargs["center"], kwargs["r"],
                                kwargs.get("block", "minecraft:stone"),
                                True, session, reg)
    if name == "add.helix":
        return v.check_add_helix(kwargs["center"], kwargs["r"],
                                 kwargs["y0"], kwargs["y1"],
                                 kwargs.get("turns", 3.0),
                                 kwargs.get("block", "minecraft:stone"),
                                 session, reg)
    if name == "add.arch":
        return v.check_add_arch(kwargs["center"], kwargs["z0"], kwargs["z1"],
                                kwargs["r"], kwargs.get("thickness", 1.0),
                                kwargs.get("block", "minecraft:stone"),
                                session, reg)
    if name == "add.staircase":
        return v.check_add_staircase(kwargs["corner"], kwargs["y1"],
                                     kwargs.get("step_width", 3),
                                     kwargs.get("step_depth", 2),
                                     kwargs.get("step_height", 1),
                                     kwargs.get("axis", "x"),
                                     kwargs.get("block", "minecraft:stone"),
                                     session, reg)
    if name == "add.cone":
        return v.check_add_cone(kwargs["center"], kwargs["r_base"],
                                kwargs["y_base"], kwargs["y_apex"],
                                kwargs.get("block", "minecraft:stone"),
                                session, reg)
    if name == "add.ellipsoid":
        return v.check_add_ellipsoid(kwargs["center"], kwargs["rx"],
                                     kwargs["ry"], kwargs["rz"],
                                     kwargs.get("block", "minecraft:stone"),
                                     kwargs.get("hollow", False), session, reg)
    if name == "add.hellipsoid":
        return v.check_add_ellipsoid(kwargs["center"], kwargs["rx"],
                                     kwargs["ry"], kwargs["rz"],
                                     kwargs.get("block", "minecraft:stone"),
                                     True, session, reg)
    if name == "add.pyramid":
        return v.check_add_pyramid(kwargs["center"], kwargs["base_half"],
                                   kwargs["y_base"], kwargs["y_apex"],
                                   kwargs.get("block", "minecraft:stone"),
                                   session, reg)
    if name == "add.torus":
        return v.check_add_torus(kwargs["center"], kwargs["R"], kwargs["r"],
                                 kwargs.get("block", "minecraft:stone"),
                                 session, reg)
    if name == "add.line":
        return v.check_add_line(kwargs["frm"], kwargs["to"],
                                kwargs.get("block", "minecraft:stone"),
                                session, reg)
    if name == "add.wedge":
        return v.check_add_wedge(kwargs["frm"], kwargs["to"],
                                 kwargs.get("split_axis", "x"),
                                 kwargs.get("block", "minecraft:stone"),
                                 session, reg)
    if name == "add.spiral":
        return v.check_add_spiral(kwargs["center"], kwargs["r_inner"],
                                  kwargs["r_outer"], kwargs["y0"], kwargs["y1"],
                                  kwargs.get("turns", 2.0),
                                  kwargs.get("block", "minecraft:stone"),
                                  session, reg)
    if name == "add.plane":
        return v.check_add_plane(kwargs["axis"], kwargs["coord"],
                                 kwargs.get("thickness", 1),
                                 kwargs.get("block", "minecraft:stone"),
                                 session, reg)
    if name == "subtract.sphere":
        return v.check_subtract_sphere(kwargs["center"], kwargs["r"], session)
    if name == "subtract.cylinder":
        return v.check_subtract_cylinder(kwargs["center"], kwargs["r"],
                                         kwargs["h"], session)
    if name == "subtract.dome":
        return v.check_subtract_dome(kwargs["center"], kwargs["r"], session)
    if name == "subtract.pyramid":
        return v.check_subtract_pyramid(kwargs["center"], kwargs["base_half"],
                                        kwargs["y_base"], kwargs["y_apex"], session)
    if name == "paint.box":
        return v.check_paint_box(kwargs["frm"], kwargs["to"],
                                 kwargs["block"], session, reg)
    if name == "paint.sphere":
        return v.check_paint_sphere(kwargs["center"], kwargs["r"],
                                    kwargs["block"], session, reg)
    if name == "replace":
        return v.check_replace(kwargs["src"], kwargs["dst"], reg)
    if name == "replace.bulk":
        return []
    if name == "replace.by_name":
        return []
    if name == "replace.pattern":
        return []
    if name == "retexture":
        return []
    if name == "retexture.map":
        return []
    if name == "texture.palette":
        return v.check_generate_wfc(kwargs["frm"], kwargs["to"], session)
    if name == "fill":
        return v.check_fill(kwargs["block"], reg)
    if name == "mirror":
        return v.check_mirror(kwargs["axis"])
    if name == "rotate":
        return v.check_rotate(kwargs["times"], kwargs.get("axes", "xy"))
    if name == "generate.terrain":
        return []
    if name == "generate.tree":
        return v.check_generate_tree(kwargs["at"], kwargs.get("height", 6), session)
    if name == "generate.wfc":
        return v.check_generate_wfc(kwargs["frm"], kwargs["to"], session)
    if name == "export":
        return v.check_export(kwargs["path"])
    if name == "export.mcedit":
        return v.check_export(kwargs["path"])
    if name == "export.litematic":
        return v.check_export(kwargs["path"])
    if name == "save":
        return v.check_save(kwargs["path"])
    if name == "load":
        return v.check_load(kwargs["path"])
    if name == "preview":
        return v.check_preview(kwargs.get("out_dir", "previews"))
    return []


def dispatch(session: Session, line: str) -> str:
    # Pre-parse backslash check: shlex would silently eat backslashes, so
    # detect them in the raw line first and warn (but still proceed with the
    # mangled value so the agent sees the consequence).
    backslash_warn = ""
    if "\\" in line and not line.strip().startswith("#"):
        backslash_warn = "\n! [backslash_path] line contains backslashes; shlex may mangle paths - use forward slashes"

    parsed = parse_line(line)
    if parsed is None:
        return ""
    spec = COMMANDS.get(parsed.name)
    if spec is None:
        alt = parsed.name.replace(" ", ".")
        spec = COMMANDS.get(alt)
        if spec is None:
            return f"unknown command: {parsed.name}" + backslash_warn
    kwargs: dict[str, Any] = {}
    positional = parsed.args.pop("__positional__", "")
    pos_list = positional.split() if positional else []
    pos_idx = 0
    for arg in spec.args:
        if arg.name in parsed.args:
            raw = parsed.args[arg.name]
        elif pos_idx < len(pos_list):
            raw = pos_list[pos_idx]
            pos_idx += 1
        else:
            if arg.required:
                return f"missing arg: {arg.name}"
            kwargs[arg.name] = arg.default
            continue
        kwargs[arg.name] = _coerce(raw, arg.kind)

    # Pre-execution validation. Errors refuse the command; warnings proceed.
    checks = _run_checks(spec.name, kwargs, session)
    errors = [c for c in checks if c.is_error]
    warnings = [c for c in checks if not c.is_error]
    if errors:
        parts = "; ".join(f"[{c.code}] {c.message}" for c in errors)
        return f"error: {parts}"
    warn_str = ""
    if warnings:
        warn_str = "\n! " + "\n! ".join(f"[{c.code}] {c.message}" for c in warnings)

    try:
        result = spec.handler(session, **kwargs)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}" + backslash_warn
    return str(result) + warn_str + backslash_warn


def run_script(session: Session, script_path: str) -> list[str]:
    out: list[str] = []
    for raw in Path(script_path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        res = dispatch(session, line)
        out.append(f"> {line}")
        if res:
            out.append(res)
    return out


def repl_main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    session = Session.new((32, 32, 32))
    if argv and argv[0] == "--script":
        for line in run_script(session, argv[1]):
            print(line)
        return 0
    print("Schematica REPL. Type 'help' for commands, 'exit' to quit.")
    try:
        while True:
            try:
                line = input("schematica> ").strip()
            except EOFError:
                break
            if line in ("exit", "quit"):
                break
            if line == "help":
                for name, spec in COMMANDS.items():
                    print(f"  {name:20s} {spec.help}")
                continue
            res = dispatch(session, line)
            if res:
                print(res)
    except KeyboardInterrupt:
        print()
    return 0


def main() -> int:
    return repl_main()


if __name__ == "__main__":
    raise SystemExit(main())
