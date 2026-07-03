"""Tests for the full CLI command surface (all shapes registered)."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.commands import COMMANDS
from schematica.session.session import Session


def test_all_add_shapes_exist():
    expected = {
        "add.box", "add.sphere", "add.cylinder", "add.dome", "add.helix",
        "add.arch", "add.staircase", "add.cone", "add.ellipsoid",
        "add.pyramid", "add.torus", "add.line", "add.wedge",
        "add.spiral", "add.plane",
    }
    assert expected <= set(COMMANDS)


def test_all_subtract_shapes_exist():
    expected = {
        "subtract.box", "subtract.sphere", "subtract.cylinder",
        "subtract.dome", "subtract.pyramid",
    }
    assert expected <= set(COMMANDS)


def test_all_paint_shapes_exist():
    expected = {"paint.box", "paint.sphere"}
    assert expected <= set(COMMANDS)


def test_add_cone():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.cone center=16,0,16 r_base=5 y_base=1 y_apex=10 block=minecraft:stone")
    assert "cone" in res and s.grid.nonempty_count() > 0


def test_add_ellipsoid():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.ellipsoid center=16,16,16 rx=5 ry=3 rz=5 block=minecraft:glass")
    assert "ellipsoid" in res and s.grid.nonempty_count() > 0


def test_add_pyramid():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.pyramid center=16,0,16 base_half=4 y_base=1 y_apex=8 block=minecraft:bricks")
    assert "pyramid" in res and s.grid.nonempty_count() > 0


def test_add_torus():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.torus center=16,16,16 R=5 r=2 block=minecraft:obsidian")
    assert "torus" in res and s.grid.nonempty_count() > 0


def test_add_line():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.line frm=0,0,0 to=31,31,31 block=minecraft:glowstone")
    assert "line" in res and s.grid.nonempty_count() > 0


def test_add_wedge():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.wedge frm=0,0,0 to=8,8,8 split_axis=x block=minecraft:sand")
    assert "wedge" in res and s.grid.nonempty_count() > 0


def test_add_spiral():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.spiral center=16,16,16 r_inner=2 r_outer=8 y0=1 y1=3 block=minecraft:quartz_block")
    assert "spiral" in res and s.grid.nonempty_count() > 0


def test_add_plane():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.plane axis=y coord=15 block=minecraft:bedrock")
    assert "plane" in res and s.grid.nonempty_count() > 0


def test_subtract_dome():
    s = Session.new((32, 32, 32))
    dispatch(s, "add.box frm=0,0,0 to=31,31,31 block=minecraft:stone")
    before = s.grid.nonempty_count()
    res = dispatch(s, "subtract.dome center=16,16,16 r=5")
    assert "subtracted dome" in res and s.grid.nonempty_count() < before


def test_subtract_pyramid():
    s = Session.new((32, 32, 32))
    dispatch(s, "add.box frm=0,0,0 to=31,31,31 block=minecraft:stone")
    before = s.grid.nonempty_count()
    res = dispatch(s, "subtract.pyramid center=16,0,16 base_half=3 y_base=1 y_apex=6")
    assert "subtracted pyramid" in res and s.grid.nonempty_count() < before


def test_paint_sphere():
    s = Session.new((32, 32, 32))
    dispatch(s, "add.box frm=0,0,0 to=15,15,15 block=minecraft:stone")
    res = dispatch(s, "paint.sphere center=8,8,8 r=5 block=minecraft:dirt")
    assert "painted sphere" in res
    assert s.grid.count("minecraft:dirt") > 0


def test_cone_inverted_y_error():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.cone center=16,0,16 r_base=5 y_base=10 y_apex=3 block=minecraft:stone")
    assert "error" in res and "inverted_bounds" in res


def test_torus_negative_R_error():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.torus center=16,16,16 R=-1 r=2 block=minecraft:stone")
    assert "error" in res and "negative_radius" in res


def test_wedge_bad_split_axis_error():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.wedge frm=0,0,0 to=8,8,8 split_axis=y block=minecraft:stone")
    assert "error" in res and "bad_axis" in res


def test_plane_bad_axis_error():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.plane axis=q coord=5 block=minecraft:stone")
    assert "error" in res and "bad_axis" in res


def test_ellipsoid_zero_rx_error():
    s = Session.new((32, 32, 32))
    res = dispatch(s, "add.ellipsoid center=16,16,16 rx=0 ry=3 rz=5 block=minecraft:glass")
    assert "error" in res and "negative_radius" in res