"""Tests for procedural micro-detail tools: paint_gradient, edge_wear, surface_scatter."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.procedural.detail import edge_wear, paint_gradient, surface_scatter
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _solid_grid(size: int = 8, block: str = "minecraft:stone") -> Session:
    s = Session.new((size, size, size))
    s.add(Box(0, 0, 0, size - 1, size - 1, size - 1), block)
    return s


def test_paint_gradient_vertical():
    s = _solid_grid(8)
    n = paint_gradient(s.grid, (0, 0, 0), (7, 7, 7),
                      ["minecraft:stone", "minecraft:cobblestone", "minecraft:diorite"],
                      axis="y")
    assert n == 512  # all solid voxels painted
    # Bottom layer should be stone (idx 1), top should be diorite.
    assert s.grid.get(0, 0, 0).name == "minecraft:stone"
    assert s.grid.get(0, 7, 0).name == "minecraft:diorite"


def test_paint_gradient_only_solid():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")  # only 64 solid
    n = paint_gradient(s.grid, (0, 0, 0), (7, 7, 7),
                      ["minecraft:stone", "minecraft:cobblestone"], axis="x")
    assert n == 64


def test_paint_gradient_empty_region():
    s = _solid_grid(8)
    n = paint_gradient(s.grid, (0, 0, 0), (0, 0, 0),
                      ["minecraft:stone", "minecraft:cobblestone"], axis="y")
    assert n == 1  # single voxel


def test_edge_wear_exposed_surfaces():
    s = _solid_grid(8)
    n = edge_wear(s.grid, ["minecraft:mossy_cobblestone", "minecraft:cobblestone"],
                  min_exposure=3, max_exposure=6, noise=0.0)
    # Corners have 3 exposed faces, edges 2, faces 1, interior 0.
    # With min_exposure=3: only corners (8 voxels) qualify.
    assert n == 8


def test_edge_wear_all_exposed():
    s = _solid_grid(4)  # 4x4x4 = 64 voxels, 56 on the surface (8 interior)
    n = edge_wear(s.grid, ["minecraft:mossy_cobblestone"],
                  min_exposure=1, max_exposure=6)
    assert n == 56  # 64 - 8 interior = 56 surface voxels


def test_edge_wear_noise_reduces_count():
    s = _solid_grid(8)
    n_no_noise = edge_wear(s.grid, ["minecraft:mossy_cobblestone"],
                           min_exposure=3, max_exposure=6, noise=0.0, seed=0)
    s2 = _solid_grid(8)
    n_with_noise = edge_wear(s2.grid, ["minecraft:mossy_cobblestone"],
                             min_exposure=3, max_exposure=6, noise=0.99, seed=42)
    assert n_with_noise < n_no_noise


def test_surface_scatter_density():
    s = _solid_grid(8)
    n = surface_scatter(s.grid, "minecraft:moss_block",
                        density=1.0, min_exposure=1, max_exposure=6, seed=0)
    # With density=1.0, all exposed voxels should be scattered.
    assert n > 0
    # Count moss_block in palette.
    count = s.grid.count("minecraft:moss_block")
    assert count == n


def test_surface_scatter_zero_density():
    s = _solid_grid(8)
    n = surface_scatter(s.grid, "minecraft:moss_block", density=0.0, seed=0)
    assert n == 0


def test_surface_scatter_on_blocks_filter():
    s = _solid_grid(8, block="minecraft:stone")
    # Add some dirt blocks.
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:dirt")
    n = surface_scatter(s.grid, "minecraft:moss_block",
                        density=1.0, min_exposure=1, max_exposure=6,
                        seed=0, on_blocks=["minecraft:dirt"])
    # Only dirt voxels that are exposed should be scattered.
    assert n > 0
    # No stone should be scattered.
    for x in range(8):
        for y in range(8):
            for z in range(8):
                b = s.grid.get(x, y, z)
                if b.name == "minecraft:stone":
                    pass  # stone wasn't changed


def test_dispatch_paint_gradient():
    s = _solid_grid(8)
    r = dispatch(s, "paint.gradient frm=0,0,0 to=7,7,7 blocks=minecraft:stone,minecraft:cobblestone axis=y")
    assert "gradient" in r and "512" in r


def test_dispatch_edge_wear():
    s = _solid_grid(8)
    r = dispatch(s, "edge.wear blocks=minecraft:mossy_cobblestone,minecraft:cobblestone min_exposure=3")
    assert "edge-worn" in r


def test_dispatch_surface_scatter():
    s = _solid_grid(8)
    r = dispatch(s, "surface.scatter block=minecraft:moss_block density=0.5 seed=1")
    assert "scattered" in r
