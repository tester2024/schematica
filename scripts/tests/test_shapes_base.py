"""Unit tests for schematica.shapes.base geometry helpers.

Covers: in_bounds, coords_grid, coords_grid_offset, bounds_default,
intersect_bbox, mask_region, shape_bounds, and the Shape protocol.
"""
from __future__ import annotations

import numpy as np

from schematica.shapes.base import (
    Shape,
    bounds_default,
    coords_grid,
    coords_grid_offset,
    in_bounds,
    intersect_bbox,
    mask_region,
    shape_bounds,
)
from schematica.shapes.primitives import Box

# ---- in_bounds ------------------------------------------------------------

def test_in_bounds_inside():
    assert in_bounds((0, 0, 0), (4, 4, 4)) is True
    assert in_bounds((3, 3, 3), (4, 4, 4)) is True


def test_in_bounds_outside_high():
    assert in_bounds((4, 0, 0), (4, 4, 4)) is False
    assert in_bounds((0, 4, 0), (4, 4, 4)) is False
    assert in_bounds((0, 0, 4), (4, 4, 4)) is False


def test_in_bounds_outside_negative():
    assert in_bounds((-1, 0, 0), (4, 4, 4)) is False
    assert in_bounds((0, -1, 0), (4, 4, 4)) is False


# ---- coords_grid ----------------------------------------------------------

def test_coords_grid_shape_and_values():
    X, Y, Z = coords_grid((2, 3, 4))
    assert X.shape == (2, 3, 4)
    assert Y.shape == (2, 3, 4)
    assert Z.shape == (2, 3, 4)
    # X varies along axis 0 only.
    assert (X[:, 0, 0] == np.arange(2, dtype=np.int32)).all()
    assert (Y[0, :, 0] == np.arange(3, dtype=np.int32)).all()
    assert (Z[0, 0, :] == np.arange(4, dtype=np.int32)).all()


def test_coords_grid_dtype():
    X, _, _ = coords_grid((2, 2, 2))
    assert X.dtype == np.int32


# ---- coords_grid_offset ---------------------------------------------------

def test_coords_grid_offset_shifts_values():
    X, Y, Z = coords_grid_offset((2, 2, 2), origin=(10, 20, 30))
    assert X.shape == (2, 2, 2)
    assert X[0, 0, 0] == 10
    assert X[1, 0, 0] == 11
    assert Y[0, 0, 0] == 20
    assert Y[0, 1, 0] == 21
    assert Z[0, 0, 0] == 30
    assert Z[0, 0, 1] == 31


def test_coords_grid_offset_zero_origin_matches_coords_grid():
    X1, Y1, Z1 = coords_grid((3, 3, 3))
    X2, Y2, Z2 = coords_grid_offset((3, 3, 3), origin=(0, 0, 0))
    assert np.array_equal(X1, X2)
    assert np.array_equal(Y1, Y2)
    assert np.array_equal(Z1, Z2)


# ---- bounds_default -------------------------------------------------------

def test_bounds_default_full_grid():
    assert bounds_default((4, 5, 6)) == (0, 0, 0, 3, 4, 5)


def test_bounds_default_single_voxel():
    assert bounds_default((1, 1, 1)) == (0, 0, 0, 0, 0, 0)


# ---- intersect_bbox -------------------------------------------------------

def test_intersect_bbox_overlap():
    a = (0, 0, 0, 4, 4, 4)
    b = (2, 2, 2, 6, 6, 6)
    assert intersect_bbox(a, b) == (2, 2, 2, 4, 4, 4)


def test_intersect_bbox_contained():
    a = (0, 0, 0, 10, 10, 10)
    b = (2, 2, 2, 4, 4, 4)
    assert intersect_bbox(a, b) == (2, 2, 2, 4, 4, 4)


def test_intersect_bbox_disjoint_x():
    a = (0, 0, 0, 2, 2, 2)
    b = (5, 0, 0, 7, 2, 2)
    assert intersect_bbox(a, b) is None


def test_intersect_bbox_disjoint_y():
    a = (0, 0, 0, 2, 2, 2)
    b = (0, 5, 0, 2, 7, 2)
    assert intersect_bbox(a, b) is None


def test_intersect_bbox_disjoint_z():
    a = (0, 0, 0, 2, 2, 2)
    b = (0, 0, 5, 2, 2, 7)
    assert intersect_bbox(a, b) is None


def test_intersect_bbox_touching_edge():
    # Touching on the boundary (x0 == x1) is still a valid intersection.
    a = (0, 0, 0, 2, 2, 2)
    b = (2, 0, 0, 4, 2, 2)
    assert intersect_bbox(a, b) == (2, 0, 0, 2, 2, 2)


# ---- mask_region ----------------------------------------------------------

def test_mask_region_slices_full_mask():
    box = Box(2, 2, 2, 5, 5, 5)
    sub = mask_region(box, (8, 8, 8), origin=(1, 1, 1), size=(4, 4, 4))
    assert sub.shape == (4, 4, 4)
    assert sub.dtype == bool
    # Box starts at 2,2,2. In the sub-grid starting at world 1,1,1, the box
    # begins at local index 1. So (0,0,0) is outside, (1,1,1) is inside.
    assert sub[0, 0, 0] is False or sub[0, 0, 0] == np.False_
    assert sub[1, 1, 1] == True  # noqa: E712


def test_mask_region_copies_result():
    box = Box(0, 0, 0, 3, 3, 3)
    sub = mask_region(box, (4, 4, 4), origin=(0, 0, 0), size=(2, 2, 2))
    # Mutating sub must not affect the underlying full mask.
    sub[0, 0, 0] = False
    full = box.mask((4, 4, 4))
    assert full[0, 0, 0] == True  # noqa: E712


def test_mask_region_delegates_to_shape_method():
    class _RegionShape:
        def mask(self, shape):
            return np.ones(shape, dtype=bool)

        def mask_region(self, grid_shape, origin, size):
            return np.zeros(size, dtype=bool)

    rs = _RegionShape()
    out = mask_region(rs, (8, 8, 8), origin=(0, 0, 0), size=(2, 2, 2))
    assert out.shape == (2, 2, 2)
    # The override returns all-False even though mask() is all-True.
    assert not out.any()


# ---- shape_bounds ---------------------------------------------------------

def test_shape_bounds_uses_shape_bounds_method():
    box = Box(1, 2, 3, 4, 5, 6)
    b = shape_bounds(box, (16, 16, 16))
    assert b == (1, 2, 3, 4, 5, 6)


def test_shape_bounds_falls_back_to_default():
    class _NoBounds:
        def mask(self, shape):
            return np.zeros(shape, dtype=bool)

    b = shape_bounds(_NoBounds(), (4, 5, 6))
    assert b == (0, 0, 0, 3, 4, 5)


# ---- Shape protocol -------------------------------------------------------

def test_shape_protocol_runtime_checkable():
    class _Dummy:
        def mask(self, shape):
            return np.zeros(shape, dtype=bool)

    assert isinstance(_Dummy(), Shape)


def test_shape_protocol_rejects_non_mask_object():
    class _NoMask:
        pass

    assert not isinstance(_NoMask(), Shape)
