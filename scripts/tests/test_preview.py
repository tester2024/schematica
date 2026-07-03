"""Tests for preview rendering."""
from __future__ import annotations

from pathlib import Path

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