"""Tests for CLI dispatch."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def test_dispatch_add_box():
    s = Session.new((8, 8, 8))
    res = dispatch(s, "add.box frm=0,0,0 to=2,2,2 block=minecraft:stone")
    assert "box" in res
    assert s.grid.nonempty_count() == 27


def test_dispatch_stats():
    s = Session.new((4, 4, 4))
    res = dispatch(s, "stats")
    assert "shape=" in res
    assert "vol=64" in res


def test_dispatch_undo_redo():
    s = Session.new((8, 8, 8))
    dispatch(s, "add.box frm=0,0,0 to=1,1,1 block=minecraft:stone")
    assert s.grid.nonempty_count() == 8
    dispatch(s, "undo")
    assert s.grid.nonempty_count() == 0
    dispatch(s, "redo")
    assert s.grid.nonempty_count() == 8


def test_dispatch_replace():
    s = Session.new((4, 4, 4))
    dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    res = dispatch(s, "replace src=minecraft:stone dst=minecraft:dirt")
    assert "replaced" in res
    assert s.grid.count("minecraft:dirt") == 64


def test_dispatch_unknown():
    s = Session.new((4, 4, 4))
    res = dispatch(s, "nonexistent.command")
    assert "unknown" in res


def test_dispatch_clear():
    s = Session.new((4, 4, 4))
    dispatch(s, "add.box frm=0,0,0 to=1,1,1 block=minecraft:stone")
    dispatch(s, "clear")
    assert s.grid.nonempty_count() == 0
