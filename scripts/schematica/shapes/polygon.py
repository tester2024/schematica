"""2D shapely polygon extruded into 3D (prism / revolve / loft).

The 2D polygon lives in the (u, v) plane where v maps to height Y and u maps to
either X or Z depending on ``extrude_axis``. Extrusion runs along the third axis.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely import wkt as _wkt
from shapely.geometry import Polygon
from shapely.geometry import shape as shp_geom

from .base import coords_grid


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
