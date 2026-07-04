"""Tests for ChunkedGrid sparse storage."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.blocks.block import AIR, Block
from schematica.core.chunked import ChunkedGrid
from schematica.core.voxel import VoxelGrid


def test_chunked_default_empty():
    g = ChunkedGrid(shape=(32, 32, 32))
    assert g.nonempty_count() == 0
    assert g.chunk_count() == 0
    assert g.memory_estimate_bytes() == 0


def test_chunked_set_get_single():
    g = ChunkedGrid(shape=(32, 32, 32))
    b = Block.parse("minecraft:stone")
    g.set(5, 6, 7, b)
    assert g.get(5, 6, 7) == b
    assert g.nonempty_count() == 1
    assert g.chunk_count() == 1


def test_chunked_set_out_of_bounds():
    g = ChunkedGrid(shape=(8, 8, 8))
    with pytest.raises(IndexError):
        g.set(10, 0, 0, Block.parse("minecraft:stone"))


def test_chunked_get_out_of_bounds():
    g = ChunkedGrid(shape=(8, 8, 8))
    with pytest.raises(IndexError):
        g.get(10, 0, 0)


def test_chunked_fill_then_clear():
    g = ChunkedGrid(shape=(16, 16, 16))
    g.fill(Block.parse("minecraft:stone"))
    assert g.nonempty_count() == 16 * 16 * 16
    g.fill_air()
    assert g.nonempty_count() == 0
    assert g.chunk_count() == 0


def test_chunked_apply_mask_sparse():
    g = ChunkedGrid(shape=(64, 64, 64))
    mask = np.zeros((64, 64, 64), dtype=bool)
    mask[10:12, 10:12, 10:12] = True
    g.apply_mask(mask, Block.parse("minecraft:stone"))
    assert g.nonempty_count() == 8
    # Only chunks overlapping [10:12]^3 should be materialised.
    assert g.chunk_count() <= 8


def test_chunked_erase_mask_frees_chunks():
    g = ChunkedGrid(shape=(32, 32, 32))
    mask = np.zeros((32, 32, 32), dtype=bool)
    mask[0:4, 0:4, 0:4] = True
    g.apply_mask(mask, Block.parse("minecraft:stone"))
    assert g.chunk_count() == 1
    g.erase_mask(mask)
    assert g.chunk_count() == 0
    assert g.nonempty_count() == 0


def test_chunked_paint_mask_only_solid():
    g = ChunkedGrid(shape=(16, 16, 16))
    g.set(0, 0, 0, Block.parse("minecraft:stone"))
    mask = np.ones((16, 16, 16), dtype=bool)
    g.paint_mask(mask, Block.parse("minecraft:dirt"))
    assert g.get(0, 0, 0) == Block.parse("minecraft:dirt")
    # Voxels that were air stay air.
    assert g.get(5, 5, 5) == AIR


def test_chunked_replace():
    g = ChunkedGrid(shape=(16, 16, 16))
    g.fill(Block.parse("minecraft:stone"))
    n = g.replace(Block.parse("minecraft:stone"), Block.parse("minecraft:dirt"))
    assert n == 16 ** 3
    assert g.count(Block.parse("minecraft:dirt")) == 16 ** 3
    assert g.count(Block.parse("minecraft:stone")) == 0


def test_chunked_count_across_chunks():
    g = ChunkedGrid(shape=(32, 32, 32), chunk_size=16)
    g.set(0, 0, 0, Block.parse("minecraft:stone"))
    g.set(20, 20, 20, Block.parse("minecraft:stone"))
    assert g.count(Block.parse("minecraft:stone")) == 2
    assert g.chunk_count() == 2


def test_chunked_to_dense_roundtrip():
    g = ChunkedGrid(shape=(16, 16, 16))
    g.set(3, 5, 7, Block.parse("minecraft:stone"))
    g.set(10, 11, 12, Block.parse("minecraft:dirt"))
    dense = g.to_dense()
    assert isinstance(dense, VoxelGrid)
    assert dense.shape == (16, 16, 16)
    assert dense.get(3, 5, 7) == Block.parse("minecraft:stone")
    assert dense.get(10, 11, 12) == Block.parse("minecraft:dirt")
    assert dense.get(0, 0, 0) == AIR


def test_chunked_from_dense():
    vg = VoxelGrid(shape=(16, 16, 16))
    vg.set(2, 3, 4, Block.parse("minecraft:stone"))
    vg.set(8, 9, 10, Block.parse("minecraft:dirt"))
    cg = ChunkedGrid.from_dense(vg, chunk_size=8)
    assert cg.shape == (16, 16, 16)
    assert cg.get(2, 3, 4) == Block.parse("minecraft:stone")
    assert cg.get(8, 9, 10) == Block.parse("minecraft:dirt")
    # Only 2 chunks should be materialised (each voxel in a different chunk).
    assert cg.chunk_count() <= 2


def test_chunked_copy():
    g = ChunkedGrid(shape=(16, 16, 16))
    g.set(0, 0, 0, Block.parse("minecraft:stone"))
    c = g.copy()
    c.set(0, 0, 0, Block.parse("minecraft:dirt"))
    assert g.get(0, 0, 0) == Block.parse("minecraft:stone")
    assert c.get(0, 0, 0) == Block.parse("minecraft:dirt")


def test_chunked_equality():
    a = ChunkedGrid(shape=(16, 16, 16))
    b = ChunkedGrid(shape=(16, 16, 16))
    a.set(1, 2, 3, Block.parse("minecraft:stone"))
    b.set(1, 2, 3, Block.parse("minecraft:stone"))
    assert a == b
    b.set(4, 5, 6, Block.parse("minecraft:stone"))
    assert a != b


def test_chunked_iter_chunks_in_box():
    g = ChunkedGrid(shape=(64, 64, 64), chunk_size=16)
    g.set(5, 5, 5, Block.parse("minecraft:stone"))
    g.set(50, 50, 50, Block.parse("minecraft:dirt"))
    touched = list(g.iter_chunks_in_box(0, 0, 0, 20, 20, 20))
    assert len(touched) == 1
    cx, cy, cz, arr, origin = touched[0]
    assert (cx, cy, cz) == (0, 0, 0)


def test_chunked_edge_chunk_clamped():
    g = ChunkedGrid(shape=(20, 20, 20), chunk_size=16)
    g.set(18, 18, 18, Block.parse("minecraft:stone"))
    arr = g._chunks.get((1, 1, 1))
    assert arr is not None
    assert arr.shape == (4, 4, 4)
