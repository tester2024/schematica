"""Tests for advanced replace, retexture, and texture palette generator."""
from __future__ import annotations

import numpy as np

from schematica.blocks.block import AIR, Block
from schematica.core.voxel import VoxelGrid
from schematica.generators.replace import (
    NeighbourSpec,
    replace_bulk,
    replace_by_name,
    replace_in_mask,
    replace_pattern,
)
from schematica.generators.retexture import (
    retexture,
    retexture_map,
    retexture_random,
)
from schematica.generators.texture import TexturePalette, apply_texture, worley_field
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _dense_grid_with(*blocks: tuple[int, Block]) -> VoxelGrid:
    """Build a small dense grid where each (index, block) sets one voxel."""
    g = VoxelGrid(shape=(4, 4, 4))
    for (i, b) in blocks:
        x, y, z = (i % 4, (i // 4) % 4, (i // 16) % 4)
        g.set(x, y, z, b)
    return g


# ---- bulk replace ----------------------------------------------------

def test_replace_bulk_multiple_sources():
    g = _dense_grid_with(
        (0, Block.parse("minecraft:stone")),
        (1, Block.parse("minecraft:dirt")),
        (2, Block.parse("minecraft:cobblestone")),
    )
    n = replace_bulk(g, {"minecraft:stone": "minecraft:diorite",
                          "minecraft:dirt": "minecraft:grass_block"})
    assert n == 2
    assert g.get(0, 0, 0) == Block.parse("minecraft:diorite")
    assert g.get(1, 0, 0) == Block.parse("minecraft:grass_block")
    # Unmapped block untouched.
    assert g.get(2, 0, 0) == Block.parse("minecraft:cobblestone")


def test_replace_bulk_unknown_source_skipped():
    g = _dense_grid_with((0, Block.parse("minecraft:stone")))
    n = replace_bulk(g, {"minecraft:nonsense": "minecraft:dirt"})
    assert n == 0
    assert g.get(0, 0, 0) == Block.parse("minecraft:stone")


def test_replace_bulk_chunked():
    s = Session.new((8, 8, 8), chunked=True, chunk_size=4)
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    s.add(Box(4, 4, 4, 7, 7, 7), "minecraft:dirt")
    n = replace_bulk(s.grid, {"minecraft:stone": "minecraft:diorite",
                               "minecraft:dirt": "minecraft:grass_block"})
    assert n == 64 + 64
    assert s.grid.get(0, 0, 0) == Block.parse("minecraft:diorite")
    assert s.grid.get(4, 4, 4) == Block.parse("minecraft:grass_block")


# ---- replace_by_name -------------------------------------------------

def test_replace_by_name_all_states():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    g.set(1, 0, 0, Block.parse("minecraft:oak_log[axis=x]"))
    g.set(2, 0, 0, Block.parse("minecraft:stone"))
    n = replace_by_name(g, "minecraft:oak_log", "minecraft:oak_log[axis=z]")
    assert n == 2
    assert g.get(0, 0, 0) == Block.parse("minecraft:oak_log[axis=z]")
    assert g.get(1, 0, 0) == Block.parse("minecraft:oak_log[axis=z]")
    # Stone untouched.
    assert g.get(2, 0, 0) == Block.parse("minecraft:stone")


def test_replace_by_name_with_filter():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    g.set(1, 0, 0, Block.parse("minecraft:oak_log[axis=x]"))
    n = replace_by_name(g, "minecraft:oak_log", "minecraft:birch_log",
                        where=lambda b: dict(b.states).get("axis") == "y")
    assert n == 1
    assert g.get(0, 0, 0) == Block.parse("minecraft:birch_log")
    # axis=x untouched.
    assert g.get(1, 0, 0) == Block.parse("minecraft:oak_log[axis=x]")


# ---- replace_pattern -------------------------------------------------

def test_replace_pattern_dirt_under_grass():
    g = VoxelGrid(shape=(4, 4, 4))
    # Column: grass on top, dirt below.
    g.set(0, 1, 0, Block.parse("minecraft:grass_block"))
    g.set(0, 0, 0, Block.parse("minecraft:dirt"))
    # Standalone dirt with air above.
    g.set(1, 0, 0, Block.parse("minecraft:dirt"))
    n = replace_pattern(g, "minecraft:dirt", "minecraft:stone",
                        neighbours=[NeighbourSpec((0, 1, 0), "minecraft:grass_block")])
    assert n == 1
    assert g.get(0, 0, 0) == Block.parse("minecraft:stone")
    # Standalone dirt untouched.
    assert g.get(1, 0, 0) == Block.parse("minecraft:dirt")


def test_replace_pattern_any_solid_above():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:stone"))
    g.set(0, 1, 0, Block.parse("minecraft:dirt"))
    g.set(1, 0, 0, Block.parse("minecraft:stone"))  # air above -> no match
    n = replace_pattern(g, "minecraft:stone", "minecraft:cobblestone",
                        neighbours=[NeighbourSpec((0, 1, 0), "*")])
    assert n == 1
    assert g.get(0, 0, 0) == Block.parse("minecraft:cobblestone")
    assert g.get(1, 0, 0) == Block.parse("minecraft:stone")


def test_replace_pattern_touches_air():
    g = VoxelGrid(shape=(4, 4, 4))
    # Stone at (1,0,0) with air at (2,0,0) -> match.
    g.set(1, 0, 0, Block.parse("minecraft:stone"))
    # Stone at (1,0,1) with stone at (2,0,1) and (3,0,1) -> no air on +x.
    g.set(1, 0, 1, Block.parse("minecraft:stone"))
    g.set(2, 0, 1, Block.parse("minecraft:stone"))
    g.set(3, 0, 1, Block.parse("minecraft:stone"))
    n = replace_pattern(g, "minecraft:stone", "minecraft:cobblestone",
                        neighbours=[NeighbourSpec((1, 0, 0), "air")])
    assert n == 1
    assert g.get(1, 0, 0) == Block.parse("minecraft:cobblestone")
    # (1,0,1) is stone with stone on +x, untouched.
    assert g.get(1, 0, 1) == Block.parse("minecraft:stone")


# ---- replace_in_mask -------------------------------------------------

def test_replace_in_mask_region():
    g = VoxelGrid(shape=(4, 4, 4))
    g.fill(Block.parse("minecraft:stone"))
    mask = np.zeros((4, 4, 4), dtype=bool)
    mask[0:2, 0:2, 0:2] = True
    n = replace_in_mask(g, "minecraft:stone", "minecraft:dirt", mask)
    assert n == 8
    assert g.get(0, 0, 0) == Block.parse("minecraft:dirt")
    assert g.get(2, 2, 2) == Block.parse("minecraft:stone")


# ---- retexture -------------------------------------------------------

def test_retexture_set_axis():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    g.set(1, 0, 0, Block.parse("minecraft:oak_log[axis=x]"))
    n = retexture(g, "axis", "z", name="minecraft:oak_log")
    assert n == 2
    assert g.get(0, 0, 0) == Block.parse("minecraft:oak_log[axis=z]")
    assert g.get(1, 0, 0) == Block.parse("minecraft:oak_log[axis=z]")


def test_retexture_map_rotate_axes():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:oak_log[axis=x]"))
    g.set(1, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    g.set(2, 0, 0, Block.parse("minecraft:oak_log[axis=z]"))
    n = retexture_map(g, "axis", {"x": "y", "y": "z", "z": "x"},
                      name="minecraft:oak_log")
    assert n == 3
    assert g.get(0, 0, 0) == Block.parse("minecraft:oak_log[axis=y]")
    assert g.get(1, 0, 0) == Block.parse("minecraft:oak_log[axis=z]")
    assert g.get(2, 0, 0) == Block.parse("minecraft:oak_log[axis=x]")


def test_retexture_only_affects_named_block():
    g = VoxelGrid(shape=(4, 4, 4))
    g.set(0, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    g.set(1, 0, 0, Block.parse("minecraft:stone"))
    n = retexture(g, "axis", "x", name="minecraft:oak_log")
    assert n == 1
    assert g.get(0, 0, 0) == Block.parse("minecraft:oak_log[axis=x]")
    # Stone untouched (no axis property anyway).
    assert g.get(1, 0, 0) == Block.parse("minecraft:stone")


def test_retexture_random():
    g = VoxelGrid(shape=(16, 1, 1))
    for i in range(16):
        g.set(i, 0, 0, Block.parse("minecraft:oak_log[axis=y]"))
    n = retexture_random(g, "axis", ["x", "y", "z"], name="minecraft:oak_log", seed=42)
    assert n == 16
    # Should have some variety (not all the same axis).
    axes = {g.get(i, 0, 0).states[0][1] for i in range(16)}
    assert len(axes) >= 2


# ---- texture palette -------------------------------------------------

def test_texture_palette_sample_shape():
    tp = TexturePalette(
        blocks=["minecraft:stone", "minecraft:dirt", "minecraft:cobblestone"],
        weights=[0.5, 0.3, 0.2],
        noise="perlin", scale=0.5, seed=0,
    )
    idx = tp.sample((8, 8))
    assert idx.shape == (8, 8)
    assert idx.min() >= 0
    assert idx.max() < 3


def test_texture_palette_blockstate_grid():
    tp = TexturePalette(
        blocks=["minecraft:stone", "minecraft:dirt"],
        noise="perlin", scale=0.5, seed=1,
    )
    grid = tp.blockstate_grid((4, 4))
    assert grid.shape == (4, 4)
    # Every cell should be one of the two blocks.
    for x in range(4):
        for z in range(4):
            assert grid[x, z] in ("minecraft:stone", "minecraft:dirt")


def test_worley_field_shape_and_range():
    f = worley_field((8, 8), num_points=4, seed=0)
    assert f.shape == (8, 8)
    assert f.min() >= 0.0
    assert f.max() <= 1.0


def test_apply_texture_paints_existing_only():
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 3, 0, 3), "minecraft:stone")
    tp = TexturePalette(
        blocks=["minecraft:stone", "minecraft:cobblestone"],
        weights=[0.5, 0.5],
        noise="perlin", scale=0.5, seed=0,
    )
    n = apply_texture(s, tp, (0, 0, 0), (3, 0, 3))
    # Only the 16 solid voxels in the floor should be painted.
    assert n == 16
    # Air layer above should remain air.
    assert s.grid.get(0, 1, 0) == AIR


def test_texture_palette_chunked():
    s = Session.new((8, 8, 8), chunked=True, chunk_size=4)
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    tp = TexturePalette(
        blocks=["minecraft:stone", "minecraft:cobblestone"],
        weights=[0.5, 0.5],
        noise="perlin", scale=0.3, seed=42,
    )
    n = apply_texture(s, tp, (0, 0, 0), (7, 0, 7))
    assert n == 64
    # Should have both block types present (with this seed + scale).
    blocks_present = {s.grid.get(x, 0, z).name for x in range(8) for z in range(8)}
    assert "minecraft:stone" in blocks_present
    assert "minecraft:cobblestone" in blocks_present
