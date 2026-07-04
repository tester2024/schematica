"""Tests for Palette + VoxelGrid."""
from __future__ import annotations

import numpy as np

from schematica.blocks.block import AIR, Block
from schematica.core.palette import Palette
from schematica.core.voxel import VoxelGrid


def test_palette_dedupe():
    p = Palette()
    i1 = p.add(Block.parse("minecraft:stone"))
    i2 = p.add(Block.parse("minecraft:stone"))
    assert i1 == i2
    assert i1 > 0  # air is 0
    assert p[0] == AIR


def test_palette_air_zero():
    p = Palette()
    assert p.index_of(AIR) == 0


def test_voxelgrid_default_air():
    g = VoxelGrid(shape=(4, 4, 4))
    assert g.nonempty_count() == 0
    assert g.data.dtype == np.uint16
    assert g.data.shape == (4, 4, 4)


def test_voxelgrid_set_get():
    g = VoxelGrid(shape=(4, 4, 4))
    b = Block.parse("minecraft:stone")
    g.set(1, 2, 3, b)
    assert g.get(1, 2, 3) == b
    assert g.nonempty_count() == 1


def test_voxelgrid_fill():
    g = VoxelGrid(shape=(2, 2, 2))
    g.fill(Block.parse("minecraft:stone"))
    assert g.nonempty_count() == 8


def test_voxelgrid_replace():
    g = VoxelGrid(shape=(2, 2, 2))
    g.fill(Block.parse("minecraft:stone"))
    n = g.replace(Block.parse("minecraft:stone"), Block.parse("minecraft:dirt"))
    assert n == 8
    assert g.count(Block.parse("minecraft:dirt")) == 8


def test_voxelgrid_subregion():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(1, 1, 1, Block.parse("minecraft:stone"))
    sub = g.subregion((0, 0, 0), (2, 2, 2))
    assert sub.shape == (2, 2, 2)
    assert sub.get(1, 1, 1) == Block.parse("minecraft:stone")


def test_voxelgrid_rotate_shape():
    g = VoxelGrid(shape=(2, 4, 8))
    r = g.rotate(1, "xy")
    assert r.shape == (4, 2, 8)


def test_voxelgrid_mirror():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:stone"))
    m = g.mirror(0)
    assert m.get(3, 0, 0) == Block.parse("minecraft:stone")
