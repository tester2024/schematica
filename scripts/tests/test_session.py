"""Tests for Session + history."""
from __future__ import annotations

from schematica.session.session import Session
from schematica.shapes.primitives import Box


def test_session_new_air():
    s = Session.new((4, 4, 4))
    assert s.grid.nonempty_count() == 0
    assert s.version == "1.20.1"


def test_session_add_box():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 2, 2, 2), "minecraft:stone")
    assert s.grid.nonempty_count() == 27


def test_session_subtract():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    s.subtract(Box(1, 1, 1, 2, 2, 2))
    assert s.grid.nonempty_count() == 64 - 8


def test_session_undo_redo():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 1, 1, 1), "minecraft:stone")
    assert s.grid.nonempty_count() == 8
    assert s.undo()
    assert s.grid.nonempty_count() == 0
    assert not s.undo()
    assert s.redo()
    assert s.grid.nonempty_count() == 8
    assert not s.redo()


def test_session_replace():
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    n = s.replace("minecraft:stone", "minecraft:dirt")
    assert n == 64
    assert s.grid.count("minecraft:dirt") == 64


def test_session_save_load_roundtrip(tmp_path):
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 1, 1, 1), "minecraft:stone")
    p = tmp_path / "sess.json"
    s.save(p)
    s2 = Session.load(p)
    assert s2.grid.shape == (4, 4, 4)
    assert s2.grid.nonempty_count() == 8
    assert s2.grid == s.grid


def test_session_paint_only_solid():
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 1, 1, 1), "minecraft:stone")
    # paint only affects existing solid voxels
    s.paint(Box(0, 0, 0, 3, 3, 3), "minecraft:dirt")
    assert s.grid.count("minecraft:dirt") == 8
    assert s.grid.count("minecraft:stone") == 0


def test_session_clone_translate_undo_redo():
    s = Session.new((8, 4, 4))
    s.add(Box(0, 0, 0, 0, 0, 0), "minecraft:stone")
    n = s.clone_translate((0, 0, 0), (0, 0, 0), (2, 0, 0), count=2)
    assert n == 2
    assert s.grid.get(2, 0, 0).name == "minecraft:stone"
    assert s.grid.get(4, 0, 0).name == "minecraft:stone"
    assert s.undo()
    assert s.grid.get(2, 0, 0).name == "minecraft:air"
    assert s.redo()
    assert s.grid.get(4, 0, 0).name == "minecraft:stone"


def test_session_clone_cardinal():
    s = Session.new((9, 2, 9))
    s.add(Box(6, 0, 4, 6, 0, 4), "minecraft:stone")
    n = s.clone_cardinal((6, 0, 4), (6, 0, 4), (4, 4))
    assert n == 3
    for pos in ((4, 0, 6), (2, 0, 4), (4, 0, 2)):
        assert s.grid.get(*pos).name == "minecraft:stone"


def test_session_set_box_records_single_delta():
    s = Session.new((8, 8, 8))
    n = s.set_box((1, 1, 1), (3, 3, 3), "minecraft:stone")
    assert n == 27
    assert s.grid.nonempty_count() == 27
    assert s.undo()
    assert s.grid.nonempty_count() == 0
    assert s.redo()
    assert s.grid.nonempty_count() == 27


def test_session_set_box_clips_by_default():
    s = Session.new((4, 4, 4))
    n = s.set_box((-2, -2, -2), (1, 1, 1), "minecraft:stone")
    assert n == 8
    assert s.grid.nonempty_count() == 8


def test_session_set_many_dedupes_and_skips_out_of_bounds():
    s = Session.new((4, 4, 4))
    n = s.set_many([(0, 0, 0), (0, 0, 0), (1, 0, 0), (9, 0, 0)], "minecraft:dirt")
    assert n == 2
    assert s.grid.count("minecraft:dirt") == 2


def test_session_set_many_history_false_clears_stale_history():
    s = Session.new((4, 4, 4))
    s.set_many([(0, 0, 0)], "minecraft:stone")
    assert s.undo()
    assert s.redo()
    s.set_many([(1, 0, 0)], "minecraft:stone", history=False)
    assert not s.undo()
