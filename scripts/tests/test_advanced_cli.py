"""Tests for new CLI commands (dome, helix, arch, staircase, subtract sphere/cyl, paint)."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def test_add_dome():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.dome center=8,0,8 r=5 block=minecraft:glass")
    assert "dome" in res
    assert s.grid.nonempty_count() > 0


def test_add_helix():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.helix center=8,8,8 r=4 y0=0 y1=10 turns=2 block=minecraft:oak_log")
    assert "helix" in res
    assert s.grid.nonempty_count() > 0


def test_add_arch():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.arch center=5,0,5 z0=2 z1=8 r=4 block=minecraft:stone")
    assert "arch" in res
    assert s.grid.nonempty_count() > 0


def test_add_staircase():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.staircase corner=0,0,0 y1=8 block=minecraft:oak_planks")
    assert "staircase" in res
    assert s.grid.nonempty_count() > 0


def test_subtract_sphere():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.box frm=0,0,0 to=15,15,15 block=minecraft:stone")
    before = s.grid.nonempty_count()
    res = dispatch(s, "subtract.sphere center=8,8,8 r=5")
    assert "subtracted sphere" in res
    assert s.grid.nonempty_count() < before


def test_subtract_cylinder():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.box frm=0,0,0 to=15,15,15 block=minecraft:stone")
    before = s.grid.nonempty_count()
    res = dispatch(s, "subtract.cylinder center=8,0,8 r=3 h=10")
    assert "subtracted cylinder" in res
    assert s.grid.nonempty_count() < before


def test_paint_box():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.box frm=0,0,0 to=10,10,10 block=minecraft:stone")
    res = dispatch(s, "paint.box frm=0,0,0 to=10,10,10 block=minecraft:dirt")
    assert "painted" in res
    assert s.grid.count("minecraft:dirt") > 0


def test_helix_inverted_y_error():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.helix center=8,8,8 r=4 y0=10 y1=0 block=minecraft:stone")
    assert "error" in res and "inverted_bounds" in res


def test_staircase_bad_axis_error():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.staircase corner=0,0,0 y1=8 axis=q block=minecraft:stone")
    assert "error" in res and "bad_axis" in res


def test_arch_negative_radius_error():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.arch center=5,0,5 z0=2 z1=8 r=-3 block=minecraft:stone")
    assert "error" in res and "negative_radius" in res
