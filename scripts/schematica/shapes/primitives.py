"""Primitive analytic shapes (box, sphere, ellipsoid, cylinder, cone, pyramid,
torus, plane, wedge, line). All produce boolean masks via vectorized numpy.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import coords_grid


def _make_mask(shape: tuple[int, int, int]) -> np.ndarray:
    return np.zeros(shape, dtype=bool)


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    z0: int
    x1: int  # inclusive
    y1: int
    z1: int
    hollow: bool = False
    wall_thickness: int = 1

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        x0 = max(self.x0, 0)
        y0 = max(self.y0, 0)
        z0 = max(self.z0, 0)
        x1 = min(self.x1, grid_shape[0] - 1)
        y1 = min(self.y1, grid_shape[1] - 1)
        z1 = min(self.z1, grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask_region(self, grid_shape: tuple[int, int, int],
                    origin: tuple[int, int, int],
                    size: tuple[int, int, int]) -> np.ndarray:
        ox, oy, oz = origin
        sx, sy, sz = size
        m = np.zeros((sx, sy, sz), dtype=bool)
        x0 = max(self.x0, ox)
        y0 = max(self.y0, oy)
        z0 = max(self.z0, oz)
        x1 = min(self.x1, ox + sx - 1)
        y1 = min(self.y1, oy + sy - 1)
        z1 = min(self.z1, oz + sz - 1)
        if x1 < x0 or y1 < y0 or z1 < z0:
            return m
        lx0, ly0, lz0 = x0 - ox, y0 - oy, z0 - oz
        lx1, ly1, lz1 = x1 - ox, y1 - oy, z1 - oz
        if self.hollow and self.wall_thickness > 0:
            m[lx0:lx1 + 1, ly0:ly1 + 1, lz0:lz1 + 1] = True
            t = self.wall_thickness
            ix0, iy0, iz0 = lx0 + t, ly0 + t, lz0 + t
            ix1, iy1, iz1 = lx1 - t, ly1 - t, lz1 - t
            if ix0 <= ix1 and iy0 <= iy1 and iz0 <= iz1:
                m[ix0:ix1 + 1, iy0:iy1 + 1, iz0:iz1 + 1] = False
        else:
            m[lx0:lx1 + 1, ly0:ly1 + 1, lz0:lz1 + 1] = True
        return m

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = _make_mask(shape)
        x0, y0, z0 = max(self.x0, 0), max(self.y0, 0), max(self.z0, 0)
        x1, y1, z1 = min(self.x1, shape[0] - 1), min(self.y1, shape[1] - 1), min(self.z1, shape[2] - 1)
        if x1 < x0 or y1 < y0 or z1 < z0:
            return m
        if self.hollow and self.wall_thickness > 0:
            m[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1] = True
            t = self.wall_thickness
            ix0, iy0, iz0 = x0 + t, y0 + t, z0 + t
            ix1, iy1, iz1 = x1 - t, y1 - t, z1 - t
            if ix0 <= ix1 and iy0 <= iy1 and iz0 <= iz1:
                m[ix0:ix1 + 1, iy0:iy1 + 1, iz0:iz1 + 1] = False
        else:
            m[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1] = True
        return m


@dataclass(frozen=True)
class Sphere:
    cx: float
    cy: float
    cz: float
    r: float
    hollow: bool = False
    shell_thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(int(np.floor(self.cy - r)), 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        d2 = (X - self.cx) ** 2 + (Y - self.cy) ** 2 + (Z - self.cz) ** 2
        r2 = self.r * self.r
        m = d2 <= r2
        if self.hollow:
            ri = max(self.r - self.shell_thickness, 0.0)
            inner = d2 <= ri * ri
            m = m & ~inner
        return m


@dataclass(frozen=True)
class Ellipsoid:
    cx: float
    cy: float
    cz: float
    rx: float
    ry: float
    rz: float
    hollow: bool = False
    shell_thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = max(self.rx, self.ry, self.rz)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(int(np.floor(self.cy - r)), 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        rx, ry, rz = self.rx, self.ry, self.rz
        if rx <= 0 or ry <= 0 or rz <= 0:
            return np.zeros(shape, dtype=bool)
        d = ((X - self.cx) / rx) ** 2 + ((Y - self.cy) / ry) ** 2 + ((Z - self.cz) / rz) ** 2
        m = d <= 1.0
        if self.hollow:
            rx2 = max(rx - self.shell_thickness, 0.0)
            ry2 = max(ry - self.shell_thickness, 0.0)
            rz2 = max(rz - self.shell_thickness, 0.0)
            inner = (
                ((X - self.cx) / max(rx2, 1e-9)) ** 2
                + ((Y - self.cy) / max(ry2, 1e-9)) ** 2
                + ((Z - self.cz) / max(rz2, 1e-9)) ** 2
            ) <= 1.0
            m = m & ~inner
        return m


@dataclass(frozen=True)
class Cylinder:
    """Right circular cylinder with an arbitrary long axis.

    Parameters
    ----------
    cx, cz : float
        Cross-section center coordinates. For ``axis="y"`` these are the
        (X, Z) center of the circular cross-section. For ``axis="x"`` they
        are the (Y, Z) center. For ``axis="z"`` they are the (X, Y) center.
    r : float
        Cross-section radius.
    y0, y1 : int
        Along-axis extent (inclusive). For ``axis="y"`` these are Y bounds;
        for ``axis="x"`` they are X bounds; for ``axis="z"`` they are Z
        bounds. The names are retained for backward compatibility — prefer
        the explicit ``start``/``end`` aliases for new code.
    start, end : int | None
        Explicit aliases for ``y0``/``y1`` (the along-axis extent). When
        provided they override ``y0``/``y1``. This removes the surprise where
        ``y0``/``y1`` secretly mean X or Z bounds for non-Y axes.
    axis : str
        The cylinder's long axis: ``"y"`` (default), ``"x"`` or ``"z"``.
    hollow : bool
        Keep only a tube shell of ``shell_thickness`` voxels.
    shell_thickness : float
        Thickness of the hollow tube wall.
    """
    cx: float
    cz: float
    r: float
    y0: int = 0
    y1: int = 0  # inclusive
    axis: str = "y"  # 'x','y','z' -- the cylinder's long axis
    hollow: bool = False
    shell_thickness: float = 1.0
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y", "z"):
            raise ValueError(f"axis must be 'x', 'y', or 'z'; got {self.axis!r}")
        if self.start is not None or self.end is not None:
            s = self.start if self.start is not None else self.y0
            e = self.end if self.end is not None else self.y1
            object.__setattr__(self, "y0", s)
            object.__setattr__(self, "y1", e)

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r)
        if self.axis == "y":
            x0 = max(int(np.floor(self.cx - r)), 0)
            z0 = max(int(np.floor(self.cz - r)), 0)
            x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
            z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
            y0 = max(min(self.y0, self.y1), 0)
            y1 = min(max(self.y0, self.y1), grid_shape[1] - 1)
        elif self.axis == "x":
            # cross-section in (y, z); long axis = x in [min(y0,y1)..max] -- but
            # y0/y1 are reused as the along-axis extent.
            y0c = max(int(np.floor(self.cx - r)), 0)
            z0 = max(int(np.floor(self.cz - r)), 0)
            y1c = min(int(np.ceil(self.cx + r)), grid_shape[1] - 1)
            z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
            x0 = max(min(self.y0, self.y1), 0)
            x1 = min(max(self.y0, self.y1), grid_shape[0] - 1)
            return (x0, y0c, z0, x1, y1c, z1)
        else:  # axis == "z"
            x0 = max(int(np.floor(self.cx - r)), 0)
            y0c = max(int(np.floor(self.cz - r)), 0)
            x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
            y1c = min(int(np.ceil(self.cz + r)), grid_shape[1] - 1)
            z0 = max(min(self.y0, self.y1), 0)
            z1 = min(max(self.y0, self.y1), grid_shape[2] - 1)
            return (x0, y0c, z0, x1, y1c, z1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        if self.axis == "y":
            d2 = (X - self.cx) ** 2 + (Z - self.cz) ** 2
            along = (Y >= self.y0) & (Y <= self.y1)
        elif self.axis == "x":
            # cross-section in (Y, Z); long axis = X in [y0..y1] (reused names)
            d2 = (Y - self.cx) ** 2 + (Z - self.cz) ** 2
            along = (X >= self.y0) & (X <= self.y1)
        else:  # "z"
            d2 = (X - self.cx) ** 2 + (Y - self.cz) ** 2
            along = (Z >= self.y0) & (Z <= self.y1)
        r2 = self.r * self.r
        radial = d2 <= r2
        m = along & radial
        if self.hollow:
            ri = max(self.r - self.shell_thickness, 0.0)
            inner = d2 <= ri * ri
            m = m & ~inner
        return m


@dataclass(frozen=True)
class Cone:
    """Right circular cone. The base sits at ``y_base`` (or along-axis coord)
    and tapers to a point at ``y_apex`` (or the apex along-axis coord).

    Parameters
    ----------
    cx, cz : float
        Cross-section center (X, Z) for ``axis="y"``; (Y, Z) for ``axis="x"``;
        (X, Y) for ``axis="z"``.
    r_base : float
        Base radius.
    y_base, y_apex : int
        Along-axis coords of the base and apex. For ``axis="y"`` these are Y
        values; for ``axis="x"`` they are X values; for ``axis="z"`` they are
        Z values. The names are retained for backward compatibility.
    axis : str
        ``"y"`` (default, vertical), ``"x"`` or ``"z"``.
    """
    cx: float
    cz: float
    r_base: float
    y_base: int
    y_apex: int  # apex above base; r decreases linearly to 0
    axis: str = "y"

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y", "z"):
            raise ValueError(f"axis must be 'x', 'y', or 'z'; got {self.axis!r}")

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r_base)
        if self.axis == "y":
            x0 = max(int(np.floor(self.cx - r)), 0)
            z0 = max(int(np.floor(self.cz - r)), 0)
            x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
            z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
            y0 = max(min(self.y_base, self.y_apex), 0)
            y1 = min(max(self.y_base, self.y_apex), grid_shape[1] - 1)
            return (x0, y0, z0, x1, y1, z1)
        if self.axis == "x":
            # cross-section in (Y, Z) centered (cx, cz); long axis = X
            y0c = max(int(np.floor(self.cx - r)), 0)
            z0 = max(int(np.floor(self.cz - r)), 0)
            y1c = min(int(np.ceil(self.cx + r)), grid_shape[1] - 1)
            z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
            x0 = max(min(self.y_base, self.y_apex), 0)
            x1 = min(max(self.y_base, self.y_apex), grid_shape[0] - 1)
            return (x0, y0c, z0, x1, y1c, z1)
        # axis == "z": cross-section in (X, Y) centered (cx, cz); long axis = Z
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0c = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1c = min(int(np.ceil(self.cz + r)), grid_shape[1] - 1)
        z0 = max(min(self.y_base, self.y_apex), 0)
        z1 = min(max(self.y_base, self.y_apex), grid_shape[2] - 1)
        return (x0, y0c, z0, x1, y1c, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        h = self.y_apex - self.y_base
        if h == 0:
            return np.zeros(shape, dtype=bool)
        if self.axis == "y":
            along = Y
            d2 = (X - self.cx) ** 2 + (Z - self.cz) ** 2
        elif self.axis == "x":
            along = X
            d2 = (Y - self.cx) ** 2 + (Z - self.cz) ** 2
        else:  # "z"
            along = Z
            d2 = (X - self.cx) ** 2 + (Y - self.cz) ** 2
        y_rel = (along - self.y_base).astype(np.float64) / h
        y_clamped = np.clip(y_rel, 0.0, 1.0)
        r_at = self.r_base * (1.0 - y_clamped)
        r2 = r_at * r_at
        in_axis = (along >= min(self.y_base, self.y_apex)) & (along <= max(self.y_base, self.y_apex))
        return in_axis & (d2 <= r2)


@dataclass(frozen=True)
class Pyramid:
    x0: int
    z0: int
    base_half: int
    y_base: int
    y_apex: int

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        bh = int(self.base_half)
        x0 = max(self.x0 - bh, 0)
        z0 = max(self.z0 - bh, 0)
        x1 = min(self.x0 + bh, grid_shape[0] - 1)
        z1 = min(self.z0 + bh, grid_shape[2] - 1)
        y0 = max(min(self.y_base, self.y_apex), 0)
        y1 = min(max(self.y_base, self.y_apex), grid_shape[1] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        h = self.y_apex - self.y_base
        if h == 0:
            return np.zeros(shape, dtype=bool)
        y_rel = np.clip((Y - self.y_base).astype(np.float64) / h, 0.0, 1.0)
        half = self.base_half * (1.0 - y_rel)
        in_y = (Y >= min(self.y_base, self.y_apex)) & (Y <= max(self.y_base, self.y_apex))
        in_x = np.abs(X - float(self.x0)) <= half
        in_z = np.abs(Z - float(self.z0)) <= half
        return in_y & in_x & in_z


@dataclass(frozen=True)
class Torus:
    cx: float
    cy: float
    cz: float
    R: float  # major radius (ring center distance)
    r: float  # minor radius (tube)

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        Rr = self.R + self.r
        x0 = max(int(np.floor(self.cx - Rr)), 0)
        y0 = max(int(np.floor(self.cy - self.r)), 0)
        z0 = max(int(np.floor(self.cz - Rr)), 0)
        x1 = min(int(np.ceil(self.cx + Rr)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + self.r)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + Rr)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        dx = X - self.cx
        dz = Z - self.cz
        ring_dist = np.sqrt(dx * dx + dz * dz)
        tube_axis = np.sqrt(np.maximum((ring_dist - self.R) ** 2, 0.0))
        d2 = tube_axis ** 2 + (Y - self.cy) ** 2
        return d2 <= self.r * self.r


@dataclass(frozen=True)
class Plane:
    """Filled axis-aligned plane slice: thickness 1, perpendicular to ``axis`` at ``coord``."""
    axis: str  # 'x','y','z'
    coord: int
    thickness: int = 1

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        ax = {"x": 0, "y": 1, "z": 2}[self.axis]
        t = max(self.thickness, 1)
        lo = max(self.coord - t // 2, 0)
        hi = min(self.coord + t // 2 + (t % 2), grid_shape[ax] - 1)
        full = [0, 0, 0, grid_shape[0] - 1, grid_shape[1] - 1, grid_shape[2] - 1]
        full[ax * 2] = lo
        full[ax * 2 + 3] = hi
        return (full[0], full[1], full[2], full[3], full[4], full[5])

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        ax = {"x": 0, "y": 1, "z": 2}[self.axis]
        t = max(self.thickness, 1)
        center = self.coord
        lo = max(center - t // 2, 0)
        hi = min(center + t // 2 + (t % 2), shape[ax])
        sl = [slice(None), slice(None), slice(None)]
        sl[ax] = slice(lo, hi)
        m[tuple(sl)] = True
        return m


@dataclass(frozen=True)
class Wedge:
    """Triangular prism filling half of a box along an axis."""
    x0: int
    y0: int
    z0: int
    x1: int
    y1: int
    z1: int
    split_axis: str = "x"  # axis along which the diagonal runs

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return (min(self.x0, self.x1), min(self.y0, self.y1), min(self.z0, self.z1),
                min(max(self.x0, self.x1), grid_shape[0] - 1),
                min(max(self.y0, self.y1), grid_shape[1] - 1),
                min(max(self.z0, self.z1), grid_shape[2] - 1))

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        box = Box(self.x0, self.y0, self.z0, self.x1, self.y1, self.z1).mask(shape)
        X, Y, Z = coords_grid(shape)
        if self.split_axis == "x":
            t = (X - self.x0) / max(self.x1 - self.x0, 1)
            diag = (Y - self.y0) <= (1 - t) * (self.y1 - self.y0)
        elif self.split_axis == "z":
            t = (Z - self.z0) / max(self.z1 - self.z0, 1)
            diag = (Y - self.y0) <= (1 - t) * (self.y1 - self.y0)
        else:
            raise ValueError("split_axis must be 'x' or 'z'")
        return box & diag


@dataclass(frozen=True)
class Line:
    """A 1-voxel-thick line between two points (Bresenham-style on a 3D mask)."""
    x0: int
    y0: int
    z0: int
    x1: int
    y1: int
    z1: int

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        x0 = max(min(self.x0, self.x1), 0)
        y0 = max(min(self.y0, self.y1), 0)
        z0 = max(min(self.z0, self.z1), 0)
        x1 = min(max(self.x0, self.x1), grid_shape[0] - 1)
        y1 = min(max(self.y0, self.y1), grid_shape[1] - 1)
        z1 = min(max(self.z0, self.z1), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        dx = abs(self.x1 - self.x0)
        dy = abs(self.y1 - self.y0)
        dz = abs(self.z1 - self.z0)
        steps = max(dx, dy, dz, 1)
        for i in range(steps + 1):
            t = i / steps
            x = round(self.x0 + (self.x1 - self.x0) * t)
            y = round(self.y0 + (self.y1 - self.y0) * t)
            z = round(self.z0 + (self.z1 - self.z0) * t)
            if 0 <= x < shape[0] and 0 <= y < shape[1] and 0 <= z < shape[2]:
                m[x, y, z] = True
        return m


@dataclass(frozen=True)
class Dome:
    """Half-sphere: the upper hemisphere of a sphere (y >= cy for axis="y").

    For ``axis="x"`` the dome is the +X hemisphere (X >= cx); for ``axis="z"``
    the +Z hemisphere (Z >= cz). Useful for wall-mounted caps and horizontal
    apses without needing ``Rotated90``.
    """
    cx: float
    cy: float
    cz: float
    r: float
    hollow: bool = False
    shell_thickness: float = 1.0
    axis: str = "y"

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y", "z"):
            raise ValueError(f"axis must be 'x', 'y', or 'z'; got {self.axis!r}")

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(int(np.floor(self.cy - r)), 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        if self.axis == "y":
            y0 = max(int(np.floor(self.cy)), 0)
        elif self.axis == "x":
            x0 = max(int(np.floor(self.cx)), 0)
        else:  # "z"
            z0 = max(int(np.floor(self.cz)), 0)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        d2 = (X - self.cx) ** 2 + (Y - self.cy) ** 2 + (Z - self.cz) ** 2
        r2 = self.r * self.r
        if self.axis == "y":
            upper = Y >= self.cy
        elif self.axis == "x":
            upper = X >= self.cx
        else:  # "z"
            upper = Z >= self.cz
        m = (d2 <= r2) & upper
        if self.hollow:
            ri = max(self.r - self.shell_thickness, 0.0)
            inner = (d2 <= ri * ri) & upper
            m = m & ~inner
        return m


@dataclass(frozen=True)
class Helix:
    """A 1-voxel helical curve winding around a vertical axis.

    Turns `turns` times around the y axis from `y0` to `y1`, at radius `r`
    centered on (cx, cz). `thickness` widens the strand.
    """
    cx: float
    cy: float
    cz: float
    r: float
    y0: int
    y1: int
    turns: float = 3.0
    thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(self.y0, 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(self.y1, grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        height = self.y1 - self.y0
        if height <= 0:
            return m
        steps = max(height * 8, 64)
        t = np.linspace(0, 1, steps)
        ys = self.y0 + t * height
        angles = t * self.turns * 2 * np.pi
        xs = self.cx + self.r * np.cos(angles)
        zs = self.cz + self.r * np.sin(angles)
        th = max(self.thickness, 0.5)
        for x, y, z in zip(xs, ys, zs, strict=False):
            xi, yi, zi = int(round(x)), int(round(y)), int(round(z))
            for dx in range(-int(th), int(th) + 1):
                for dy in range(-int(th), int(th) + 1):
                    for dz in range(-int(th), int(th) + 1):
                        if dx * dx + dy * dy + dz * dz <= th * th:
                            nx, ny, nz = xi + dx, yi + dy, zi + dz
                            if 0 <= nx < shape[0] and 0 <= ny < shape[1] and 0 <= nz < shape[2]:
                                m[nx, ny, nz] = True
        return m


@dataclass(frozen=True)
class Arch:
    """A semicircular arch in a coordinate plane, extruded along the third axis.

    The arch is a half-ring from angle 0 to pi. ``plane`` selects which
    coordinate plane the ring lies in:

    * ``"xy"`` (default): ring in the (X, Y) plane centered at (cx, cy),
      extruded along Z from ``z0`` to ``z1``. Backward-compatible with the
      legacy signature.
    * ``"xz"``: ring in the (X, Z) plane centered at (cx, cz), extruded along
      Y from ``z0`` to ``z1`` (reinterpreted as Y bounds).
    * ``"yz"``: ring in the (Y, Z) plane centered at (cy, cz), extruded
      along X from ``z0`` to ``z1`` (reinterpreted as X bounds).

    For non-default planes, ``cx``/``cy``/``z0``/``z1`` are reinterpreted as
    the ring-center coords and extrusion extent of the two non-extrusion
    axes (the third axis is the extrusion axis). The naming follows the
    legacy convention so existing call sites keep working.
    """
    cx: float
    cy: float
    z0: int
    z1: int
    r: float
    thickness: float = 1.0
    plane: str = "xy"

    def __post_init__(self) -> None:
        if self.plane not in ("xy", "xz", "yz"):
            raise ValueError(f"plane must be 'xy', 'xz', or 'yz'; got {self.plane!r}")

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r) + float(self.thickness)
        if self.plane == "xy":
            x0 = max(int(np.floor(self.cx - r)), 0)
            y0 = max(int(np.floor(self.cy - r)), 0)
            x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
            y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
            z0 = max(min(self.z0, self.z1), 0)
            z1 = min(max(self.z0, self.z1), grid_shape[2] - 1)
            return (x0, y0, z0, x1, y1, z1)
        if self.plane == "xz":
            x0 = max(int(np.floor(self.cx - r)), 0)
            z0b = max(int(np.floor(self.cy - r)), 0)
            x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
            z1b = min(int(np.ceil(self.cy + r)), grid_shape[2] - 1)
            y0 = max(min(self.z0, self.z1), 0)
            y1 = min(max(self.z0, self.z1), grid_shape[1] - 1)
            return (x0, y0, z0b, x1, y1, z1b)
        # "yz": ring in (Y, Z) centered at (cx, cz); extrude along X
        y0 = max(int(np.floor(self.cx - r)), 0)
        z0b = max(int(np.floor(self.cy - r)), 0)
        y1 = min(int(np.ceil(self.cx + r)), grid_shape[1] - 1)
        z1b = min(int(np.ceil(self.cy + r)), grid_shape[2] - 1)
        x0 = max(min(self.z0, self.z1), 0)
        x1 = min(max(self.z0, self.z1), grid_shape[0] - 1)
        return (x0, y0, z0b, x1, y1, z1b)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        if self.plane == "xy":
            a = X - self.cx
            b = Y - self.cy
            dist = np.sqrt(a * a + b * b)
            upper = Y >= self.cy
            in_ext = (Z >= self.z0) & (Z <= self.z1)
        elif self.plane == "xz":
            a = X - self.cx
            b = Z - self.cy
            dist = np.sqrt(a * a + b * b)
            upper = Z >= self.cy
            in_ext = (Y >= self.z0) & (Y <= self.z1)
        else:  # "yz"
            a = Y - self.cx
            b = Z - self.cy
            dist = np.sqrt(a * a + b * b)
            upper = Z >= self.cy
            in_ext = (X >= self.z0) & (X <= self.z1)
        ring = (dist >= self.r - self.thickness / 2) & (dist <= self.r + self.thickness / 2)
        return ring & upper & in_ext


@dataclass(frozen=True)
class Spiral:
    """A flat 2D spiral in the (x, z) plane at height y, extruded vertically.

    The spiral starts at radius `r_inner` and grows to `r_outer` over `turns`
    revolutions. Filled from `y0` to `y1`.
    """
    cx: float
    cz: float
    y0: int
    y1: int
    r_inner: float
    r_outer: float
    turns: float = 2.0
    thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = max(float(self.r_inner), float(self.r_outer)) + float(self.thickness)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(self.y0, 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(self.y1, grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        steps = max(int(self.turns * 64), 128)
        t = np.linspace(0, 1, steps)
        r = self.r_inner + t * (self.r_outer - self.r_inner)
        angles = t * self.turns * 2 * np.pi
        xs = self.cx + r * np.cos(angles)
        zs = self.cz + r * np.sin(angles)
        th = max(self.thickness, 0.5)
        for x, z in zip(xs, zs, strict=False):
            xi, zi = int(round(x)), int(round(z))
            for dx in range(-int(th), int(th) + 1):
                for dz in range(-int(th), int(th) + 1):
                    if dx * dx + dz * dz <= th * th:
                        for y in range(self.y0, self.y1 + 1):
                            nx, ny, nz = xi + dx, y, zi + dz
                            if 0 <= nx < shape[0] and 0 <= ny < shape[1] and 0 <= nz < shape[2]:
                                m[nx, ny, nz] = True
        return m


@dataclass(frozen=True)
class Staircase:
    """A straight staircase rising along an axis.

    Each step is `step_width` voxels wide, `step_depth` voxels deep, and the
    staircase rises `step_height` per step. Total steps = (y1 - y0) // step_height.
    """
    x0: int
    y0: int
    z0: int
    y1: int
    step_width: int = 3
    step_depth: int = 2
    step_height: int = 1
    axis: str = "x"  # 'x' or 'z' direction of travel

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        x_max = self.x0 + (self.y1 - self.y0) // max(self.step_height, 1) * self.step_depth + self.step_depth
        z_max = self.z0 + self.step_width
        x1 = min(max(self.x0, x_max - 1), grid_shape[0] - 1) if self.axis == "x" else min(self.x0 + self.step_width - 1, grid_shape[0] - 1)
        z1 = min(max(self.z0, z_max - 1), grid_shape[2] - 1) if self.axis == "z" else min(self.z0 + self.step_width - 1, grid_shape[2] - 1)
        x0 = min(self.x0, x1)
        z0 = min(self.z0, z1)
        y0 = max(self.y0, 0)
        y1 = min(self.y1, grid_shape[1] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        total_rise = self.y1 - self.y0
        if total_rise <= 0:
            return m
        n_steps = total_rise // max(self.step_height, 1)
        for i in range(n_steps + 1):
            y = self.y0 + i * self.step_height
            if self.axis == "x":
                xa = self.x0 + i * self.step_depth
                xb = xa + self.step_depth - 1
                za = self.z0
                zb = self.z0 + self.step_width - 1
            else:
                za = self.z0 + i * self.step_depth
                zb = za + self.step_depth - 1
                xa = self.x0
                xb = self.x0 + self.step_width - 1
            xa, xb = min(xa, xb), max(xa, xb)
            za, zb = min(za, zb), max(za, zb)
            for xx in range(max(xa, 0), min(xb + 1, shape[0])):
                for yy in range(max(y, 0), min(y + 1, shape[1])):
                    for zz in range(max(za, 0), min(zb + 1, shape[2])):
                        m[xx, yy, zz] = True
        return m


@dataclass(frozen=True)
class BezierCurve:
    """A 1-voxel-thick 3D Bezier curve extruded into a tube.

    Supports quadratic (3 control points) and cubic (4 control points)
    Bezier curves. ``thickness`` widens the strand into a tube of that
    radius (in voxels). Useful for organic paths, winding rivers, custom
    bridge cables, and decorative arches that Bresenham lines cannot express.

    Parameters
    ----------
    p0, p1, p2, p3 : tuple[int, int, int]
        Control points. ``p3`` is optional — omit it (or pass ``None``) for
        a quadratic Bezier through ``p0``, ``p1``, ``p2``.
    thickness : float
        Tube radius in voxels (0.5 = single-voxel strand).
    samples : int
        Number of points sampled along the curve (more = smoother).
    """
    p0: tuple[int, int, int]
    p1: tuple[int, int, int]
    p2: tuple[int, int, int]
    p3: tuple[int, int, int] | None = None
    thickness: float = 0.5
    samples: int = 128

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        pts = [self.p0, self.p1, self.p2]
        if self.p3 is not None:
            pts.append(self.p3)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        t = max(self.thickness, 0)
        x0 = max(int(np.floor(min(xs) - t)), 0)
        y0 = max(int(np.floor(min(ys) - t)), 0)
        z0 = max(int(np.floor(min(zs) - t)), 0)
        x1 = min(int(np.ceil(max(xs) + t)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(max(ys) + t)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(max(zs) + t)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        m = np.zeros(shape, dtype=bool)
        t = np.linspace(0.0, 1.0, max(self.samples, 2))
        p0 = np.array(self.p0, dtype=np.float64)
        p1 = np.array(self.p1, dtype=np.float64)
        p2 = np.array(self.p2, dtype=np.float64)
        if self.p3 is None:
            # Quadratic: B(t) = (1-t)^2 P0 + 2(1-t)t P1 + t^2 P2
            mt = 1.0 - t
            pts = ((mt[:, None] ** 2) * p0
                   + (2 * mt[:, None] * t[:, None]) * p1
                   + (t[:, None] ** 2) * p2)
        else:
            # Cubic: B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
            p3 = np.array(self.p3, dtype=np.float64)
            mt = 1.0 - t
            pts = (
                (mt[:, None] ** 3) * p0
                + (3 * mt[:, None] ** 2 * t[:, None]) * p1
                + (3 * mt[:, None] * t[:, None] ** 2) * p2
                + (t[:, None] ** 3) * p3
            )
        th = max(self.thickness, 0.5)
        for x, y, z in pts:
            xi, yi, zi = int(round(x)), int(round(y)), int(round(z))
            r = int(np.ceil(th))
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if dx * dx + dy * dy + dz * dz <= th * th:
                            nx, ny, nz = xi + dx, yi + dy, zi + dz
                            if 0 <= nx < shape[0] and 0 <= ny < shape[1] and 0 <= nz < shape[2]:
                                m[nx, ny, nz] = True
        return m
