"""Tests for Block + BlockRegistry."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from schematica.blocks.block import AIR, Block


def test_block_parse_simple():
    assert Block.parse("minecraft:stone").name == "minecraft:stone"
    assert Block.parse("stone").name == "minecraft:stone"


def test_block_parse_states():
    b = Block.parse("minecraft:oak_log[axis=y]")
    assert b.name == "minecraft:oak_log"
    assert dict(b.states) == {"axis": "y"}


def_blockstate_roundtrip = [
    "minecraft:stone",
    "minecraft:oak_log[axis=y]",
    "minecraft:stairs[facing=north,half=top]",
    "minecraft:redstone_wire[east=up,west=none]",
]


@pytest.mark.parametrize("s", def_blockstate_roundtrip)
def test_blockstate_roundtrip(s):
    assert Block.parse(s).to_blockstate_str() == s


def test_block_bool_state():
    b = Block.parse("minecraft:powered_rail[powered=true]")
    assert dict(b.states)["powered"] is True
    assert b.to_blockstate_str() == "minecraft:powered_rail[powered=true]"


def test_block_immutable():
    b = Block(name="minecraft:stone")
    with pytest.raises(FrozenInstanceError):
        b.name = "minecraft:dirt"  # type: ignore[misc]


def test_air_singleton():
    assert AIR.name == "minecraft:air"
    assert AIR.to_blockstate_str() == "minecraft:air"


def test_registry_fallback_lookup():
    from schematica.blocks.registry import BlockRegistry
    reg = BlockRegistry.for_version("1.20.1")
    bd = reg["minecraft:stone"]
    assert bd.name == "minecraft:stone"
    assert bd.display_name == "Stone"
    assert "minecraft:stone" in reg
    assert "minecraft:nonexistent_xyz" not in reg


def test_registry_loads_prismarine_minecraft_data_shape(tmp_path):
    from schematica.blocks.registry import BlockRegistry

    version_dir = tmp_path / "data" / "pc" / "1.20.1"
    version_dir.mkdir(parents=True)
    (version_dir / "blocks.json").write_text(json.dumps([
        {"id": 0, "name": "air", "displayName": "Air"},
        {"id": 17, "name": "oak_log", "displayName": "Oak Log", "states": [
            {"name": "axis", "type": "enum", "values": ["x", "y", "z"], "default": "y"},
        ]},
        {"id": 200, "name": "test_bool", "displayName": "Test Bool", "states": [
            {"name": "powered", "type": "bool", "default": False},
        ]},
        {"id": 201, "name": "test_int", "displayName": "Test Int", "states": [
            {"name": "level", "type": "int", "values": [0, 1, 2], "default": 0},
        ]},
    ]), encoding="utf-8")

    reg = BlockRegistry.for_version("1.20.1", tmp_path)
    assert BlockRegistry.list_versions(tmp_path) == ["1.20.1"]
    assert reg["oak_log"].name == "minecraft:oak_log"
    assert reg.by_id(17).name == "minecraft:oak_log"
    assert reg.resolve(Block.parse("minecraft:oak_log")).to_blockstate_str() == "minecraft:oak_log[axis=y]"
    assert reg.resolve(Block.parse("minecraft:test_bool[powered=true]")).to_blockstate_str() == "minecraft:test_bool[powered=true]"
    assert reg.resolve(Block.parse("minecraft:test_int[level=2]")).to_blockstate_str() == "minecraft:test_int[level=2]"
    with pytest.raises(ValueError, match="axis"):
        reg.resolve(Block.parse("minecraft:oak_log[axis=q]"))
    with pytest.raises(ValueError, match="level"):
        reg.resolve(Block.parse("minecraft:test_int[level=9]"))


def test_registry_normalizes_unprefixed_catalog_names():
    from schematica.blocks.registry import BlockDef, BlockRegistry

    reg = BlockRegistry("1.8", [BlockDef(35, "wool", "Wool")])
    assert "wool" in reg
    assert "minecraft:wool" in reg
    assert reg["wool"].name == "minecraft:wool"
    assert reg["minecraft:wool"].name == "minecraft:wool"
    assert reg.all()[0].name == "minecraft:wool"


def test_registry_duplicate_ids_do_not_overwrite_fallback_lookup():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    assert reg.by_id(1).name == "minecraft:stone"
    assert reg.by_id(95).name == "minecraft:purple_stained_glass"
    assert reg.by_id(168).name == "minecraft:prismarine"
    assert reg.by_id(169).name == "minecraft:sea_lantern"
    assert reg.by_id(173).name == "minecraft:coal_block"
    ids = [b.id for b in reg.all()]
    assert len(ids) == len(set(ids))


def test_registry_fallback_includes_common_colored_blocks():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    assert "minecraft:red_wool" in reg
    assert "blue_stained_glass" in reg


def test_registry_fallback_includes_common_mapmaking_blocks():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    for name in (
        "minecraft:iron_block",
        "minecraft:gold_block",
        "minecraft:diamond_block",
        "minecraft:emerald_block",
        "minecraft:beacon",
        "minecraft:chest",
        "minecraft:ladder",
        "minecraft:oak_trapdoor",
        "minecraft:oak_slab",
        "minecraft:red_bed",
    ):
        assert name in reg


def test_registry_resolve_fills_defaults():
    from schematica.blocks.registry import BlockRegistry
    reg = BlockRegistry.for_version("1.20.1")
    b = Block.parse("minecraft:oak_log")
    r = reg.resolve(b)
    assert dict(r.states) == {"axis": "y"}


def test_registry_resolve_rejects_unknown_state():
    from schematica.blocks.registry import BlockRegistry
    reg = BlockRegistry.for_version("1.20.1")
    with pytest.raises(ValueError):
        reg.validate(Block.parse("minecraft:stone[foo=bar]"))


def test_registry_resolve_rejects_invalid_state_value():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    with pytest.raises(ValueError, match="axis"):
        reg.resolve(Block.parse("minecraft:oak_log[axis=bad]"))


def test_registry_resolve_rejects_states_on_stateless_blocks():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    with pytest.raises(ValueError, match="no known states"):
        reg.resolve(Block.parse("minecraft:stone[foo=bar]"))


def test_registry_resolve_preserves_and_fills_stateful_fallback_block():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    resolved = reg.resolve(Block.parse("minecraft:oak_stairs[facing=east]"))
    states = dict(resolved.states)
    assert states["facing"] == "east"
    assert states["half"] == "bottom"
    assert states["shape"] == "straight"
    assert states["waterlogged"] is False


def test_registry_resolve_rejects_bad_stateful_fallback_value():
    from schematica.blocks.registry import BlockRegistry

    reg = BlockRegistry.for_version("1.20.1")
    with pytest.raises(ValueError, match="facing"):
        reg.resolve(Block.parse("minecraft:oak_stairs[facing=nonsense]"))


def test_registry_search():
    from schematica.blocks.registry import BlockRegistry
    reg = BlockRegistry.for_version("1.20.1")
    hits = reg.search("oak")
    names = {h.name for h in hits}
    assert "minecraft:oak_log" in names
    assert "minecraft:oak_planks" in names
