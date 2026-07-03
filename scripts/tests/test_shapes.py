"""Tests for shape masks."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.shapes.primitives import (
    Box, Sphere, Cylinder, Cone, Pyramid, Torus, Line, Wedge,
)


def test_box_fill_exact():
    m = Box(0, 0, 0, 2, 2, 2).mask((4, 4, 4))
    assert m.sum() == 27  # 3x3x3
    assert m[0, 0, 0] and m[2, 2, 2]
    assert not m[3, 3, 3]


def test_box_hollow():
    m = Box(0, 0, 0, 4, 4, 4, hollow=True, wall_thickness=1).mask((6, 6, 6))
    # 5x5x5 outer = 125, inner 3x3x3 = 27 -> shell = 98
    assert m.sum() == 125 - 27
    assert not m[1, 1, 1]  # interior
    assert m[0, 0, 0]


def test_sphere_radius():
    m = Sphere(4, 4, 4, 2).mask((10, 10, 10))
    # analytic: voxel within r=2 of center
    expected = 0
    for x in range(10):
        for y in range(10):
            for z in range(10):
                if (x - 4) ** 2 + (y - 4) ** 2 + (z - 4) ** 2 <= 4:
                    expected += 1
    assert m.sum() == expected


def test_cylinder_vertical():
    m = Cylinder(2, 2, 2.0, 0, 3).mask((5, 5, 5))
    assert m.shape == (5, 5, 5)
    assert m[2, 0, 2]
    assert m[2, 3, 2]
    assert not m[2, 4, 2]  # outside y range


def test_cone_apex():
    m = Cone(2, 2, 3.0, 0, 4).mask((5, 5, 5))
    assert m[2, 0, 2]  # base filled
    assert m[2, 4, 2]  # apex single voxel


def test_pyramid():
    m = Pyramid(2, 2, 2, 0, 4).mask((5, 5, 5))
    assert m[2, 0, 2]
    assert m[2, 4, 2]


def test_line_bresenham():
    m = Line(0, 0, 0, 3, 3, 3).mask((4, 4, 4))
    assert m.sum() == 4
    assert m[0, 0, 0] and m[3, 3, 3]


def test_wedge():
    m = Wedge(0, 0, 0, 3, 3, 3, split_axis="x").mask((4, 4, 4))
    assert m[0, 0, 0]  # base corner filled
    assert m[3, 0, 0]  # apex (only y=0 at x=3)
    assert not m[3, 3, 0]  # above diagonal at x=3


def test_torus_donut():
    m = Torus(4, 4, 4, R=3, r=1).mask((9, 9, 9))
    assert m.sum() > 0
    assert not m[4, 4, 4]  # hole in middle