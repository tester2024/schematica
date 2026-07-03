"""Tests for MCEdit .schematic and Litematica .litematic exporters."""
from __future__ import annotations

import gzip
import io
from pathlib import Path

import numpy as np
import nbtlib
import pytest

from schematica.core.chunked import ChunkedGrid
from schematica.core.voxel import VoxelGrid
from schematica.export.litematic import write_litematic
from schematica.export.mcedit import write_mcedit
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _load_nbt(path: Path) -> nbtlib.File:
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(path.read_bytes())))


# ---- MCEdit -----------------------------------------------------------

def test_mcedit_stone_cube(tmp_path):
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    out = tmp_path / "cube.schematic"
    write_mcedit(s.grid, out)
    assert out.exists()
    f = _load_nbt(out)
    assert int(f["Width"]) == 4
    assert int(f["Height"]) == 4
    assert int(f["Length"]) == 4
    assert str(f["Materials"]) == "Alpha"
    blocks = bytes(f["Blocks"])
    # 4*4*4 = 64 voxels; stone id = 1.
    assert len(blocks) == 64
    assert any(b == 1 for b in blocks)


def test_mcedit_unknown_block_becomes_air(tmp_path):
    from schematica.blocks.block import Block
    from schematica.core.palette import Palette
    g = VoxelGrid(shape=(2, 2, 2))
    g.palette = Palette.from_blocks([Block.parse("minecraft:air"),
                                       Block.parse("minecraft:nonsense_block")])
    g.data[...] = 1
    out = tmp_path / "weird.schematic"
    write_mcedit(g, out)
    f = _load_nbt(out)
    blocks = bytes(f["Blocks"])
    # Unknown block -> id 0 (air).
    assert all(b == 0 for b in blocks)


def test_mcedit_chunked_matches_dense(tmp_path):
    sd = Session.new((8, 8, 8), chunked=False)
    sc = Session.new((8, 8, 8), chunked=True, chunk_size=4)
    for s in (sd, sc):
        s.add(Box(1, 1, 1, 6, 6, 6), "minecraft:stone")
    pd = tmp_path / "d.schematic"
    pc = tmp_path / "c.schematic"
    write_mcedit(sd.grid, pd)
    write_mcedit(sc.grid, pc)
    bd = bytes(_load_nbt(pd)["Blocks"])
    bc = bytes(_load_nbt(pc)["Blocks"])
    assert bd == bc


def test_mcedit_custom_legacy_id_mapping(tmp_path):
    from schematica.blocks.block import Block
    from schematica.core.palette import Palette
    g = VoxelGrid(shape=(2, 2, 2))
    g.palette = Palette.from_blocks([Block.parse("minecraft:air"),
                                       Block.parse("minecraft:custom_block")])
    g.data[...] = 1
    out = tmp_path / "custom.schematic"
    write_mcedit(g, out, legacy_ids={"minecraft:custom_block": 200})
    f = _load_nbt(out)
    blocks = bytes(f["Blocks"])
    assert 200 in blocks


# ---- Litematic --------------------------------------------------------

def test_litematic_stone_cube(tmp_path):
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    out = tmp_path / "cube.litematic"
    write_litematic(s.grid, out)
    assert out.exists()
    f = _load_nbt(out)
    assert int(f["MinecraftDataVersion"]) == 3465
    assert int(f["Version"]) == 5
    region = f["Regions"]["Main"]
    assert int(region["Size"]["x"]) == 4
    assert int(region["Size"]["y"]) == 4
    assert int(region["Size"]["z"]) == 4
    palette = region["BlockStatePalette"]
    # Palette should contain at least air + stone.
    names = [str(p["Name"]) for p in palette]
    assert "minecraft:stone" in names
    assert "minecraft:air" in names


def test_litematic_blockstate_with_properties(tmp_path):
    s = Session.new((2, 2, 2))
    # oak_log[axis=y] is a stateful block.
    s.add(Box(0, 0, 0, 1, 1, 1), "minecraft:oak_log[axis=y]")
    out = tmp_path / "log.litematic"
    write_litematic(s.grid, out)
    f = _load_nbt(out)
    palette = f["Regions"]["Main"]["BlockStatePalette"]
    # Find the oak_log entry and check it carries Properties.axis = "y".
    log_entry = next(p for p in palette if str(p["Name"]) == "minecraft:oak_log")
    assert "Properties" in log_entry
    assert str(log_entry["Properties"]["axis"]) == "y"


def test_litematic_chunked_matches_dense(tmp_path):
    sd = Session.new((8, 8, 8), chunked=False)
    sc = Session.new((8, 8, 8), chunked=True, chunk_size=4)
    for s in (sd, sc):
        s.add(Box(1, 1, 1, 6, 6, 6), "minecraft:stone")
    write_litematic(sd.grid, tmp_path / "d.litematic")
    write_litematic(sc.grid, tmp_path / "c.litematic")
    fd = _load_nbt(tmp_path / "d.litematic")
    fc = _load_nbt(tmp_path / "c.litematic")
    # Same packed long array length and content.
    bd = list(fd["Regions"]["Main"]["BlockStates"])
    bc = list(fc["Regions"]["Main"]["BlockStates"])
    assert len(bd) == len(bc)
    assert bd == bc


def test_litematic_offset_origin(tmp_path):
    s = Session.new((2, 2, 2))
    write_litematic(s.grid, tmp_path / "o.litematic", origin=(10, 20, 30))
    f = _load_nbt(tmp_path / "o.litematic")
    pos = f["Regions"]["Main"]["Position"]
    assert [int(pos["x"]), int(pos["y"]), int(pos["z"])] == [10, 20, 30]