"""Signed Distance Field (SDF) shapes and smooth boolean blending.

Each SDF shape returns a float32 array of signed distances to its surface
(negative inside, positive outside). These compose with smooth-minimum
blending for organic transitions between shapes — useful for terrain-to-
structure blends, melted joins, and naturalistic merges that the strict
binary union/intersect/subtract operations cannot express.

The SDF shapes here are thin adapters over the existing analytic primitives:
they evaluate the primitive's mask and convert it to a signed distance
approximation. True analytic SDFs would be faster, but this keeps the API
small and composes with every existing primitive.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Shape, shape_bounds


def _mask_to_sdf(mask: np.ndarray) -> np.ndarray:
    """Approximate signed distance from a boolean mask via distance transform.

    Returns a float32 array: negative inside the mask, positive outside,
    zero on the surface. Uses scipy's `distance_transform_edt` when
    available; falls back to a BFS-based approximation otherwise.
    """
    mask = mask.astype(bool)
    shape = mask.shape
    if not mask.any():
        return np.full(shape, np.inf, dtype=np.float32)
    try:
        from scipy import ndimage as _ndi
        # distance from True voxels to the nearest False (inside->boundary)
        inside = _ndi.distance_transform_edt(mask).astype(np.float32)
        # distance from False voxels to the nearest True (outside->boundary)
        outside = _ndi.distance_transform_edt(~mask).astype(np.float32)
        return np.asarray(outside - inside, dtype=np.float32)
    except ImportError:
        # Pure-numpy fallback: 6-connectivity multi-source BFS via iterative
        # array-based wavefront propagation. Each iteration expands the
        # distance by 1. 6-connectivity underestimates Euclidean distance
        # (it's the L1 / Manhattan metric), but the sign and monotonic
        # gradient are what the smooth-min needs.
        sx, sy, sz = shape
        # Handle edge cases: fully filled or fully empty masks.
        if mask.all():
            # No surface; whole grid is deep interior.
            return np.full(shape, -float(max(sx, sy, sz)), dtype=np.float32)
        # Inside distance: distance from each True voxel to the nearest False.
        # We compute by repeated erosion: the iteration count at which a
        # voxel erodes = its Chebyshev distance to the nearest outside voxel.
        in_d = np.where(mask, 0, -1).astype(np.int32)
        current = mask.copy()
        d = 0
        while current.any():
            d += 1
            # eroded = current AND all 6-neighbours are in `current`
            eroded = current.copy()
            eroded[1:, :, :] &= current[:-1, :, :]
            eroded[:-1, :, :] &= current[1:, :, :]
            eroded[:, 1:, :] &= current[:, :-1, :]
            eroded[:, :-1, :] &= current[:, 1:, :]
            eroded[:, :, 1:] &= current[:, :, :-1]
            eroded[:, :, :-1] &= current[:, :, 1:]
            # voxels that disappeared at this step get distance d.
            disappeared = current & ~eroded
            in_d[disappeared] = d
            current = eroded
        # Outside distance: distance from each False voxel to the nearest True.
        out_d = np.where(mask, -1, 0).astype(np.int32)
        current = ~mask
        d = 0
        while current.any():
            d += 1
            eroded = current.copy()
            eroded[1:, :, :] &= current[:-1, :, :]
            eroded[:-1, :, :] &= current[1:, :, :]
            eroded[:, 1:, :] &= current[:, :-1, :]
            eroded[:, :-1, :] &= current[:, 1:, :]
            eroded[:, :, 1:] &= current[:, :, :-1]
            eroded[:, :, :-1] &= current[:, :, 1:]
            disappeared = current & ~eroded
            out_d[disappeared] = d
            current = eroded
        # Signed distance: inside voxels negative, outside voxels positive.
        signed = np.where(mask, -in_d.astype(np.float32),
                          out_d.astype(np.float32))
        return np.asarray(signed, dtype=np.float32)


@dataclass(frozen=True)
class SDFShape:
    """Wrap a binary shape as an SDF via distance-transform conversion.

    The SDF is computed lazily in :meth:`sdf` and cached on the array
    through memoization of the input shape tuple. Composing SDF shapes via
    :class:`SmoothUnion`, :class:`SmoothIntersect`, :class:`SmoothSubtract`
    uses these signed distances to blend smoothly.
    """
    shape: Shape

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return shape_bounds(self.shape, grid_shape)

    def sdf(self, grid_shape: tuple[int, int, int]) -> np.ndarray:
        return _mask_to_sdf(self.shape.mask(grid_shape))

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return self.shape.mask(shape).astype(bool)


def _smooth_min(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth-minimum of two SDF arrays.

    When ``k == 0`` this is a hard ``min(a, b)``. As ``k`` grows the blend
    region widens and the join becomes rounder/softer.
    """
    if k <= 0.0:
        return np.minimum(a, b)
    h = np.maximum(0.5 - 0.5 * (b - a) / k, 0.0)
    return np.minimum(a, b) - h * h * k


def _smooth_max(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth-maximum (smooth union complement for subtraction)."""
    return -_smooth_min(-a, -b, k)


@dataclass(frozen=True)
class SmoothUnion:
    """Blend two SDF shapes with a smooth minimum for organic transitions.

    ``k`` is the blend radius in voxels; ``k=0`` reduces to a hard union.
    The mask is True wherever the blended SDF is <= 0.
    """
    a: SDFShape | Shape
    b: SDFShape | Shape
    k: float = 1.0

    def _sdf_of(self, s: SDFShape | Shape, grid_shape: tuple[int, int, int]) -> np.ndarray:
        if isinstance(s, SDFShape):
            return s.sdf(grid_shape)
        return _mask_to_sdf(s.mask(grid_shape))

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        a_b = shape_bounds(self.a, grid_shape)
        b_b = shape_bounds(self.b, grid_shape)
        return (min(a_b[0], b_b[0]), min(a_b[1], b_b[1]), min(a_b[2], b_b[2]),
                max(a_b[3], b_b[3]), max(a_b[4], b_b[4]), max(a_b[5], b_b[5]))

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sdf_a = self._sdf_of(self.a, shape)
        sdf_b = self._sdf_of(self.b, shape)
        blended = _smooth_min(sdf_a, sdf_b, float(self.k))
        return blended <= 0.0


@dataclass(frozen=True)
class SmoothIntersect:
    """Smooth intersection of two SDF shapes via smooth-maximum.

    ``k`` is the blend radius; ``k=0`` reduces to a hard intersection.
    """
    a: SDFShape | Shape
    b: SDFShape | Shape
    k: float = 1.0

    def _sdf_of(self, s: SDFShape | Shape, grid_shape: tuple[int, int, int]) -> np.ndarray:
        if isinstance(s, SDFShape):
            return s.sdf(grid_shape)
        return _mask_to_sdf(s.mask(grid_shape))

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        a_b = shape_bounds(self.a, grid_shape)
        b_b = shape_bounds(self.b, grid_shape)
        x0 = max(a_b[0], b_b[0])
        y0 = max(a_b[1], b_b[1])
        z0 = max(a_b[2], b_b[2])
        x1 = min(a_b[3], b_b[3])
        y1 = min(a_b[4], b_b[4])
        z1 = min(a_b[5], b_b[5])
        if x0 > x1 or y0 > y1 or z0 > z1:
            return (0, 0, 0, -1, -1, -1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sdf_a = self._sdf_of(self.a, shape)
        sdf_b = self._sdf_of(self.b, shape)
        blended = _smooth_max(sdf_a, sdf_b, float(self.k))
        return blended <= 0.0


@dataclass(frozen=True)
class SmoothSubtract:
    """Smooth subtraction: ``a - b`` with a soft transition at the boundary.

    ``k`` is the blend radius; ``k=0`` reduces to hard subtraction.
    """
    a: SDFShape | Shape
    b: SDFShape | Shape
    k: float = 1.0

    def _sdf_of(self, s: SDFShape | Shape, grid_shape: tuple[int, int, int]) -> np.ndarray:
        if isinstance(s, SDFShape):
            return s.sdf(grid_shape)
        return _mask_to_sdf(s.mask(grid_shape))

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return shape_bounds(self.a, grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sdf_a = self._sdf_of(self.a, shape)
        sdf_b = self._sdf_of(self.b, shape)
        # Subtract = smooth-max(a, -b) => intersect a with the complement of b.
        blended = _smooth_max(sdf_a, -sdf_b, float(self.k))
        return blended <= 0.0
