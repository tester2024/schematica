"""Tests for Sponge export."""
from __future__ import annotations

import gzip
import io
import warnings
from pathlib import Path

import nbtlib
import pytest

from schematica.export.sponge import write_sponge
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _load_schem(path: Path) -> nbtlib.File:
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(path.read_bytes())))


def test_export_stone_cube(tmp_path):
    s = Session.new((3, 3, 3))
    s.add(Box(0, 0, 0, 2, 2, 2), "minecraft:stone")
    out = tmp_path / "cube.schem"
    write_sponge(s.grid, out)
    assert out.exists()
    # Read it back
    f = _load_schem(out)
    sch = f["Schematic"]
    assert int(sch["Width"]) == 3
    assert int(sch["Height"]) == 3
    assert int(sch["Length"]) == 3
    assert "minecraft:stone" in sch["Palette"]
    assert int(sch["Palette"]["minecraft:stone"]) > 0
    # BlockData length: each voxel varint (idx=1 -> 1 byte), 27 voxels
    assert len(bytes(sch["BlockData"])) == 27


def test_export_air_grid(tmp_path):
    s = Session.new((2, 2, 2))
    out = tmp_path / "empty.schem"
    write_sponge(s.grid, out)
    f = _load_schem(out)
    assert int(f["Schematic"]["Palette"]["minecraft:air"]) == 0


def test_export_offset_and_metadata(tmp_path):
    s = Session.new((2, 2, 2))
    s.fill_all("minecraft:stone")
    out = tmp_path / "off.schem"
    write_sponge(s.grid, out, offset=(5, 10, 15), metadata={"name": "test"})
    f = _load_schem(out)
    assert [int(v) for v in f["Schematic"]["Offset"]] == [5, 10, 15]
    assert str(f["Schematic"]["Metadata"]["name"]) == "test"


def test_export_warns_on_modern_palette_with_legacy_data_version(tmp_path):
    s = Session.new((1, 1, 1))
    s.fill_all("minecraft:red_wool")
    with pytest.warns(RuntimeWarning, match="pre-1.13"):
        write_sponge(s.grid, tmp_path / "legacy.schem", data_version=169)


def test_export_allows_legacy_data_version_for_simple_palette(tmp_path):
    s = Session.new((1, 1, 1))
    s.fill_all("minecraft:stone")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        write_sponge(s.grid, tmp_path / "legacy_stone.schem", data_version=169)
    assert not caught
