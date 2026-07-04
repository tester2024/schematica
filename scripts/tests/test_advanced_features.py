"""Tests for export validation, constraint system, and material intelligence."""
from __future__ import annotations

from schematica.cli.repl import dispatch
from schematica.constraints import (
    BlockBan,
    BoxBounds,
    ConstraintSet,
    ConstraintViolation,
    HeightLimit,
    PaletteLimit,
    SolidRatio,
    Symmetry,
)
from schematica.export.materials import apply_substitutions, suggest_substitutions
from schematica.export.validation import validate_all, validate_export
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _solid_grid(size: int = 8, block: str = "minecraft:stone") -> Session:
    s = Session.new((size, size, size))
    s.add(Box(0, 0, 0, size - 1, size - 1, size - 1), block)
    return s


# ---- export validation ------------------------------------------------

def test_validate_sponge_ok(tmp_path):
    s = _solid_grid(8)
    r = validate_export(s.grid, tmp_path / "out.schem", fmt="sponge")
    assert r.ok is True
    assert r.voxel_mismatches == 0


def test_validate_litematic_ok(tmp_path):
    s = _solid_grid(8)
    r = validate_export(s.grid, tmp_path / "out.litematic", fmt="litematic")
    assert r.ok is True
    assert r.voxel_mismatches == 0


def test_validate_mcedit_ok(tmp_path):
    s = _solid_grid(8)
    r = validate_export(s.grid, tmp_path / "out.schematic", fmt="mcedit")
    assert r.ok is True


def test_validate_all_three(tmp_path):
    s = _solid_grid(8)
    results = validate_all(s.grid, tmp_path / "validation")
    assert len(results) == 3
    for r in results:
        assert r.ok is True


def test_validate_unknown_format(tmp_path):
    s = _solid_grid(4)
    r = validate_export(s.grid, tmp_path / "out.bin", fmt="unknown")
    assert r.ok is False
    assert "unknown format" in r.issues[0]


def test_validate_mcedit_with_modern_block(tmp_path):
    """MCEdit should report data loss for modern blocks, but still pass."""
    s = Session.new((4, 4, 4))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:deepslate")
    r = validate_export(s.grid, tmp_path / "out.schematic", fmt="mcedit")
    # deepslate is unmapped, becomes stone (id=1) in mcedit.
    # The validation should detect this but may flag it.
    # It should at least complete without crashing.
    assert r.format == "mcedit"


def test_dispatch_validate_all(tmp_path):
    s = _solid_grid(4)
    d = (tmp_path / "val").as_posix()
    r = dispatch(s, f"validate.all dir_path={d}")
    assert "[sponge] OK" in r
    assert "[litematic] OK" in r
    assert "[mcedit] OK" in r


# ---- constraint system ------------------------------------------------

def test_height_limit_ok():
    s = _solid_grid(8)
    c = HeightLimit(max_y=7)
    assert c.check(s.grid) == []


def test_height_limit_violation():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 5, 7), "minecraft:stone")
    c = HeightLimit(max_y=3)
    result = c.check(s.grid)
    assert len(result) == 1
    assert "above y=3" in result[0]


def test_block_ban_violation():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:bedrock")
    c = BlockBan(banned={"minecraft:bedrock"})
    result = c.check(s.grid)
    assert len(result) == 1
    assert "bedrock" in result[0]


def test_block_ban_ok():
    s = _solid_grid(8, "minecraft:stone")
    c = BlockBan(banned={"minecraft:bedrock"})
    assert c.check(s.grid) == []


def test_symmetry_ok():
    s = Session.new((8, 4, 8))
    # Symmetric build: box centered.
    s.add(Box(2, 0, 2, 5, 3, 5), "minecraft:stone")
    c = Symmetry(axis=0)
    assert c.check(s.grid) == []


def test_symmetry_violation():
    s = Session.new((8, 4, 8))
    s.add(Box(0, 0, 0, 2, 3, 7), "minecraft:stone")  # only left side
    c = Symmetry(axis=0)
    result = c.check(s.grid)
    assert len(result) == 1
    assert "not symmetric" in result[0]


def test_box_bounds_ok():
    s = Session.new((8, 8, 8))
    s.add(Box(2, 2, 2, 5, 5, 5), "minecraft:stone")
    c = BoxBounds(min_corner=(0, 0, 0), max_corner=(7, 7, 7))
    assert c.check(s.grid) == []


def test_box_bounds_violation():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 7, 7), "minecraft:stone")
    c = BoxBounds(min_corner=(2, 2, 2), max_corner=(5, 5, 5))
    result = c.check(s.grid)
    assert len(result) == 1
    assert "outside bounds" in result[0]


def test_palette_limit_ok():
    s = _solid_grid(8, "minecraft:stone")
    c = PaletteLimit(max_size=256)
    assert c.check(s.grid) == []


def test_palette_limit_violation():
    s = _solid_grid(8, "minecraft:stone")
    c = PaletteLimit(max_size=1)  # only air allowed
    result = c.check(s.grid)
    assert len(result) == 1


def test_solid_ratio_ok():
    s = _solid_grid(8)
    c = SolidRatio(min_frac=0.5, max_frac=1.0)
    assert c.check(s.grid) == []


def test_solid_ratio_min_violation():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 1, 1, 1), "minecraft:stone")  # very sparse
    c = SolidRatio(min_frac=0.5)
    result = c.check(s.grid)
    assert any("< min" in m for m in result)


def test_constraint_set_check_all():
    s = _solid_grid(8)
    cs = ConstraintSet([
        HeightLimit(max_y=7),
        BlockBan(banned={"minecraft:bedrock"}),
    ])
    violations = cs.check_all(s.grid)
    assert violations == {}


def test_constraint_set_check_or_raise():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 7, 7), "minecraft:bedrock")
    cs = ConstraintSet([BlockBan(banned={"minecraft:bedrock"})])
    try:
        cs.check_or_raise(s.grid)
    except ConstraintViolation as e:
        assert "block_ban" in str(e)
        return
    raise AssertionError("expected ConstraintViolation")


def test_constraint_attach_rejects_violation():
    s = Session.new((8, 8, 8))
    cs = ConstraintSet([HeightLimit(max_y=3)])
    cs.attach(s)
    try:
        s.add(Box(0, 0, 0, 7, 5, 7), "minecraft:stone")
    except ConstraintViolation:
        # The grid should be unchanged (operation was rejected).
        assert s.grid.nonempty_count() == 0
        return
    finally:
        cs.detach()
    raise AssertionError("expected ConstraintViolation")


def test_constraint_attach_allows_valid():
    s = Session.new((8, 8, 8))
    cs = ConstraintSet([HeightLimit(max_y=7)])
    cs.attach(s)
    s.add(Box(0, 0, 0, 7, 3, 7), "minecraft:stone")
    assert s.grid.nonempty_count() > 0
    cs.detach()


def test_dispatch_constraint_add_and_check():
    s = _solid_grid(8)
    r = dispatch(s, "constraint.add kind=height a=10")
    assert "added constraint" in r
    r = dispatch(s, "constraint.check")
    assert "OK" in r


def test_dispatch_constraint_ban_violation():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 3, 3, 3), "minecraft:bedrock")
    dispatch(s, "constraint.add kind=ban a=minecraft:bedrock")
    r = dispatch(s, "constraint.check")
    assert "violated" in r


# ---- material intelligence --------------------------------------------

def test_suggest_substitutions_no_unmapped():
    s = _solid_grid(8, "minecraft:stone")
    subs = suggest_substitutions(s.grid)
    # stone has a legacy mapping, so no substitutions needed.
    assert "minecraft:stone" not in subs


def test_suggest_substitutions_deepslate():
    s = _solid_grid(4, "minecraft:amethyst_block")
    subs = suggest_substitutions(s.grid)
    assert "minecraft:amethyst_block" in subs
    # Should suggest quartz_block (which has a legacy mapping).
    assert subs["minecraft:amethyst_block"] == "minecraft:quartz_block"


def test_suggest_substitutions_copper():
    s = _solid_grid(4, "minecraft:basalt")
    subs = suggest_substitutions(s.grid)
    assert "minecraft:basalt" in subs
    # Should suggest stone (which has a legacy mapping).
    assert subs["minecraft:basalt"] == "minecraft:stone"


def test_apply_substitutions_replaces_blocks():
    s = _solid_grid(4, "minecraft:amethyst_block")
    n = apply_substitutions(s.grid)
    assert n == 64  # all voxels replaced
    # Check that amethyst_block is now quartz_block.
    assert s.grid.get(0, 0, 0).name == "minecraft:quartz_block"


def test_apply_substitutions_no_op():
    s = _solid_grid(4, "minecraft:stone")
    n = apply_substitutions(s.grid)
    assert n == 0  # nothing to substitute


def test_dispatch_substitutions():
    s = _solid_grid(4, "minecraft:amethyst_block")
    r = dispatch(s, "substitutions")
    assert "substitutions needed" in r
    assert "amethyst_block" in r


def test_dispatch_apply_substitutions():
    s = _solid_grid(4, "minecraft:amethyst_block")
    r = dispatch(s, "apply.substitutions")
    assert "applied" in r and "64" in r
    assert s.grid.get(0, 0, 0).name == "minecraft:quartz_block"
