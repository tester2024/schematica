"""Tests for the review-driven feature additions:
- BezierCurve shape
- arbitrary-angle Rotated transform
- SVG path voxelization via extrude_polygon
- Session.enable_symmetry / disable_symmetry
- Session.resample_subregion
- Cone/Dome/Arch axis-or-plane variants
- Session.add kwargs delegation (the bug-1 fix)
- Cylinder start/end aliases (the bug-2 fix)
"""
from __future__ import annotations

import numpy as np
import pytest

from schematica.session.session import Session
from schematica.shapes.primitives import (
    Arch,
    BezierCurve,
    Box,
    Cone,
    Cylinder,
    Dome,
    Sphere,
)

# ---- Bug #1: Session.add kwargs delegation -------------------------------

def test_add_forwards_hollow_kwarg_to_sphere():
    s = Session.new((16, 16, 16))
    s.add(Sphere(8, 8, 8, 5), "minecraft:stone", hollow=True)
    # Hollow sphere: center voxel should be air.
    assert s.grid.data[8, 8, 8] == 0
    # Shell voxel should be stone.
    assert s.grid.data[8, 8, 8 + 5] != 0


def test_add_forwards_wall_thickness_to_box():
    s = Session.new((16, 16, 16))
    s.add(Box(0, 0, 0, 10, 10, 10), "minecraft:stone",
         hollow=True, wall_thickness=2)
    # 2-voxel wall: voxel at (5,5,5) should be air (interior).
    assert s.grid.data[5, 5, 5] == 0
    # voxel at (1,5,5) should be wall (within 2 of edge).
    assert s.grid.data[1, 5, 5] != 0


def test_add_rejects_unknown_kwarg_with_clear_error():
    s = Session.new((16, 16, 16))
    with pytest.raises(TypeError, match="does not accept"):
        s.add(Sphere(8, 8, 8, 5), "minecraft:stone", bogus=True)


def test_subtract_forwards_hollow_kwarg():
    s = Session.new((16, 16, 16))
    s.fill_all("minecraft:stone")
    s.subtract(Sphere(8, 8, 8, 5), hollow=True)
    # Hollow subtraction: only the shell is carved, the center remains.
    assert s.grid.data[8, 8, 8] != 0  # center still solid
    assert s.grid.data[8, 8, 8 + 5] == 0  # shell carved


# ---- Bug #2: Cylinder start/end aliases ----------------------------------

def test_cylinder_start_end_aliases_override_y0_y1():
    # axis=x with explicit start/end: clearer than y0/y1 meaning X bounds.
    m = Cylinder(8, 8, 3, y0=0, y1=0, start=2, end=6, axis="x").mask((16, 16, 16))
    assert m[2, 8, 8]
    assert m[6, 8, 8]
    assert not m[7, 8, 8]


def test_cylinder_start_only_falls_back_to_y0():
    c = Cylinder(8, 8, 3, y0=4, y1=9, start=2, axis="y")
    # start overrides y0; end stays as y1=9.
    assert c.y0 == 2
    assert c.y1 == 9


# ---- Cone axis support ---------------------------------------------------

def test_cone_axis_x_horizontal():
    m = Cone(8, 8, 5, y_base=2, y_apex=10, axis="x").mask((16, 16, 16))
    # Base at X=2 (full radius), apex at X=10 (zero radius).
    assert m[2, 8, 8]  # base center is solid
    # Apex voxel should be empty (radius shrunk to 0).
    # Just check that something is solid in the middle of the cone.
    assert m.any()


def test_cone_axis_y_still_works():
    m = Cone(8, 8, 5, y_base=2, y_apex=10, axis="y").mask((16, 16, 16))
    assert m.any()
    # Base at y=2 should be wider than apex at y=10.
    base_count = m[:, 2, :].sum()
    apex_count = m[:, 10, :].sum()
    assert base_count >= apex_count


# ---- Dome axis support ---------------------------------------------------

def test_dome_axis_x_keeps_positive_x():
    m = Dome(8, 8, 8, 4, axis="x").mask((16, 16, 16))
    # +X hemisphere: x >= cx
    coords = np.nonzero(m)
    assert (coords[0] >= 8).all()
    # The center should be on the boundary (included).
    assert m[8, 8, 8]


def test_dome_axis_y_upper_hemisphere_still_works():
    m = Dome(8, 8, 8, 4, axis="y").mask((16, 16, 16))
    coords = np.nonzero(m)
    assert (coords[1] >= 8).all()


# ---- Arch plane support --------------------------------------------------

def test_arch_plane_xz_extrudes_along_y():
    # plane="xz": ring in (X, Z) centered at (cx, cy=5), extrude along Y [0..8].
    m = Arch(8, 5, 0, 8, r=4, plane="xz").mask((16, 16, 16))
    assert m.any()
    # The arch should exist at Y=0 and Y=8 (the extrusion bounds).
    assert m[:, 0, :].any()
    assert m[:, 8, :].any()


def test_arch_plane_xy_legacy_default():
    # Default plane="xy" must match the legacy behaviour exactly.
    m1 = Arch(8, 5, 0, 8, r=4).mask((16, 16, 16))
    m2 = Arch(8, 5, 0, 8, r=4, plane="xy").mask((16, 16, 16))
    assert np.array_equal(m1, m2)


# ---- BezierCurve ---------------------------------------------------------

def test_bezier_quadratic_produces_voxels():
    curve = BezierCurve((0, 0, 0), (8, 15, 8), (15, 0, 15), thickness=1.0)
    m = curve.mask((16, 16, 16))
    assert m.sum() > 30
    # The curve should pass near the start and end control points.
    assert m[0, 0, 0]
    assert m[15, 0, 15]


def test_bezier_cubic_produces_voxels():
    curve = BezierCurve((0, 0, 0), (0, 15, 15), (15, 15, 15), (15, 0, 0),
                        thickness=1.5, samples=200)
    m = curve.mask((16, 16, 16))
    assert m.sum() > 40
    assert m[0, 0, 0]
    assert m[15, 0, 0]


def test_bezier_zero_thickness_still_single_voxel():
    curve = BezierCurve((0, 0, 0), (8, 8, 8), (15, 0, 0), thickness=0.0)
    m = curve.mask((16, 16, 16))
    assert m.any()


# ---- Rotated (arbitrary angle) -------------------------------------------

def test_rotated_0_degrees_matches_original():
    from schematica.shapes.transforms import Rotated
    box = Box(2, 2, 2, 8, 8, 8)
    rot = Rotated(box, angle_deg=0.0, axes="xy")
    assert np.array_equal(rot.mask((16, 16, 16)), box.mask((16, 16, 16)))


def test_rotated_360_matches_original():
    from schematica.shapes.transforms import Rotated
    box = Box(2, 2, 2, 8, 8, 8)
    rot = Rotated(box, angle_deg=360.0, axes="xy")
    assert np.array_equal(rot.mask((16, 16, 16)), box.mask((16, 16, 16)))


def test_rotated_45_degrees_preserves_volume_roughly():
    from schematica.shapes.transforms import Rotated
    box = Box(0, 0, 0, 9, 9, 9)
    base = box.mask((16, 16, 16)).sum()
    rot = Rotated(box, angle_deg=45.0, axes="xy").mask((16, 16, 16))
    # 45-degree rotation of a square should produce a diamond of similar area;
    # the nearest-neighbour resampling will lose some voxels but not too many.
    assert rot.sum() >= base * 0.6


# ---- SVG path voxelization -----------------------------------------------

def test_extrude_svg_path_simple_square():
    from schematica.shapes.polygon import extrude_polygon
    # A 10x10 square: M 0 0 H 10 V 10 H 0 Z
    shape = extrude_polygon("M 0 0 H 10 V 10 H 0 Z", origin=(0, 0, 0),
                            extrude_axis="z", length=4)
    m = shape.mask((16, 16, 16))
    assert m.any()
    # The extrusion should span z=0..3.
    assert m[:, :, 0].any()
    assert m[:, :, 3].any()
    assert not m[:, :, 4].any()


def test_extrude_svg_path_with_quadratic_curve():
    from schematica.shapes.polygon import extrude_polygon
    # A path with a Q curve — should still produce a closed polygon.
    shape = extrude_polygon("M 0 0 Q 5 10 10 0 Z", origin=(0, 0, 0),
                            extrude_axis="z", length=3)
    m = shape.mask((16, 16, 16))
    assert m.any()


# ---- Active symmetry -----------------------------------------------------

def test_enable_symmetry_mirrors_subsequent_adds():
    s = Session.new((16, 16, 16))
    s.enable_symmetry(axis="x")  # mirror about the grid middle (x=7.5)
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    # The mirror about x=7.5 maps x=0..3 to x=12..15.
    assert s.grid.data[1, 1, 1] != 0       # original
    assert s.grid.data[14, 1, 1] != 0      # mirror image
    s.disable_symmetry()
    assert not s.symmetry_active
    s.add(Box(5, 5, 5, 6, 6, 6), "minecraft:stone")
    # After disabling, only the explicit box is added.
    assert s.grid.data[5, 5, 5] != 0
    # The mirror of (5,5,5) about x=7.5 is (10,5,5); should NOT be added now.
    assert s.grid.data[10, 5, 5] == 0


def test_enable_symmetry_with_explicit_center():
    s = Session.new((16, 16, 16))
    s.enable_symmetry(axis=0, center=8.0)
    s.add(Box(0, 0, 0, 2, 2, 2), "minecraft:stone")
    # Mirror of x=0..2 about x=8 is x=14..16 -> clipped to x=14..15.
    assert s.grid.data[1, 1, 1] != 0
    assert s.grid.data[15, 1, 1] != 0


# ---- resample_subregion --------------------------------------------------

def test_resample_subregion_upscales_box():
    s = Session.new((16, 16, 16))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")  # 4x4x4 source cube
    # Upscale it into the (8..15, 8..15, 8..15) corner at 8x8x8.
    n = s.resample_subregion((0, 0, 0), (3, 3, 3), new_size=(8, 8, 8),
                              block="minecraft:cobblestone",
                              dest_origin=(8, 8, 8))
    assert n > 0
    # The upscaled region should fill the [8..15]^3 box.
    assert s.grid.data[8, 8, 8] != 0
    assert s.grid.data[15, 15, 15] != 0


def test_resample_subregion_downscales_box():
    s = Session.new((16, 16, 16))
    s.add(Box(0, 0, 0, 9, 9, 9), "minecraft:stone")  # 10x10x10 source cube
    # Downscale into a 4x4x4 region at (12, 12, 12).
    n = s.resample_subregion((0, 0, 0), (9, 9, 9), new_size=(4, 4, 4),
                              block="minecraft:cobblestone",
                              dest_origin=(12, 12, 12))
    assert n > 0
    assert s.grid.data[12, 12, 12] != 0
    assert s.grid.data[15, 15, 15] != 0
