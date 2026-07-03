"""Shape protocol: pure geometry producing a boolean mask over a target grid.

A Shape is geometry-only; it has no knowledge of blocks. Given a target shape
(sx, sy, sz), it returns a boolean numpy array of that shape marking the
voxels it occupies.
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
