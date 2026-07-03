"""Shape protocol: pure geometry producing a boolean mask over a target grid.

A Shape is geometry-only; it has no knowledge of blocks. Given a target shape
(sx, sy, sz), it returns a boolean numpy array of that shape marking the
voxels it occupies.

Big-map support: shapes optionally implement ``bounds(grid_shape)`` returning
the inclusive world-space bbox ``(x0,y0,z0,x1,y1,z1)`` where the mask could be
True, and ``mask_region(grid_shape, origin, size)`` returning a boolean array
of shape ``size`` covering world coords ``[origin, origin+size)``. The default
``mask_region`` computes the full-grid mask and slices, so subclasses get
correctness for free and can override for sparse local evaluation.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Shape(Protocol):
    def mask(self, shape: tuple[int, int, int]) -> np.ndarray: ...


def in_bounds(coord: tuple[int, int, int], shape: tuple[int, int, int]) -> bool:
    x, y, z = coord
    sx, sy, sz = shape
    return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz


def coords_grid(shape: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return meshgrid X, Y, Z arrays of int indices for the given shape."""
    xs = np.arange(shape[0], dtype=np.int32)
    ys = np.arange(shape[1], dtype=np.int32)
    zs = np.arange(shape[2], dtype=np.int32)
    return np.meshgrid(xs, ys, zs, indexing="ij")


def coords_grid_offset(
    shape: tuple[int, int, int], origin: tuple[int, int, int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return meshgrid X, Y, Z for a sub-grid of ``shape`` offset by ``origin``.

    The returned arrays have shape ``shape`` but their values are world
    coordinates (i.e. local index i maps to world origin[axis]+i).
    """
    xs = np.arange(shape[0], dtype=np.int32) + origin[0]
    ys = np.arange(shape[1], dtype=np.int32) + origin[1]
    zs = np.arange(shape[2], dtype=np.int32) + origin[2]
    return np.meshgrid(xs, ys, zs, indexing="ij")


def bounds_default(shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    """Full-grid bbox (inclusive) for shapes with no tighter bound."""
    return (0, 0, 0, shape[0] - 1, shape[1] - 1, shape[2] - 1)


def intersect_bbox(
    a: tuple[int, int, int, int, int, int],
    b: tuple[int, int, int, int, int, int],
) -> tuple[int, int, int, int, int, int] | None:
    """Intersect two inclusive bboxes; return None if disjoint."""
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    x0, y0, z0 = max(ax0, bx0), max(ay0, by0), max(az0, bz0)
    x1, y1, z1 = min(ax1, bx1), min(ay1, by1), min(az1, bz1)
    if x0 > x1 or y0 > y1 or z0 > z1:
        return None
    return (x0, y0, z0, x1, y1, z1)


def mask_region(
    shape: Shape,
    grid_shape: tuple[int, int, int],
    origin: tuple[int, int, int],
    size: tuple[int, int, int],
) -> np.ndarray:
    """Return the shape's mask restricted to world region [origin, origin+size).

    Default: compute the full-grid mask and slice. Shapes that override
    ``mask_region`` natively compute only the sub-grid for sparsity.
    """
    if hasattr(shape, "mask_region"):
        return np.asarray(shape.mask_region(grid_shape, origin, size))
    full = shape.mask(grid_shape)
    ox, oy, oz = origin
    sx, sy, sz = size
    return full[ox:ox + sx, oy:oy + sy, oz:oz + sz].copy()


def shape_bounds(shape: Shape, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    """Return the inclusive bbox where ``shape`` could be True, or the full grid."""
    if hasattr(shape, "bounds"):
        b = shape.bounds(grid_shape)
        if b is not None:
            return tuple(int(v) for v in b)  # type: ignore[return-value]
    return bounds_default(grid_shape)
