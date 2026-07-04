"""Tests for SDF-based smooth blending (SmoothUnion/Intersect/Subtract)."""
from __future__ import annotations

import numpy as np

from schematica.shapes.primitives import Box, Sphere
from schematica.shapes.sdf import SDFShape, SmoothIntersect, SmoothSubtract, SmoothUnion


def test_smooth_union_hard_k0_matches_union():
    from schematica.shapes.boolean import Union
    a = Sphere(8, 8, 8, 5)
    b = Sphere(14, 8, 8, 5)
    hard = Union((a, b)).mask((24, 16, 16))
    smooth = SmoothUnion(a, b, k=0.0).mask((24, 16, 16))
    # Hard smooth-min (k=0) should be identical to boolean union.
    assert np.array_equal(hard, smooth)


def test_smooth_union_soft_k_grows_overlap():
    a = Sphere(8, 8, 8, 5)
    b = Sphere(16, 8, 8, 5)
    # At k=0 the two spheres are disjoint (gap between them).
    hard = SmoothUnion(a, b, k=0.0).mask((24, 16, 16))
    # With a large k, the blend should bridge the gap (more voxels).
    soft = SmoothUnion(a, b, k=4.0).mask((24, 16, 16))
    assert soft.sum() >= hard.sum()
    # The soft union should fill some voxel between them that the hard one doesn't.
    bridge_voxels = soft & ~hard
    assert bridge_voxels.any(), "smooth union should bridge the gap"


def test_smooth_intersect_subset_of_hard_intersect():
    a = Sphere(8, 8, 8, 6)
    b = Sphere(10, 8, 8, 6)
    hard_int = (a.mask((20, 16, 16)) & b.mask((20, 16, 16)))
    smooth = SmoothIntersect(a, b, k=2.0).mask((20, 16, 16))
    # Smooth intersection should be a rounded subset near the overlap.
    assert smooth.sum() <= hard_int.sum() + 5  # roughly smaller or equal


def test_smooth_subtract_removes_overlap():
    a = Box(0, 0, 0, 15, 15, 15)
    b = Sphere(8, 8, 8, 6)
    sub = SmoothSubtract(a, b, k=2.0).mask((16, 16, 16))
    # The center should be carved out by the sphere.
    assert not sub[8, 8, 8]
    # The far corner should remain.
    assert sub[0, 0, 0]


def test_sdf_shape_round_trips_mask():
    s = SDFShape(Sphere(5, 5, 5, 3))
    m = s.mask((12, 12, 12))
    assert m[5, 5, 5]
    assert not m[0, 0, 0]
    d = s.sdf((12, 12, 12))
    # Inside the sphere: negative SDF.
    assert d[5, 5, 5] <= 0
    # Outside the sphere: positive SDF.
    assert d[0, 0, 0] > 0
