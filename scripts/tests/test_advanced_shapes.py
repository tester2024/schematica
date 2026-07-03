"""Tests for advanced shapes (Dome, Helix, Arch, Spiral, Staircase)."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.shapes.primitives import Dome, Helix, Arch, Spiral, Staircase


def test_dome_upper_half_only():
    m = Dome(4, 4, 4, 3).mask((10, 10, 10))
    assert m[4, 4, 4]   # center is on the boundary
    assert m[4, 6, 4]   # above center
    assert not m[4, 2, 4]  # below center: excluded


def test_dome_hollow():
    m = Dome(5, 5, 5, 4, hollow=True).mask((12, 12, 12))
    # Top of dome at y=5+4=9: should be shell
    assert m[5, 9, 5]
    # Interior near center: should be hollow (air)
    assert not m[5, 6, 5]


def test_helix_produces_voxels():
    m = Helix(8, 0, 8, 4, 0, 10, turns=2.0).mask((16, 16, 16))
    assert m.sum() > 20  # should have a decent number of voxels
    assert m.any()  # at least something


def test_helix_zero_height_empty():
    m = Helix(8, 0, 8, 4, 5, 5).mask((16, 16, 16))
    assert m.sum() == 0


def test_arch_semiring():
    m = Arch(5, 0, 2, 8, r=4, thickness=1.5).mask((12, 12, 12))
    assert m.any()
    # arch is only in y >= cy (=0), so all voxels should have y >= 0
    coords = np.nonzero(m)
    assert coords[1].min() >= 0


def test_arch_inverted_z_empty():
    m = Arch(5, 0, 8, 2, r=4).mask((12, 12, 12))
    # z0=8 > z1=2: the z range is empty
    assert m.sum() == 0


def test_spiral_produces_voxels():
    m = Spiral(8, 8, 0, 3, r_inner=1, r_outer=5, turns=2.0).mask((16, 16, 16))
    assert m.sum() > 10


def test_staircase_x_axis():
    m = Staircase(0, 0, 0, 8, step_width=3, step_depth=2, step_height=1, axis="x").mask((16, 16, 16))
    assert m[0, 0, 0]   # first step at origin
    assert m[2, 1, 0]   # second step: x=2, y=1, z=0..2
    assert m[4, 2, 0]   # third step: x=4, y=2


def test_staircase_z_axis():
    m = Staircase(0, 0, 0, 6, step_width=3, step_depth=2, step_height=2, axis="z").mask((16, 16, 16))
    assert m[0, 0, 0]   # first step
    assert m[0, 2, 2]   # second step at y=2, z=2


def test_staircase_zero_rise_empty():
    m = Staircase(0, 5, 0, 5).mask((16, 16, 16))
    assert m.sum() == 0