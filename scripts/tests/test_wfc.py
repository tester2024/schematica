"""Tests for the Wave Function Collapse generator."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.generators.wfc import (
    ContradictionError,
    Tile,
    TileSet,
    WFC,
    run_wfc,
    tileset_mossy_ruins,
    tileset_wildcard,
)


def test_tileset_compatible_wildcard():
    ts = TileSet([
        Tile("minecraft:stone"),
        Tile("minecraft:dirt"),
    ])
    # All edges are "*" by default -> everything compatible.
    assert ts.compatible(0, 1, "+x")
    assert ts.compatible(0, 1, "-y")
    assert ts.compatible(1, 0, "+z")


def test_tileset_compatible_labelled():
    ts = TileSet([
        Tile("minecraft:stone",        ("s", "s", "s", "s", "s", "s")),
        Tile("minecraft:cobblestone",   ("c", "c", "c", "c", "c", "c")),
    ])
    # Different labels on touching faces => not compatible.
    assert not ts.compatible(0, 1, "+x")
    # Same label => compatible.
    assert ts.compatible(0, 0, "+x")
    # Wildcard edge always compatible.
    ts2 = TileSet([Tile("minecraft:stone", ("*", "s", "s", "s", "s", "s")),
                   Tile("minecraft:dirt", ("d", "d", "d", "d", "d", "d"))])
    assert ts2.compatible(0, 1, "+x")  # stone +x is "*" wildcard


def test_run_wfc_wildcard_converges():
    ts = tileset_wildcard(["minecraft:stone", "minecraft:dirt", "minecraft:cobblestone"])
    blocks = run_wfc((4, 4, 1), ts, seed=0)
    assert blocks.shape == (4, 4, 1)
    # Every cell should be one of the three blocks.
    for x in range(4):
        for y in range(4):
            assert blocks[x, y, 0] in ("minecraft:stone", "minecraft:dirt", "minecraft:cobblestone")


def test_run_wfc_mossy_ruins_converges():
    ts = tileset_mossy_ruins()
    blocks = run_wfc((6, 6, 1), ts, seed=42)
    assert blocks.shape == (6, 6, 1)
    flat = blocks.ravel().tolist()
    # Should have placed at least 2 distinct block types.
    assert len(set(flat)) >= 2


def test_run_wfc_3d_shape():
    ts = tileset_wildcard(["minecraft:stone", "minecraft:dirt"])
    blocks = run_wfc((3, 3, 3), ts, seed=7)
    assert blocks.shape == (3, 3, 3)


def test_wfc_contradiction_raises():
    # No tile is compatible with any other on +x/-x: every tile has +x="s"
    # and -x="d" (which never match). Once a cell collapses, its +x neighbour
    # has no allowed tile and the wave contradicts.
    ts = TileSet([
        Tile("minecraft:stone",      ("s", "d", "*", "*", "*", "*")),
        Tile("minecraft:dirt",        ("s", "d", "*", "*", "*", "*")),
    ])
    with pytest.raises(ContradictionError):
        run_wfc((2, 2, 1), ts, seed=0, max_iter=1000)


def test_wfc_seed_reproducible():
    ts = tileset_wildcard(["minecraft:stone", "minecraft:dirt", "minecraft:cobblestone"])
    a = run_wfc((4, 4, 1), ts, seed=123)
    b = run_wfc((4, 4, 1), ts, seed=123)
    # Same seed -> same output.
    assert a.tolist() == b.tolist()


def test_wfc_rotated_tile():
    t = Tile("minecraft:oak_log[axis=x]",
             edges=("a", "b", "c", "d", "e", "f"))
    r = t.rotated()
    # Rotation swaps +x/+z (indices 0,4) and -x/-z (1,5).
    assert r.edges == ("e", "f", "c", "d", "a", "b")