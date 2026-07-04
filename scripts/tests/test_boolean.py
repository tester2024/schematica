"""Tests for boolean shape ops."""
from __future__ import annotations

from schematica.shapes.boolean import Intersect, Subtract, Union, Xor
from schematica.shapes.primitives import Box


def test_union_overlap():
    a = Box(0, 0, 0, 2, 2, 2)
    b = Box(1, 1, 1, 3, 3, 3)
    u = Union((a, b)).mask((5, 5, 5))
    assert u[0, 0, 0] and u[3, 3, 3] and u[1, 1, 1]


def test_intersect():
    a = Box(0, 0, 0, 3, 3, 3)
    b = Box(2, 2, 2, 5, 5, 5)
    m = Intersect((a, b)).mask((6, 6, 6))
    assert m[2, 2, 2] and m[3, 3, 3]
    assert not m[0, 0, 0]


def test_subtract():
    a = Box(0, 0, 0, 3, 3, 3)
    b = Box(1, 1, 1, 2, 2, 2)
    m = Subtract(a, b).mask((4, 4, 4))
    assert m[0, 0, 0]
    assert not m[1, 1, 1]


def test_xor():
    a = Box(0, 0, 0, 1, 1, 1)
    b = Box(1, 1, 1, 2, 2, 2)
    m = Xor(a, b).mask((3, 3, 3))
    assert m[0, 0, 0] and m[2, 2, 2]
    assert not m[1, 1, 1]
