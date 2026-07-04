"""Tests for preview rendering."""
from __future__ import annotations

import pytest

from schematica.render.preview import preview
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def test_preview_writes_pngs(tmp_path):
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 6, 6, 6), "minecraft:stone")
    paths = preview(s.grid, tmp_path)
    names = {p.name for p in paths}
    assert {"preview_top.png", "preview_front.png", "preview_right.png", "preview_iso.png"} <= names
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 100  # non-trivial PNG


def test_preview_projects_large_dense_grid(tmp_path):
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 7, 7), "minecraft:stone")
    with pytest.warns(RuntimeWarning, match="projected previews"):
        paths = preview(s.grid, tmp_path, views=("top",), max_voxels=1, max_dim=4)
    assert [p.name for p in paths] == ["preview_top.png"]
    assert paths[0].exists()
    assert paths[0].stat().st_size > 100


def test_preview_names_projected_iso_explicitly(tmp_path):
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 7, 7), "minecraft:stone")
    with pytest.warns(RuntimeWarning, match="projected previews"):
        paths = preview(s.grid, tmp_path, views=("iso",), max_voxels=1, max_dim=4)
    assert [p.name for p in paths] == ["preview_iso_projected.png"]
