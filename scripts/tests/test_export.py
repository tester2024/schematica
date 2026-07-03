"""Tests for Sponge export."""
from __future__ import annotations

import gzip
import io
import json
from pathlib import Path

import numpy as np
import pytest
import nbtlib

from schematica.blocks.block import Block
from schematica.core.voxel import VoxelGrid
from schematica.export.sponge import write_sponge
from schematica.shapes.primitives import Box
from schematica.session.session import Session


def _load_schem(path: Path) -> nbtlib.File:
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(path.read_bytes())))


def test_export_stone_cube(tmp_path):
    s = Session.new((3, 3, 3))
    s.add(Box(0, 0, 0, 2, 2, 2), "minecraft:stone")
    out = tmp_path / "cube.schem"
    write_sponge(s.grid, out)
    assert out.exists()
    # Read it back
    raw = gzip.decompress(out.read_bytes())
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