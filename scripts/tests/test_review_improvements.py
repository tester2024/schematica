"""Tests for the review-driven improvements added in the second pass:

- NoiseDeformed broadcasting bug fix (asymmetric grids sz != sy)
- NoiseDeformed graceful scipy fallback
- Expanded fallback block registry (wood families + copper families)
- Radial / quad symmetry (enable_radial_symmetry, enable_quad_symmetry)
- minecraft-data downloader utility (mocked)
- New WFC presets (medieval_tower, modern_office, nether_fortress,
  cherry_grove, ocean_floor, tileset_by_name)
"""
from __future__ import annotations

import numpy as np
import pytest

from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere

# ---- NoiseDeformed broadcasting fix --------------------------------------

def test_noise_deformed_asymmetric_grid_does_not_crash():
    """The original bug: perlin2d((sz, sy)) repeated to (sx, sz, sy) instead
    of (sx, sy, sz), crashing with a broadcast ValueError on asymmetric grids.
    """
    from schematica.shapes.transforms import NoiseDeformed

    # sz=128, sy=64 — asymmetric, the exact shape from the bug report.
    shape = NoiseDeformed(Sphere(64, 32, 64, 10), amplitude=2, scale=0.1, seed=1)
    mask = shape.mask((128, 64, 128))
    assert mask.shape == (128, 64, 128)
    assert mask.dtype == bool


def test_noise_deformed_amplitude_zero_returns_base():
    from schematica.shapes.transforms import NoiseDeformed

    base = Sphere(8, 8, 8, 3).mask((16, 16, 16))
    out = NoiseDeformed(Sphere(8, 8, 8, 3), amplitude=0).mask((16, 16, 16))
    assert np.array_equal(out, base)


def test_noise_deformed_scipy_fallback_uses_numpy_when_scipy_missing(monkeypatch):
    """If scipy import fails, NoiseDeformed must still produce a valid mask
    via the numpy-only erosion/dilation fallback."""
    from schematica.shapes import transforms as transforms_mod

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            raise ImportError(f"no {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    out = transforms_mod.NoiseDeformed(Sphere(8, 8, 8, 3), amplitude=2, seed=1).mask((16, 16, 16))
    assert out.shape == (16, 16, 16)
    assert out.dtype == bool


# ---- Expanded fallback block registry -------------------------------------

@pytest.fixture
def fallback_registry():
    from schematica.blocks.registry import BlockRegistry
    # Use a non-existent data root to force the fallback catalog.
    return BlockRegistry.for_version("1.99.99-nodata")


@pytest.mark.parametrize("name", [
    "minecraft:spruce_fence", "minecraft:birch_fence_gate",
    "minecraft:jungle_stairs", "minecraft:acacia_slab",
    "minecraft:dark_oak_trapdoor", "minecraft:mangrove_door",
    "minecraft:cherry_sign", "minecraft:bamboo_pressure_plate",
    "minecraft:crimson_fence", "minecraft:warped_stairs",
])
def test_wood_family_present(fallback_registry, name):
    assert name in fallback_registry, f"{name} missing from fallback registry"


@pytest.mark.parametrize("name", [
    "minecraft:copper_block", "minecraft:exposed_copper",
    "minecraft:weathered_copper", "minecraft:oxidized_copper",
    "minecraft:cut_copper", "minecraft:exposed_cut_copper",
    "minecraft:cut_copper_slab", "minecraft:cut_copper_stairs",
    "minecraft:waxed_copper_block", "minecraft:waxed_cut_copper_stairs",
    "minecraft:raw_copper_block", "minecraft:chiseled_copper",
    "minecraft:copper_bulb",
])
def test_copper_families_present(fallback_registry, name):
    assert name in fallback_registry, f"{name} missing from fallback registry"


def test_copper_stairs_have_stairs_states(fallback_registry):
    bd = fallback_registry["minecraft:cut_copper_stairs"]
    state_names = {s.name for s in bd.states}
    assert {"facing", "half", "shape"} <= state_names


def test_wood_fence_has_fence_states(fallback_registry):
    bd = fallback_registry["minecraft:spruce_fence"]
    state_names = {s.name for s in bd.states}
    assert {"north", "east", "south", "west"} <= state_names


def test_fallback_registry_resolves_wood_block(fallback_registry):
    block = fallback_registry.resolve(
        fallback_registry["minecraft:birch_fence_gate"].default_block()
    )
    assert block.name == "minecraft:birch_fence_gate"


# ---- Radial / quad symmetry -----------------------------------------------

def test_enable_quad_symmetry_produces_4_fold_rotation():
    s = Session.new((16, 8, 16))
    s.enable_quad_symmetry(center=(7.5, 7.5))
    s.add(Box(0, 0, 7, 3, 4, 9), "minecraft:stone")
    data = s.grid.data
    coords = set(zip(*np.where(data != 0), strict=False))

    def rot90_xz(p):
        x, y, z = p
        return (int(round(15 - z)), y, int(round(x)))

    rotated = {rot90_xz(p) for p in coords}
    assert rotated == coords, "build is not invariant under 90-degree rotation"
    s.disable_symmetry()
    assert not s.symmetry_active


def test_enable_radial_symmetry_8_fold():
    s = Session.new((16, 16, 16))
    s.enable_radial_symmetry(folds=8, plane="xz")
    s.add(Box(7, 0, 7, 8, 4, 8), "minecraft:stone")  # 1-voxel column at center
    data = s.grid.data
    # All 8 rotations should overlap at the center column; non-empty.
    assert (data != 0).sum() > 0


def test_radial_symmetry_rejects_bad_plane():
    s = Session.new((16, 16, 16))
    with pytest.raises(ValueError, match="plane"):
        s.enable_radial_symmetry(folds=4, plane="abc")


def test_radial_symmetry_rejects_low_folds():
    s = Session.new((16, 16, 16))
    with pytest.raises(ValueError, match="folds"):
        s.enable_radial_symmetry(folds=1)


def test_mirror_symmetry_still_works_after_schema_change():
    s = Session.new((16, 8, 16))
    s.enable_symmetry("x")
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:stone")
    # Mirror about x=7.5 maps x=0..3 to x=12..15.
    assert s.grid.data[1, 1, 1] != 0
    assert s.grid.data[14, 1, 1] != 0
    s.disable_symmetry()


def test_radial_symmetry_with_offset_center():
    s = Session.new((16, 8, 16))
    # Center offset from grid middle.
    s.enable_radial_symmetry(folds=4, plane="xz", center=(4.0, 4.0))
    s.add(Box(2, 0, 2, 3, 4, 3), "minecraft:stone")
    # Should be 4-fold symmetric about (4, 4) in xz.
    data = s.grid.data
    coords = set(zip(*np.where(data != 0), strict=False))

    def rot90_about(p, cx, cz):
        x, y, z = p
        dx, dz = x - cx, z - cz
        # 90-degree rotation: (dx, dz) -> (-dz, dx)
        return (int(round(cx - dz)), y, int(round(cz + dx)))

    rotated = {rot90_about(p, 4.0, 4.0) for p in coords}
    assert rotated == coords


# ---- WFC presets ----------------------------------------------------------

@pytest.mark.parametrize("name", [
    "mossy_ruins", "medieval_tower", "modern_office", "nether_fortress",
    "cherry_grove", "ocean_floor",
])
def test_tileset_by_name_returns_nonempty(name):
    from schematica.generators.wfc import tileset_by_name
    ts = tileset_by_name(name)
    assert len(ts) >= 3


def test_tileset_by_name_unknown_raises():
    from schematica.generators.wfc import tileset_by_name
    with pytest.raises(KeyError, match="unknown WFC tileset"):
        tileset_by_name("does_not_exist")


def test_tilesets_registry_lists_all_presets():
    from schematica.generators.wfc import TILESETS
    assert set(TILESETS) == {
        "mossy_ruins", "medieval_tower", "modern_office",
        "nether_fortress", "cherry_grove", "ocean_floor",
    }


def test_run_wfc_with_modern_office_collapses():
    from schematica.generators.wfc import run_wfc, tileset_by_name
    out = run_wfc((4, 4, 2), tileset_by_name("modern_office"), seed=42)
    assert out.shape == (4, 4, 2)
    # Every cell should be a non-empty block string.
    for x in range(4):
        for y in range(4):
            for z in range(2):
                assert isinstance(out[x, y, z], str)
                assert out[x, y, z].startswith("minecraft:")


def test_medieval_tower_contains_oak_and_stone():
    from schematica.generators.wfc import tileset_by_name
    blocks = {t.block for t in tileset_by_name("medieval_tower").tiles}
    assert "minecraft:stone_bricks" in blocks
    assert "minecraft:oak_planks" in blocks


def test_nether_fortress_contains_nether_bricks():
    from schematica.generators.wfc import tileset_by_name
    blocks = {t.block for t in tileset_by_name("nether_fortress").tiles}
    assert "minecraft:nether_bricks" in blocks
    assert "minecraft:lava" in blocks


def test_cherry_grove_contains_cherry_planks():
    from schematica.generators.wfc import tileset_by_name
    blocks = {t.block for t in tileset_by_name("cherry_grove").tiles}
    assert "minecraft:cherry_planks" in blocks


def test_ocean_floor_contains_prismarine():
    from schematica.generators.wfc import tileset_by_name
    blocks = {t.block for t in tileset_by_name("ocean_floor").tiles}
    assert "minecraft:prismarine" in blocks
    assert "minecraft:sea_lantern" in blocks


# ---- download utility (mocked, no network) --------------------------------

def test_is_version_cached_false(tmp_path):
    from schematica.blocks.download import is_version_cached
    assert is_version_cached("1.20.1", cache_root=tmp_path) is False


def test_download_version_writes_blocks_json(tmp_path):
    from schematica.blocks import download as dl

    def fake_get(url, timeout=30.0):
        if url.endswith("blocks.json"):
            return b'[{"id":1,"name":"minecraft:stone","displayName":"Stone"}]'
        return b'{"minecraftVersion":"1.20.1"}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dl, "_http_get", fake_get)
        out = dl.download_version("1.20.1", cache_root=tmp_path)
    assert (out / "blocks.json").exists()
    import json
    data = json.loads((out / "blocks.json").read_text(encoding="utf-8"))
    assert data[0]["name"] == "minecraft:stone"
