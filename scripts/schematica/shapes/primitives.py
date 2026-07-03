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
    cx: float
    cz: float
    r: float
    y0: int
    y1: int  # inclusive
    axis: str = "y"  # 'x','y','z' -- the cylinder's long axis
    hollow: bool = False
    shell_thickness: float = 1.0

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
    cx: float
    cz: float
    r_base: float
    y_base: int
    y_apex: int  # apex above base; r decreases linearly to 0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r_base)
        x0 = max(int(np.floor(self.cx - r)), 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        y0 = max(min(self.y_base, self.y_apex), 0)
        y1 = min(max(self.y_base, self.y_apex), grid_shape[1] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        h = self.y_apex - self.y_base
        if h == 0:
            return np.zeros(shape, dtype=bool)
        y_rel = (Y - self.y_base).astype(np.float64) / h
        y_clamped = np.clip(y_rel, 0.0, 1.0)
        r_at_y = self.r_base * (1.0 - y_clamped)
        d2 = (X - self.cx) ** 2 + (Z - self.cz) ** 2
        r2 = r_at_y * r_at_y
        in_y = (Y >= min(self.y_base, self.y_apex)) & (Y <= max(self.y_base, self.y_apex))
        return in_y & (d2 <= r2)


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
    """Half-sphere: the upper hemisphere of a sphere (y >= cy)."""
    cx: float
    cy: float
    cz: float
    r: float
    hollow: bool = False
    shell_thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(int(np.floor(self.cy)), 0)
        z0 = max(int(np.floor(self.cz - r)), 0)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
        z1 = min(int(np.ceil(self.cz + r)), grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        d2 = (X - self.cx) ** 2 + (Y - self.cy) ** 2 + (Z - self.cz) ** 2
        r2 = self.r * self.r
        upper = Y >= self.cy
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
    """A semicircular arch in the (x, y) plane, extruded along z.

    The arch is a half-ring from angle 0 to pi, centered at (cx, cy, z0),
    with inner radius `r - thickness/2` and outer radius `r + thickness/2`.
    Extruded from z0 to z1 (inclusive).
    """
    cx: float
    cy: float
    z0: int
    z1: int
    r: float
    thickness: float = 1.0

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        r = float(self.r) + float(self.thickness)
        x0 = max(int(np.floor(self.cx - r)), 0)
        y0 = max(int(np.floor(self.cy - r)), 0)
        z0 = min(self.z0, grid_shape[2] - 1)
        x1 = min(int(np.ceil(self.cx + r)), grid_shape[0] - 1)
        y1 = min(int(np.ceil(self.cy + r)), grid_shape[1] - 1)
        z1 = min(self.z1, grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        X, Y, Z = coords_grid(shape)
        dx = X - self.cx
        dy = Y - self.cy
        dist = np.sqrt(dx * dx + dy * dy)
        ring = (dist >= self.r - self.thickness / 2) & (dist <= self.r + self.thickness / 2)
        upper = Y >= self.cy
        in_z = (Z >= self.z0) & (Z <= self.z1)
        return ring & upper & in_z


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
