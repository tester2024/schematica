"""Validation and warnings for CLI command usage.

Returns structured (severity, code, message) tuples that the dispatcher formats
consistently. Severity is 'error' (command refused) or 'warn' (command ran but
flagged suspicious usage). Codes are stable strings the agent can match on.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["error", "warn"]


@dataclass(frozen=True)
class CheckResult:
    severity: Severity
    code: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def _coord_tuple(s: str | tuple[int, int, int]) -> tuple[int, int, int] | None:
    if isinstance(s, (tuple, list)) and len(s) == 3:
        try:
            return tuple(int(p) for p in s)  # type: ignore[return-value]
        except (ValueError, TypeError):
            return None
    if not isinstance(s, str):
        return None
    cleaned = s.strip().lstrip("(").rstrip(")")
    parts = cleaned.replace(",", " ").split()
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _bounds(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return per-axis max - min. Negative => inverted bounds."""
    return tuple(b[i] - a[i] for i in range(3))  # type: ignore[return-value]


def _known_axis_value(value: str) -> bool:
    return value.lower() in {"x", "y", "z"}


def _parse_blockstate_check(s: str, registry: Any) -> tuple[object, str | None]:
    """Return (block_or_None, error_or_None). Validates states when registry present."""
    from ..blocks.block import Block
    try:
        b = Block.parse(s)
    except Exception as e:  # noqa: BLE001
        return None, f"invalid blockstate string: {e}"
    if registry is None:
        return b, None
    if b.name not in registry:
        return None, f"unknown block '{b.name}' for version {registry.version}"
    try:
        registry.validate(b)
    except ValueError as e:
        return None, str(e)
    return b, None


def check_session_new(size_str: str, version: str,
                      registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    # size accepts "WxHxD" or "W,H,D" - normalize to commas then parse.
    shape = _coord_tuple(size_str.replace("x", ",") if isinstance(size_str, str) else size_str)
    if shape is None:
        out.append(CheckResult("error", "bad_size",
                                f"size {size_str!r} did not parse to WxHxD or W,H,D"))
        return out
    sx, sy, sz = shape
    if sx <= 0 or sy <= 0 or sz <= 0:
        out.append(CheckResult("error", "nonpositive_size",
                               f"size {shape} has a nonpositive axis; grid would be empty"))
    elif max(shape) > 512:
        out.append(CheckResult("warn", "huge_size",
                               f"size {shape} is very large; preview/export may be slow"))
    if registry is not None:
        versions = _available_versions(registry)
        if versions and version not in versions:
            out.append(CheckResult("warn", "unknown_version",
                                   f"version {version} has no blocks.json; "
                                   f"available: {sorted(versions)[:5]}..."))
    return out


def _available_versions(registry: Any) -> set[str]:
    from ..blocks.registry import BlockRegistry
    try:
        return set(BlockRegistry.list_versions())
    except Exception:
        return set()


def check_add_box(frm: str, to: str, block: str, hollow: bool,
                  session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse to x,y,z"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse to x,y,z"))
    if a and b:
        dims = _bounds(a, b)
        if any(d < 0 for d in dims):
            out.append(CheckResult("error", "inverted_bounds",
                                   f"box frm={a} to={b} has inverted bounds; "
                                   f"swap frm/to so each axis in frm <= to"))
        if hollow and all(d == 0 for d in dims) and any(d == 0 for d in dims):
            out.append(CheckResult("warn", "hollow_zero",
                                   "hollow box with zero thickness collapses to nothing"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    out.extend(_check_outside(frm, to, session))
    return out


def check_subtract_box(frm: str, to: str, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse"))
    if a and b:
        dims = _bounds(a, b)
        if any(d < 0 for d in dims):
            out.append(CheckResult("error", "inverted_bounds",
                                   f"subtract box frm={a} to={b} has inverted bounds"))
    out.extend(_check_outside(frm, to, session))
    return out


def check_add_sphere(center: str, r: float, block: str, hollow: bool,
                     session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius",
                               f"radius r={r} is negative; sphere would be empty"))
    elif r == 0:
        out.append(CheckResult("warn", "zero_radius",
                               "radius r=0 yields at most a single voxel"))
    if hollow and r < 1:
        out.append(CheckResult("warn", "hollow_tiny",
                               f"hollow sphere with r={r} collapses to nothing"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    if c is not None and any(not (0 <= c[i] < session.grid.shape[i]) for i in range(3)):
        out.append(CheckResult("warn", "center_outside",
                              f"center {c} is outside grid {session.grid.shape}; "
                              f"mask will be empty or clipped"))
    return out


def check_add_cylinder(center: str, r: float, h: int, block: str, hollow: bool,
                       session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius",
                               f"radius r={r} is negative"))
    elif r == 0:
        out.append(CheckResult("warn", "zero_radius", "radius r=0 yields at most a 1-wide column"))
    if h <= 0:
        out.append(CheckResult("error", "nonpositive_height",
                               f"height h={h} must be positive"))
    if hollow and r < 1:
        out.append(CheckResult("warn", "hollow_tiny",
                               f"hollow cylinder with r={r} collapses to nothing"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_dome(center: str, r: float, block: str, hollow: bool,
                   session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    elif r == 0:
        out.append(CheckResult("warn", "zero_radius", "radius r=0 yields at most 1 voxel"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_helix(center: str, r: float, y0: int, y1: int, turns: float,
                    block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    if y1 <= y0:
        out.append(CheckResult("error", "inverted_bounds",
                               f"helix y0={y0} must be < y1={y1}"))
    if turns <= 0:
        out.append(CheckResult("warn", "zero_turns",
                               f"turns={turns} <= 0; helix will be a vertical line"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_arch(center: str, z0: int, z1: int, r: float, thickness: float,
                   block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r <= 0:
        out.append(CheckResult("error", "negative_radius",
                               f"arch radius r={r} must be positive"))
    if z1 < z0:
        out.append(CheckResult("error", "inverted_bounds",
                               f"arch z0={z0} must be <= z1={z1}"))
    if thickness <= 0:
        out.append(CheckResult("warn", "zero_thickness",
                               f"thickness={thickness} <= 0; arch may be invisible"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_staircase(corner: str, y1: int, step_width: int, step_depth: int,
                        step_height: int, axis: str, block: str,
                        session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(corner)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"corner={corner!r} did not parse"))
    if y1 <= c[1] if c else True:
        if c:
            out.append(CheckResult("error", "inverted_bounds",
                                   f"staircase y1={y1} must be > y0={c[1]}"))
    if axis not in ("x", "z"):
        out.append(CheckResult("error", "bad_axis",
                               f"axis={axis!r} must be 'x' or 'z'"))
    if step_width <= 0 or step_depth <= 0 or step_height <= 0:
        out.append(CheckResult("error", "nonpositive_step",
                               f"step dimensions must be positive; got "
                               f"w={step_width} d={step_depth} h={step_height}"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_subtract_sphere(center: str, r: float, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    elif r == 0:
        out.append(CheckResult("warn", "zero_radius", "radius r=0 carves at most 1 voxel"))
    return out


def check_subtract_cylinder(center: str, r: float, h: int, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    if h <= 0:
        out.append(CheckResult("error", "nonpositive_height", f"height h={h} must be positive"))
    return out


def check_paint_box(frm: str, to: str, block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse"))
    if a and b:
        dims = _bounds(a, b)
        if any(d < 0 for d in dims):
            out.append(CheckResult("error", "inverted_bounds",
                                   f"paint box frm={a} to={b} has inverted bounds"))
    out.extend(_check_block(block, registry))
    out.extend(_check_outside(frm, to, session))
    return out


def check_add_cone(center: str, r_base: float, y_base: int, y_apex: int,
                   block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r_base < 0:
        out.append(CheckResult("error", "negative_radius", f"r_base={r_base} is negative"))
    if y_apex <= y_base:
        out.append(CheckResult("error", "inverted_bounds",
                               f"cone y_base={y_base} must be < y_apex={y_apex}"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_ellipsoid(center: str, rx: float, ry: float, rz: float,
                        block: str, hollow: bool, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    for name, val in [("rx", rx), ("ry", ry), ("rz", rz)]:
        if val <= 0:
            out.append(CheckResult("error", "negative_radius",
                                   f"ellipsoid {name}={val} must be positive"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_pyramid(center: str, base_half: int, y_base: int, y_apex: int,
                      block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if base_half < 0:
        out.append(CheckResult("error", "negative_radius",
                               f"base_half={base_half} is negative"))
    if y_apex <= y_base:
        out.append(CheckResult("error", "inverted_bounds",
                               f"pyramid y_base={y_base} must be < y_apex={y_apex}"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_torus(center: str, R: float, r: float,
                    block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if R <= 0:
        out.append(CheckResult("error", "negative_radius", f"major radius R={R} must be positive"))
    if r <= 0:
        out.append(CheckResult("error", "negative_radius", f"minor radius r={r} must be positive"))
    if r > R:
        out.append(CheckResult("warn", "torus_inverted_radii",
                               f"minor r={r} > major R={R}; torus will self-intersect"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_line(frm: str, to: str, block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_wedge(frm: str, to: str, split_axis: str,
                    block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse"))
    if a and b:
        dims = _bounds(a, b)
        if any(d < 0 for d in dims):
            out.append(CheckResult("error", "inverted_bounds",
                                   f"wedge frm={a} to={b} has inverted bounds"))
    if split_axis not in ("x", "z"):
        out.append(CheckResult("error", "bad_axis",
                               f"split_axis={split_axis!r} must be 'x' or 'z'"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_spiral(center: str, r_inner: float, r_outer: float,
                     y0: int, y1: int, turns: float,
                     block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r_inner < 0 or r_outer < 0:
        out.append(CheckResult("error", "negative_radius", "spiral radii must be non-negative"))
    if r_outer < r_inner:
        out.append(CheckResult("warn", "spiral_inverted_radii",
                               f"r_outer={r_outer} < r_inner={r_inner}; spiral will shrink inward"))
    if y1 <= y0:
        out.append(CheckResult("error", "inverted_bounds",
                               f"spiral y0={y0} must be < y1={y1}"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_add_plane(axis: str, coord: int, thickness: int,
                    block: str, session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    if axis not in ("x", "y", "z"):
        out.append(CheckResult("error", "bad_axis", f"axis={axis!r} must be x, y, or z"))
    shape = session.grid.shape
    ax_idx = {"x": 0, "y": 1, "z": 2}[axis] if axis in ("x", "y", "z") else 0
    if coord < 0 or coord >= shape[ax_idx]:
        out.append(CheckResult("warn", "out_of_bounds",
                               f"plane coord={coord} is outside axis {axis} range [0,{shape[ax_idx]})"))
    if thickness <= 0:
        out.append(CheckResult("warn", "zero_thickness", f"thickness={thickness} <= 0"))
    out.extend(_check_block(block, registry))
    out.extend(_check_air_block(block, "add"))
    return out


def check_subtract_dome(center: str, r: float, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    return out


def check_subtract_pyramid(center: str, base_half: int, y_base: int, y_apex: int,
                           session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if base_half < 0:
        out.append(CheckResult("error", "negative_radius", f"base_half={base_half} is negative"))
    if y_apex <= y_base:
        out.append(CheckResult("error", "inverted_bounds",
                               f"pyramid y_base={y_base} must be < y_apex={y_apex}"))
    return out


def check_paint_sphere(center: str, r: float, block: str,
                       session: Any, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(center)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"center={center!r} did not parse"))
    if r < 0:
        out.append(CheckResult("error", "negative_radius", f"radius r={r} is negative"))
    out.extend(_check_block(block, registry))
    return out


def check_replace(src: str, dst: str, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.extend(_check_block(src, registry))
    out.extend(_check_block(dst, registry))
    if src == dst:
        out.append(CheckResult("warn", "replace_same",
                               f"src and dst are identical ({src}); replace is a no-op"))
    return out


def check_fill(block: str, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.extend(_check_block(block, registry))
    if block.rstrip("]").lower() in ("minecraft:air", "air"):
        out.append(CheckResult("warn", "fill_air",
                               "fill with air is equivalent to clear; prefer 'clear' for clarity"))
    return out


def check_mirror(axis: str) -> list[CheckResult]:
    if axis not in ("x", "y", "z"):
        return [CheckResult("error", "bad_axis",
                            f"axis={axis!r} must be one of x, y, z")]
    return []


def check_rotate(times: int, axes: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    if axes not in ("xy", "xz", "yz"):
        out.append(CheckResult("error", "bad_axes",
                               f"axes={axes!r} must be one of xy, xz, yz (lowercase)"))
    return out


def check_generate_tree(at: str, height: int, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    c = _coord_tuple(at)
    if c is None:
        out.append(CheckResult("error", "bad_coords", f"at={at!r} did not parse to x,y,z"))
    if height <= 0:
        out.append(CheckResult("error", "nonpositive_height",
                               f"tree height={height} must be positive"))
    if c is not None and any(not (0 <= c[i] < session.grid.shape[i]) for i in range(3)):
        out.append(CheckResult("warn", "out_of_bounds",
                               f"tree base {c} is outside grid {session.grid.shape}"))
    return out


def check_generate_wfc(frm: str, to: str, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    if a is None:
        out.append(CheckResult("error", "bad_coords", f"frm={frm!r} did not parse"))
    if b is None:
        out.append(CheckResult("error", "bad_coords", f"to={to!r} did not parse"))
    if a and b:
        dims = _bounds(a, b)
        if any(d < 0 for d in dims):
            out.append(CheckResult("error", "inverted_bounds",
                                   f"wfc frm={a} to={b} has inverted bounds"))
    return out


def check_export(path: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    if not path:
        out.append(CheckResult("error", "empty_path", "export path is empty"))
    if not any(path.lower().endswith(ext) for ext in (".schem", ".schematic", ".litematic")):
        out.append(CheckResult("warn", "bad_extension",
                               f"path {path!r} does not end in .schem/.schematic/.litematic; "
                               f"WorldEdit/FAWE/Litematica may not recognize it"))
    return out


def check_save(path: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    if not path:
        out.append(CheckResult("error", "empty_path", "save path is empty"))
    return out


def check_load(path: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    if not path:
        out.append(CheckResult("error", "empty_path", "load path is empty"))
        return out
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        out.append(CheckResult("error", "missing_file", f"file not found: {path}"))
    elif p.suffix.lower() != ".json" and not path.endswith(".schematica"):
        out.append(CheckResult("warn", "bad_extension",
                               f"load path {path!r} is not .json or .schematica"))
    return out


def check_preview(out_dir: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    if not out_dir:
        out.append(CheckResult("warn", "empty_outdir",
                               "preview out_dir is empty; defaulting to 'previews'"))
    return out


def _check_block(block: str, registry: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    if not block:
        out.append(CheckResult("error", "empty_block", "block name is empty"))
        return out
    # state value sanity for the common 'axis' property
    if "[" in block and "]" in block:
        states = block[block.index("[") + 1:block.index("]")]
        for part in states.split(","):
            k, _, v = part.partition("=")
            if k.strip().lower() == "axis" and v.strip() and not _known_axis_value(v.strip()):
                out.append(CheckResult("error", "bad_state_value",
                                       f"axis value {v!r} must be x, y, or z"))
    if registry is not None:
        b, err = _parse_blockstate_check(block, registry)
        if err is not None:
            out.append(CheckResult("error", "unknown_block", err))
    return out


def _check_air_block(block: str, op: str) -> list[CheckResult]:
    """Warn when 'add' is used with air (which erases instead of building)."""
    name = block.split("[", 1)[0].strip().lower()
    if name in ("minecraft:air", "air"):
        return [CheckResult("warn", "add_air",
                            f"{op} with air block erases voxels; "
                            f"use 'subtract' to carve intentionally")]
    return []


def _check_outside(frm: str, to: str, session: Any) -> list[CheckResult]:
    out: list[CheckResult] = []
    a = _coord_tuple(frm)
    b = _coord_tuple(to)
    shape = session.grid.shape
    if a is None or b is None:
        return out
    # The box intersects the grid only if ranges overlap on every axis.
    lo = tuple(min(a[i], b[i]) for i in range(3))
    hi = tuple(max(a[i], b[i]) for i in range(3))
    intersects = all(lo[i] < shape[i] and hi[i] >= 0 for i in range(3))
    outside_lo = any(lo[i] < 0 for i in range(3))
    outside_hi = any(hi[i] >= shape[i] for i in range(3))
    if not intersects:
        out.append(CheckResult("warn", "out_of_bounds",
                               f"box frm={a} to={b} is entirely outside grid {shape}; "
                               f"will have no effect"))
    elif outside_lo or outside_hi:
        out.append(CheckResult("warn", "partly_out_of_bounds",
                               f"box frm={a} to={b} extends outside grid {shape}; "
                               f"will be clipped"))
    return out
