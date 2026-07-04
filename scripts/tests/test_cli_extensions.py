"""Tests for CLI generate.* commands, export.* variants, and Translated fix."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.session.session import Session


def test_dispatch_generate_terrain():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "generate.terrain seed=1 amplitude=4")
    assert "terrain" in res
    assert s.grid.nonempty_count() > 0


def test_dispatch_generate_tree():
    s = Session.new((16, 16, 16))
    res = dispatch(s, "generate.tree at=8,0,8 height=6")
    assert "tree" in res
    assert s.grid.nonempty_count() > 0


def test_dispatch_generate_wfc():
    s = Session.new((8, 8, 8))
    res = dispatch(
        s,
        "generate.wfc frm=0,0,0 to=3,0,3 "
        "blocks=minecraft:stone+minecraft:cobblestone+minecraft:dirt seed=1",
    )
    assert "wfc" in res
    # WFC should place at least one non-air block in the 4x1x4 region.
    assert s.grid.nonempty_count() > 0


def test_dispatch_export_mcedit(tmp_path):
    s = Session.new((4, 4, 4))
    dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    p = tmp_path / "out.schematic"
    res = dispatch(s, f"export.mcedit path={p.as_posix()}")
    assert "mcedit" in res
    assert p.exists()


def test_dispatch_export_litematic(tmp_path):
    s = Session.new((4, 4, 4))
    dispatch(s, "add.box frm=0,0,0 to=3,3,3 block=minecraft:stone")
    p = tmp_path / "out.litematic"
    res = dispatch(s, f"export.litematic path={p.as_posix()}")
    assert "litematic" in res
    assert p.exists()


def test_dispatch_clone_translate():
    s = Session.new((8, 4, 4))
    dispatch(s, "add.box frm=0,0,0 to=0,0,0 block=minecraft:stone")
    res = dispatch(s, "clone.translate frm=0,0,0 to=0,0,0 offset=2,0,0 count=3")
    assert "clone-translated 3" in res
    assert s.grid.get(2, 0, 0).name == "minecraft:stone"
    assert s.grid.get(4, 0, 0).name == "minecraft:stone"
    assert s.grid.get(6, 0, 0).name == "minecraft:stone"
    assert s.undo()
    assert s.grid.get(2, 0, 0).name == "minecraft:air"


def test_dispatch_clone_cardinal():
    s = Session.new((9, 2, 9))
    dispatch(s, "add.box frm=6,0,4 to=6,0,4 block=minecraft:stone")
    res = dispatch(s, "clone.cardinal frm=6,0,4 to=6,0,4 center=4,4")
    assert "clone-cardinal 3" in res
    for pos in ((4, 0, 6), (2, 0, 4), (4, 0, 2)):
        assert s.grid.get(*pos).name == "minecraft:stone"


def test_dispatch_clone_translate_rejects_out_of_bounds_source():
    s = Session.new((4, 4, 4))
    res = dispatch(s, "clone.translate frm=0,0,0 to=9,0,0 offset=1,0,0")
    assert "error" in res and "clone_source_out_of_bounds" in res


def test_translated_does_not_wrap_around():
    """Translated should clip to bounds, not roll voxels to the opposite edge."""
    from schematica.shapes.primitives import Box
    from schematica.shapes.transforms import Translated

    # Box at x in [0..3]; translate +dx=10 in a 8-wide grid -> nothing in-bounds.
    t = Translated(Box(0, 0, 0, 3, 3, 3), dx=10, dy=0, dz=0)
    m = t.mask((8, 8, 8))
    assert not m.any(), "translation beyond bounds should produce empty mask, not wrap"


def test_translated_partial_in_bounds():
    from schematica.shapes.primitives import Box
    from schematica.shapes.transforms import Translated

    # Box at x in [0..3]; translate dx=6 in 8-wide grid -> only x=6,7 in bounds.
    t = Translated(Box(0, 0, 0, 3, 3, 3), dx=6, dy=0, dz=0)
    m = t.mask((8, 8, 8))
    assert m[6, 0, 0] and m[7, 0, 0]
    assert not m[0, 0, 0]  # no wrap-around to the start


def test_translated_negative_offset():
    from schematica.shapes.primitives import Box
    from schematica.shapes.transforms import Translated

    # Box at x in [4..7]; translate dx=-4 -> x in [0..3] in-bounds.
    t = Translated(Box(4, 0, 0, 7, 3, 3), dx=-4, dy=0, dz=0)
    m = t.mask((8, 8, 8))
    assert m[0, 0, 0] and m[3, 0, 0]
    assert not m[4, 0, 0]
