"""2D shapely polygon extruded into 3D (prism / revolve / loft).

The 2D polygon lives in the (u, v) plane where v maps to height Y and u maps to
either X or Z depending on ``extrude_axis``. Extrusion runs along the third axis.

SVG path strings (e.g. ``"M 0 0 L 10 0 L 10 10 Z"``) are also supported via
:func:`extrude_polygon` — they are parsed into a shapely polygon with
``shapely.geometry.LineString(...).buffer(0)`` style conversion so curved
``C``/``Q`` cubic and quadratic Bezier segments can be sampled and extruded
without needing an external SVG library.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely import wkt as _wkt
from shapely.geometry import Polygon
from shapely.geometry import shape as shp_geom

from .base import coords_grid


def _sample_svg_path(d: str, steps_per_segment: int = 16) -> list[tuple[float, float]]:
    """Sample an SVG path ``d`` string into a polyline of (x, y) points.

    Supports ``M``/``L`` (lineto), ``H``/``V`` (horizontal/vertical lineto),
    ``C`` (cubic Bezier), ``Q`` (quadratic Bezier), and ``Z`` (close path).
    Absolute and lowercase relative variants are both handled. Curved
    segments are flattened into ``steps_per_segment`` straight pieces.
    """
    import re

    tokens = re.findall(r"[MLCQHVZmlcqhvz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    i = 0
    cur = [0.0, 0.0]
    start = [0.0, 0.0]
    pts: list[tuple[float, float]] = []

    def _num() -> float:
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd in ("M", "L"):
            cur = [_num(), _num()]
            if cmd == "M":
                start = list(cur)
            pts.append((cur[0], cur[1]))
        elif cmd in ("m", "l"):
            cur = [cur[0] + _num(), cur[1] + _num()]
            if cmd == "m":
                start = list(cur)
            pts.append((cur[0], cur[1]))
        elif cmd in ("H", "h"):
            cur = [cur[0] + _num() if cmd == "h" else _num(), cur[1]]
            pts.append((cur[0], cur[1]))
        elif cmd in ("V", "v"):
            cur = [cur[0], cur[1] + _num() if cmd == "v" else _num()]
            pts.append((cur[0], cur[1]))
        elif cmd in ("C", "c"):
            for _ in range(1):  # one cubic segment per C command
                if cmd == "C":
                    c1 = [_num(), _num()]
                    c2 = [_num(), _num()]
                    end = [_num(), _num()]
                else:
                    c1 = [cur[0] + _num(), cur[1] + _num()]
                    c2 = [cur[0] + _num(), cur[1] + _num()]
                    end = [cur[0] + _num(), cur[1] + _num()]
                for s in range(1, steps_per_segment + 1):
                    t = s / steps_per_segment
                    mt = 1 - t
                    x = mt**3 * cur[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * end[0]
                    y = mt**3 * cur[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * end[1]
                    pts.append((x, y))
                cur = end
        elif cmd in ("Q", "q"):
            if cmd == "Q":
                c1 = [_num(), _num()]
                end = [_num(), _num()]
            else:
                c1 = [cur[0] + _num(), cur[1] + _num()]
                end = [cur[0] + _num(), cur[1] + _num()]
            for s in range(1, steps_per_segment + 1):
                t = s / steps_per_segment
                mt = 1 - t
                x = mt**2 * cur[0] + 2 * mt * t * c1[0] + t**2 * end[0]
                y = mt**2 * cur[1] + 2 * mt * t * c1[1] + t**2 * end[1]
                pts.append((x, y))
            cur = end
        elif cmd in ("Z", "z"):
            if pts and (start[0], start[1]) != pts[-1]:
                pts.append((start[0], start[1]))
            cur = list(start)
        else:
            raise ValueError(f"unsupported SVG path command: {cmd!r}")
    return pts


def _svg_path_to_polygon(d: str, steps_per_segment: int = 16) -> Polygon:
    """Convert an SVG path ``d`` string into a closed shapely Polygon.

    The path is sampled into a polyline, then closed and buffered to form a
    valid polygon. Self-intersecting paths are repaired by ``buffer(0)``.
    """
    pts = _sample_svg_path(d, steps_per_segment=steps_per_segment)
    if len(pts) < 3:
        raise ValueError(f"SVG path {d!r} does not define a closed polygon")
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    poly = Polygon(pts).buffer(0)
    if not isinstance(poly, Polygon) or poly.is_empty:
        raise ValueError(f"SVG path {d!r} could not be converted to a valid polygon")
    return poly


def _load_polygon(src: str | Path | dict[str, object]) -> Polygon:
    if isinstance(src, str) and src.strip().startswith("POLYGON"):
        return _wkt.loads(src)
    if isinstance(src, str) and src.strip().startswith("{"):
        import json

        return shp_geom(json.loads(src))
    if isinstance(src, dict):
        return shp_geom(src)
    if isinstance(src, Path):
        import json

        with Path(src).open("r", encoding="utf-8") as fh:
            return shp_geom(json.load(fh))
    if isinstance(src, str):
        # Treat as an SVG path "d" string if it looks like one.
        stripped = src.strip()
        if stripped and stripped[0] in "Mm":
            return _svg_path_to_polygon(stripped)
    raise TypeError("unsupported polygon source")


@dataclass(frozen=True)
class Extrude:
    polygon: Polygon
    x0: int = 0
    y0: int = 0
    z0: int = 0
    extrude_axis: str = "z"  # extrude direction
    length: int = 1
    flip: bool = False

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        # polygon coords: u in [0..), v in [0..) mapping to X/Y; extrude along Z
        # We sample the polygon against world coords (X - x0, Y - y0).
        pts = np.array(self.polygon.exterior.coords)
        u_min, v_min = pts[:, 0].min(), pts[:, 1].min()
        u_max, v_max = pts[:, 0].max(), pts[:, 1].max()
        # Build a 2-D containment lookup on integer grid of (u, v).
        u_range = int(np.floor(u_max - u_min)) + 2
        v_range = int(np.floor(v_max - v_min)) + 2
        if u_range <= 0 or v_range <= 0:
            return np.zeros(shape, dtype=bool)
        from shapely.geometry import Point

        contains = np.zeros((u_range, v_range), dtype=bool)
        for i in range(u_range):
            for j in range(v_range):
                p = Point(u_min + i + 0.5, v_min + j + 0.5)
                if self.polygon.contains(p):
                    contains[i, j] = True
        # Map into world space
        # world u = X - x0 ; world v = Y - y0
        wi = (X - self.x0).astype(np.int64)
        wj = (Y - self.y0).astype(np.int64)
        ui = wi - int(np.floor(u_min))
        vj = wj - int(np.floor(v_min))
        in_uv = (ui >= 0) & (ui < u_range) & (vj >= 0) & (vj < v_range)
        # Sample
        safe_ui = np.clip(ui, 0, u_range - 1)
        safe_vj = np.clip(vj, 0, v_range - 1)
        sample = contains[safe_ui, safe_vj]
        in_poly = in_uv & sample
        # Extrude along axis
        if self.extrude_axis == "z":
            in_extr = (Z >= self.z0) & (Z < self.z0 + self.length)
        elif self.extrude_axis == "x":
            in_extr = (X >= self.x0) & (X < self.x0 + self.length)
        elif self.extrude_axis == "y":
            in_extr = (Y >= self.y0) & (Y < self.y0 + self.length)
        else:
            raise ValueError("extrude_axis must be x/y/z")
        return in_poly & in_extr


def extrude_polygon(
    polygon: Polygon | str | Path | dict[str, object],
    origin: tuple[int, int, int] = (0, 0, 0),
    extrude_axis: str = "z",
    length: int = 1,
) -> Extrude:
    if not isinstance(polygon, Polygon):
        polygon = _load_polygon(polygon)
    return Extrude(
        polygon=polygon,
        x0=origin[0],
        y0=origin[1],
        z0=origin[2],
        extrude_axis=extrude_axis,
        length=length,
    )
