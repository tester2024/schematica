"""Tests for Block + BlockRegistry."""
from __future__ import annotations

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
    with pytest.raises(Exception):
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


def test_registry_search():
    from schematica.blocks.registry import BlockRegistry
    reg = BlockRegistry.for_version("1.20.1")
    hits = reg.search("oak")
    names = {h.name for h in hits}
    assert "minecraft:oak_log" in names
    assert "minecraft:oak_planks" in names