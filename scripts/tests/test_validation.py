"""Tests for CLI validation layer (errors + warnings)."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def _new(size=(8, 8, 8)) -> Session:
    return Session.new(size)


def test_inverted_bounds_error():
    s = _new()
    res = dispatch(s, "add.box frm=3,3,3 to=2,2,2 block=minecraft:stone")
    assert "error" in res and "inverted_bounds" in res
    assert s.grid.nonempty_count() == 0  # refused


def test_negative_radius_error():
    s = _new()
    res = dispatch(s, "add.sphere center=4,4,4 r=-2 block=minecraft:stone")
    assert "error" in res and "negative_radius" in res


def test_zero_radius_warns_but_runs():
    s = _new()
    res = dispatch(s, "add.sphere center=4,4,4 r=0 block=minecraft:stone")
    assert "sphere @ 4,4,4 r=0.0" in res
    assert "! [zero_radius]" in res


def test_nonpositive_height_error():
    s = _new()
    res = dispatch(s, "add.cylinder center=4,4,4 r=2 h=0 block=minecraft:stone")
    assert "error" in res and "nonpositive_height" in res
    res = dispatch(s, "add.cylinder center=4,4,4 r=2 h=-3 block=minecraft:stone")
    assert "error" in res and "nonpositive_height" in res


def test_bad_axis_error():
    s = _new()
    res = dispatch(s, "mirror axis=q")
    assert "error" in res and "bad_axis" in res


def test_bad_axes_error():
    s = _new()
    res = dispatch(s, "rotate times=1 axes=qq")
    assert "error" in res and "bad_axes" in res
    res = dispatch(s, "rotate times=1 axes=XY")
    assert "error" in res and "bad_axes" in res


def test_empty_export_path_error():
    s = _new()
    res = dispatch(s, "export path=")
    assert "error" in res and "empty_path" in res


def test_bad_extension_warns():
    s = _new()
    res = dispatch(s, "export path=foo")
    assert "exported foo" in res
    assert "! [bad_extension]" in res


def test_fill_air_warns():
    s = _new()
    res = dispatch(s, "fill block=minecraft:air")
    assert "filled minecraft:air" in res
    assert "! [fill_air]" in res


def test_add_air_warns():
    s = _new()
    res = dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:air")
    assert "minecraft:air" in res
    assert "! [add_air]" in res


def test_replace_same_warns():
    s = _new()
    dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    res = dispatch(s, "replace src=minecraft:stone dst=minecraft:stone")
    assert "! [replace_same]" in res


def test_bad_state_value_error():
    s = _new()
    res = dispatch(s, "add.box frm=0,0,0 to=1,1,1 block=oak_log[axis=q]")
    assert "error" in res and "bad_state_value" in res


def test_unknown_block_error():
    s = _new()
    res = dispatch(s, "add.box frm=0,0,0 to=1,1,1 block=minecraft:nonexistent")
    assert "error" in res and "unknown_block" in res


def test_out_of_bounds_warns():
    s = _new()
    res = dispatch(s, "add.box frm=-2,-2,-2 to=10,10,10 block=minecraft:stone")
    assert "! [partly_out_of_bounds]" in res


def test_nonpositive_size_error():
    s = _new()
    res = dispatch(s, "session.new size=0x0x0")
    assert "error" in res and "nonpositive_size" in res


def test_bad_size_error():
    s = _new()
    res = dispatch(s, "session.new size=16")
    assert "error" in res and "bad_size" in res


def test_valid_command_no_warnings():
    s = _new()
    res = dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    assert "!" not in res
    assert "error" not in res


def test_backslash_path_warns():
    s = _new()
    # Backslash detection happens pre-parse on the raw line.
    res = dispatch(s, "export path=foo\\bar.schem")
    assert "! [backslash_path]" in res


def test_warning_lines_use_bang_prefix():
    s = _new()
    res = dispatch(s, "add.sphere center=4,4,4 r=0 block=minecraft:stone")
    lines = res.split("\n")
    assert any(ln.startswith("! [") for ln in lines)