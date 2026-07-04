"""Tests for WorldEdit-style h-prefix hollow shortcuts."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def test_hbox_is_hollow():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.hbox frm=2,2,2 to=10,10,10 block=minecraft:stone")
    # hollow 9x9x9 shell: 9^3 - 7^3 = 729 - 343 = 386
    assert s.grid.nonempty_count() == 386
    # interior should be air
    assert s.grid.get(6, 6, 6).name == "minecraft:air"
    # wall should be stone
    assert s.grid.get(2, 2, 2).name == "minecraft:stone"


def test_hsphere_is_hollow():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.hsphere center=8,8,8 r=4 block=minecraft:glass")
    filled_count = s.grid.nonempty_count()
    # hollow sphere should have fewer voxels than solid
    s2 = Session.new((16, 16, 16))
    dispatch(s2, "add.sphere center=8,8,8 r=4 block=minecraft:glass")
    assert filled_count < s2.grid.nonempty_count()
    # center should be air
    assert s.grid.get(8, 8, 8).name == "minecraft:air"


def test_hcylinder_is_hollow():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.hcylinder center=8,1,8 r=3 h=6 block=minecraft:bricks")
    filled_count = s.grid.nonempty_count()
    s2 = Session.new((16, 16, 16))
    dispatch(s2, "add.cylinder center=8,1,8 r=3 h=6 block=minecraft:bricks")
    assert filled_count < s2.grid.nonempty_count()


def test_hdome_is_hollow():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.hdome center=8,8,8 r=4 block=minecraft:obsidian")
    filled_count = s.grid.nonempty_count()
    s2 = Session.new((16, 16, 16))
    dispatch(s2, "add.dome center=8,8,8 r=4 block=minecraft:obsidian")
    assert filled_count < s2.grid.nonempty_count()


def test_hellipsoid_is_hollow():
    s = Session.new((16, 16, 16))
    dispatch(s, "add.hellipsoid center=8,8,8 rx=4 ry=3 rz=4 block=minecraft:quartz_block")
    filled_count = s.grid.nonempty_count()
    s2 = Session.new((16, 16, 16))
    dispatch(s2, "add.ellipsoid center=8,8,8 rx=4 ry=3 rz=4 block=minecraft:quartz_block")
    assert filled_count < s2.grid.nonempty_count()


def test_hprefix_commands_in_table():
    from schematica.session.commands import COMMANDS
    assert "add.hbox" in COMMANDS
    assert "add.hsphere" in COMMANDS
    assert "add.hcylinder" in COMMANDS
    assert "add.hdome" in COMMANDS
    assert "add.hellipsoid" in COMMANDS


def test_hsphere_negative_radius_error():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.hsphere center=8,8,8 r=-3 block=minecraft:glass")
    assert "error" in res and "negative_radius" in res


def test_hcylinder_zero_height_error():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "add.hcylinder center=8,1,8 r=2 h=0 block=minecraft:bricks")
    assert "error" in res and "nonpositive_height" in res
