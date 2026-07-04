"""Tests for markers, regions, cropped preview, and compatibility report."""
from __future__ import annotations

import json
from pathlib import Path

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def test_marker_and_region_metadata():
    s = Session.new((16, 16, 16))
    s.marker("spawn", 8, 1, 8, kind="point")
    s.region("arena", (0, 0, 0), (8, 4, 8), kind="area")
    ms = s.markers()
    rs = s.regions()
    assert len(ms) == 1 and ms[0]["name"] == "spawn"
    assert ms[0]["pos"] == [8, 1, 8] and ms[0]["kind"] == "point"
    assert len(rs) == 1 and rs[0]["name"] == "arena"
    assert rs[0]["corner"] == [0, 0, 0] and rs[0]["size"] == [8, 4, 8]


def test_region_out_of_bounds_raises():
    s = Session.new((8, 8, 8))
    try:
        s.region("bad", (4, 4, 4), (8, 8, 8))
    except ValueError:
        return
    raise AssertionError("expected ValueError for out-of-bounds region")


def test_export_markers_writes_json(tmp_path):
    s = Session.new((16, 16, 16))
    s.marker("m1", 1, 2, 3)
    s.region("r1", (0, 0, 0), (2, 2, 2))
    p = tmp_path / "markers.json"
    s.export_markers(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["shape"] == [16, 16, 16]
    assert len(data["markers"]) == 1
    assert len(data["regions"]) == 1


def test_stats_includes_markers_regions_counts():
    s = Session.new((8, 8, 8))
    s.marker("a", 0, 0, 0)
    s.region("b", (0, 0, 0), (1, 1, 1))
    st = s.stats()
    assert st["markers"] == 1 and st["regions"] == 1


def test_markers_survive_save_load(tmp_path):
    s = Session.new((8, 8, 8))
    s.marker("keep", 4, 5, 6)
    sp = tmp_path / "sess.json"
    s.save(sp)
    s2 = Session.load(sp)
    assert len(s2.markers()) == 1
    assert s2.markers()[0]["pos"] == [4, 5, 6]


def test_dispatch_marker_region_commands():
    s = Session.new((16, 16, 16))
    r1 = dispatch(s, "marker name=spawn x=8 y=1 z=8 kind=point")
    assert "spawn" in r1
    r2 = dispatch(s, "region name=arena corner_x=0 corner_y=0 corner_z=0 sx=8 sy=4 sz=8 kind=area")
    assert "arena" in r2
    assert len(s.markers()) == 1
    assert len(s.regions()) == 1


def test_dispatch_report_command():
    s = Session.new((8, 8, 8))
    dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    out = dispatch(s, "report")
    assert "palette=" in out and "blocks=" in out


def test_preview_region_renders_subset(tmp_path):
    from schematica.render.preview import preview_region
    s = Session.new((16, 16, 16))
    dispatch(s, "add.box frm=0,0,0 to=15,15,15 block=minecraft:stone")
    paths = preview_region(s.grid, (0, 0, 0), (4, 4, 4), tmp_path)
    assert paths
    for p in paths:
        assert Path(p).exists()


def test_preview_region_out_of_bounds_raises(tmp_path):
    from schematica.render.preview import preview_region
    s = Session.new((8, 8, 8))
    try:
        preview_region(s.grid, (4, 4, 4), (8, 8, 8), tmp_path)
    except ValueError:
        return
    raise AssertionError("expected ValueError for out-of-bounds region")


def test_palette_report_unknown_and_mcedit():
    from schematica.export.report import palette_report
    s = Session.new((8, 8, 8))
    dispatch(s, "add.box frm=0,0,0 to=2,2,2 block=minecraft:stone")
    rep = palette_report(s.grid)
    assert rep["palette_size"] >= 2
    assert rep["block_count"] == 27
    assert rep["mcedit_unmapped"] == []  # stone is mapped
    assert rep["sponge_ok"] is False  # no registry passed