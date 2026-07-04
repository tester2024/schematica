"""Tests for chunked Session backend and chunked Sponge export."""
from __future__ import annotations

import numpy as np

from schematica.blocks.block import Block
from schematica.core.chunked import ChunkedGrid
from schematica.export.sponge import write_sponge
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere


def test_session_chunked_new():
    s = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    assert s.is_chunked
    assert isinstance(s.grid, ChunkedGrid)
    assert s.grid.chunk_size == 16


def test_session_chunked_add_box():
    s = Session.new((64, 64, 64), chunked=True, chunk_size=16)
    s.add(Box(10, 10, 10, 20, 20, 20), "minecraft:stone")
    assert s.grid.nonempty_count() == 11 ** 3
    # Should touch only chunks overlapping [10..20]^3, not all 64^3.
    assert s.grid.chunk_count() <= 8
    assert s.grid.get(15, 15, 15).name == "minecraft:stone"
    assert s.grid.get(0, 0, 0).name == "minecraft:air"


def test_session_chunked_add_sphere_sparse_chunks():
    s = Session.new((128, 128, 128), chunked=True, chunk_size=16)
    s.add(Sphere(64, 64, 64, 8), "minecraft:stone")
    # Sphere r=8 should fit in ~2x2x2 chunks, not 8x8x8=512.
    assert s.grid.chunk_count() <= 27
    assert s.grid.nonempty_count() > 0


def test_session_chunked_subtract():
    s = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 15, 15, 15), "minecraft:stone")
    s.subtract(Box(5, 5, 5, 10, 10, 10))
    assert s.grid.nonempty_count() == 16 ** 3 - 6 ** 3
    assert s.grid.get(7, 7, 7).name == "minecraft:air"


def test_session_chunked_paint():
    s = Session.new((16, 16, 16), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 5, 5, 5), "minecraft:stone")
    s.paint(Box(0, 0, 0, 5, 5, 5), "minecraft:dirt")
    assert s.grid.get(2, 2, 2).name == "minecraft:dirt"
    # Paint shouldn't fill air.
    assert s.grid.get(10, 10, 10).name == "minecraft:air"


def test_session_chunked_undo_redo():
    s = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 5, 5, 5), "minecraft:stone")
    assert s.grid.nonempty_count() == 6 ** 3
    assert s.undo()
    assert s.grid.nonempty_count() == 0
    assert s.redo()
    assert s.grid.nonempty_count() == 6 ** 3


def test_session_chunked_replace():
    s = Session.new((16, 16, 16), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 15, 15, 15), "minecraft:stone")
    n = s.replace("minecraft:stone", "minecraft:dirt")
    assert n == 16 ** 3
    assert s.grid.count(Block.parse("minecraft:dirt")) == 16 ** 3


def test_session_chunked_stats():
    s = Session.new((64, 64, 64), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 15, 15, 15), "minecraft:stone")
    st = s.stats()
    assert st["chunked"] is True
    assert st["chunks"] >= 1
    assert st["chunk_size"] == 16
    assert "memory_bytes" in st


def test_session_chunked_save_load(tmp_path):
    s = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    s.add(Box(0, 0, 0, 10, 10, 10), "minecraft:stone")
    p = s.save(tmp_path / "session.json")
    s2 = Session.load(p)
    assert s2.is_chunked
    assert s2.grid.chunk_size == 16
    assert s2.grid.nonempty_count() == 11 ** 3
    assert s2.grid.get(5, 5, 5).name == "minecraft:stone"


def test_session_chunked_matches_dense():
    # Same build in dense vs chunked should produce identical voxel data.
    sd = Session.new((32, 32, 32), chunked=False)
    sc = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    for s in (sd, sc):
        s.add(Box(2, 2, 2, 20, 20, 20), "minecraft:stone")
        s.add(Sphere(16, 16, 16, 8), "minecraft:dirt")
    dense_data = sd.grid.data
    chunked_dense = sc.grid.to_dense().data
    assert np.array_equal(dense_data, chunked_dense)


def test_export_chunked_matches_dense(tmp_path):
    sd = Session.new((32, 32, 32), chunked=False)
    sc = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    for s in (sd, sc):
        s.add(Box(2, 2, 2, 20, 20, 20), "minecraft:stone")
        s.add(Sphere(16, 16, 16, 8), "minecraft:dirt")
    pd = tmp_path / "dense.schem"
    pc = tmp_path / "chunked.schem"
    write_sponge(sd.grid, pd)
    write_sponge(sc.grid, pc)
    # Both files should exist and be non-empty.
    assert pd.exists() and pc.exists()
    assert pd.stat().st_size > 0
    assert pc.stat().st_size > 0
    # File sizes should be close (palette may differ in ordering, but data
    # is the same voxels).
    import nbtlib
    fd = nbtlib.File.load(pd, gzipped=True)
    fc = nbtlib.File.load(pc, gzipped=True)
    # Width/Height/Length must match.
    assert fd["Width"] == fc["Width"]
    assert fd["Height"] == fc["Height"]
    assert fd["Length"] == fc["Length"]
    # BlockData should be the same length (one varint per voxel).
    assert len(fd["BlockData"]) == len(fc["BlockData"])


def test_export_chunked_big_map_no_oom(tmp_path):
    # 100-chunk-scale map (160x64x160) -- would be 1.6M voxels dense, but
    # chunked should only allocate touched chunks.
    s = Session.new((160, 64, 160), chunked=True, chunk_size=16)
    s.add(Box(70, 30, 70, 90, 50, 90), "minecraft:stone")
    p = tmp_path / "big.schem"
    write_sponge(s.grid, p)
    assert p.exists()
    # Only a few chunks should be materialised, not all 10*4*10=400.
    # Box [70..90]x[30..50]x[70..90] spans 2*3*2 = 12 chunks.
    assert s.grid.chunk_count() <= 12


def test_chunked_set_box_and_set_many_undo_redo():
    s = Session.new((32, 32, 32), chunked=True, chunk_size=16)
    assert s.set_box((14, 14, 14), (17, 17, 17), "minecraft:stone") == 64
    assert s.grid.chunk_count() == 8
    assert s.undo()
    assert s.grid.nonempty_count() == 0
    assert s.redo()
    assert s.grid.nonempty_count() == 64
    assert s.set_many([(0, 0, 0), (31, 31, 31)], "minecraft:dirt") == 2
    assert s.grid.get(0, 0, 0).name == "minecraft:dirt"
    assert s.grid.get(31, 31, 31).name == "minecraft:dirt"
