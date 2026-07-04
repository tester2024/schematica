"""Direct unit tests for schematica.cli.validation check_* functions.

These call the validators directly (rather than via dispatch) so individual
error codes are pinned down independently of the dispatcher's error formatting.
"""
from __future__ import annotations

import pytest

from schematica.blocks.registry import BlockRegistry
from schematica.cli.validation import (
    CheckResult,
    check_add_arch,
    check_add_box,
    check_add_cone,
    check_add_cylinder,
    check_add_dome,
    check_add_ellipsoid,
    check_add_helix,
    check_add_line,
    check_add_plane,
    check_add_pyramid,
    check_add_sphere,
    check_add_spiral,
    check_add_staircase,
    check_add_torus,
    check_add_wedge,
    check_clone_cardinal,
    check_clone_translate,
    check_export,
    check_fill,
    check_generate_tree,
    check_generate_wfc,
    check_load,
    check_mirror,
    check_paint_box,
    check_paint_sphere,
    check_preview,
    check_replace,
    check_rotate,
    check_save,
    check_session_new,
    check_subtract_box,
    check_subtract_cylinder,
    check_subtract_dome,
    check_subtract_pyramid,
    check_subtract_sphere,
)
from schematica.session.session import Session


@pytest.fixture
def session() -> Session:
    return Session.new((16, 16, 16))


@pytest.fixture
def registry() -> BlockRegistry:
    return BlockRegistry.for_version("1.20.1")


def codes(results: list[CheckResult]) -> list[str]:
    return [r.code for r in results]


def errors(results: list[CheckResult]) -> list[str]:
    return [r.code for r in results if r.is_error]


# ---- CheckResult ----------------------------------------------------------

def test_check_result_is_error_property():
    assert CheckResult("error", "x", "y").is_error is True
    assert CheckResult("warn", "x", "y").is_error is False


# ---- check_session_new ----------------------------------------------------

def test_session_new_bad_size(registry):
    res = check_session_new("not-a-size", "1.20.1", registry)
    assert "bad_size" in errors(res)


def test_session_new_nonpositive(registry):
    res = check_session_new("0x4x4", "1.20.1", registry)
    assert "nonpositive_size" in errors(res)


def test_session_new_huge_warns(registry):
    res = check_session_new("600x4x4", "1.20.1", registry)
    assert "huge_size" in codes(res)
    assert "huge_size" not in errors(res)


def test_session_new_ok(registry):
    res = check_session_new("16x16x16", "1.20.1", registry)
    assert res == []


# ---- check_add_box --------------------------------------------------------

def test_add_box_inverted_bounds(session, registry):
    res = check_add_box("5,5,5", "0,0,0", "minecraft:stone", False, session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_box_bad_coords(session, registry):
    res = check_add_box("xyz", "0,0,0", "minecraft:stone", False, session, registry)
    assert "bad_coords" in errors(res)


def test_add_box_hollow_zero_warns(session, registry):
    res = check_add_box("0,0,0", "0,0,0", "minecraft:stone", True, session, registry)
    assert "hollow_zero" in codes(res)


def test_add_box_unknown_block(session, registry):
    res = check_add_box("0,0,0", "2,2,2", "minecraft:not_a_block", False, session, registry)
    assert "unknown_block" in errors(res)


def test_add_box_air_warns(session, registry):
    res = check_add_box("0,0,0", "2,2,2", "minecraft:air", False, session, registry)
    assert "add_air" in codes(res)


def test_add_box_outside(session, registry):
    res = check_add_box("100,0,0", "110,2,2", "minecraft:stone", False, session, registry)
    assert "out_of_bounds" in codes(res)


def test_add_box_partly_outside(session, registry):
    res = check_add_box("14,0,0", "20,2,2", "minecraft:stone", False, session, registry)
    assert "partly_out_of_bounds" in codes(res)


def test_add_box_ok(session, registry):
    res = check_add_box("0,0,0", "2,2,2", "minecraft:stone", False, session, registry)
    assert res == []


# ---- check_subtract_box ---------------------------------------------------

def test_subtract_box_inverted(session):
    res = check_subtract_box("5,5,5", "0,0,0", session)
    assert "inverted_bounds" in errors(res)


def test_subtract_box_outside(session):
    res = check_subtract_box("100,0,0", "110,2,2", session)
    assert "out_of_bounds" in codes(res)


# ---- check_add_sphere -----------------------------------------------------

def test_add_sphere_negative_radius(session, registry):
    res = check_add_sphere("8,8,8", -1, "minecraft:stone", False, session, registry)
    assert "negative_radius" in errors(res)


def test_add_sphere_zero_radius_warns(session, registry):
    res = check_add_sphere("8,8,8", 0, "minecraft:stone", False, session, registry)
    assert "zero_radius" in codes(res)


def test_add_sphere_hollow_tiny(session, registry):
    res = check_add_sphere("8,8,8", 0.5, "minecraft:stone", True, session, registry)
    assert "hollow_tiny" in codes(res)


def test_add_sphere_center_outside(session, registry):
    res = check_add_sphere("100,8,8", 3, "minecraft:stone", False, session, registry)
    assert "center_outside" in codes(res)


# ---- check_add_cylinder ---------------------------------------------------

def test_add_cylinder_negative_radius(session, registry):
    res = check_add_cylinder("8,8,8", -1, 4, "minecraft:stone", False, session, registry)
    assert "negative_radius" in errors(res)


def test_add_cylinder_nonpositive_height(session, registry):
    res = check_add_cylinder("8,8,8", 2, 0, "minecraft:stone", False, session, registry)
    assert "nonpositive_height" in errors(res)


# ---- check_add_dome -------------------------------------------------------

def test_add_dome_negative_radius(session, registry):
    res = check_add_dome("8,8,8", -1, "minecraft:stone", False, session, registry)
    assert "negative_radius" in errors(res)


# ---- check_add_helix ------------------------------------------------------

def test_add_helix_inverted_y(session, registry):
    res = check_add_helix("8,8,8", 2, 10, 4, 2.0, "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_helix_zero_turns(session, registry):
    res = check_add_helix("8,8,8", 2, 4, 10, 0, "minecraft:stone", session, registry)
    assert "zero_turns" in codes(res)


# ---- check_add_arch -------------------------------------------------------

def test_add_arch_negative_radius(session, registry):
    res = check_add_arch("8,8,8", 0, 4, -1, 1, "minecraft:stone", session, registry)
    assert "negative_radius" in errors(res)


def test_add_arch_inverted_z(session, registry):
    res = check_add_arch("8,8,8", 4, 0, 3, 1, "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_arch_zero_thickness(session, registry):
    res = check_add_arch("8,8,8", 0, 4, 3, 0, "minecraft:stone", session, registry)
    assert "zero_thickness" in codes(res)


# ---- check_add_staircase --------------------------------------------------

def test_add_staircase_bad_axis(session, registry):
    res = check_add_staircase("4,1,4", 12, 2, 1, 1, "y", "minecraft:oak_planks",
                              session, registry)
    assert "bad_axis" in errors(res)


def test_add_staircase_nonpositive_step(session, registry):
    res = check_add_staircase("4,1,4", 12, 0, 1, 1, "x", "minecraft:oak_planks",
                              session, registry)
    assert "nonpositive_step" in errors(res)


def test_add_staircase_inverted_y(session, registry):
    res = check_add_staircase("4,10,4", 8, 2, 1, 1, "x", "minecraft:oak_planks",
                              session, registry)
    assert "inverted_bounds" in errors(res)


# ---- check_subtract_sphere/cylinder/dome/pyramid --------------------------

def test_subtract_sphere_negative_radius(session):
    res = check_subtract_sphere("8,8,8", -1, session)
    assert "negative_radius" in errors(res)


def test_subtract_cylinder_nonpositive_height(session):
    res = check_subtract_cylinder("8,8,8", 2, 0, session)
    assert "nonpositive_height" in errors(res)


def test_subtract_dome_negative_radius(session):
    res = check_subtract_dome("8,8,8", -1, session)
    assert "negative_radius" in errors(res)


def test_subtract_pyramid_inverted_y(session):
    res = check_subtract_pyramid("8,8,8", 2, 10, 4, session)
    assert "inverted_bounds" in errors(res)


# ---- check_paint_box/sphere -----------------------------------------------

def test_paint_box_inverted(session, registry):
    res = check_paint_box("5,5,5", "0,0,0", "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_paint_sphere_negative_radius(session, registry):
    res = check_paint_sphere("8,8,8", -1, "minecraft:stone", session, registry)
    assert "negative_radius" in errors(res)


# ---- check_add_cone/ellipsoid/pyramid/torus -------------------------------

def test_add_cone_inverted_y(session, registry):
    res = check_add_cone("8,8,8", 3, 10, 4, "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_cone_negative_radius(session, registry):
    res = check_add_cone("8,8,8", -1, 4, 10, "minecraft:stone", session, registry)
    assert "negative_radius" in errors(res)


def test_add_ellipsoid_negative_radius(session, registry):
    res = check_add_ellipsoid("8,8,8", 0, 3, 3, "minecraft:stone", False,
                              session, registry)
    assert "negative_radius" in errors(res)


def test_add_pyramid_inverted_y(session, registry):
    res = check_add_pyramid("8,8,8", 2, 10, 4, "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_torus_inverted_radii_warns(session, registry):
    res = check_add_torus("8,8,8", R=2, r=5, block="minecraft:stone",
                          session=session, registry=registry)
    assert "torus_inverted_radii" in codes(res)


def test_add_torus_negative_major_radius(session, registry):
    res = check_add_torus("8,8,8", R=0, r=1, block="minecraft:stone",
                          session=session, registry=registry)
    assert "negative_radius" in errors(res)


# ---- check_add_line/wedge/spiral/plane ------------------------------------

def test_add_line_bad_coords(session, registry):
    res = check_add_line("xyz", "0,0,0", "minecraft:stone", session, registry)
    assert "bad_coords" in errors(res)


def test_add_wedge_inverted_bounds(session, registry):
    res = check_add_wedge("5,5,5", "0,0,0", "x", "minecraft:stone", session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_wedge_bad_axis(session, registry):
    res = check_add_wedge("0,0,0", "2,2,2", "y", "minecraft:stone", session, registry)
    assert "bad_axis" in errors(res)


def test_add_spiral_inverted_radii_warns(session, registry):
    res = check_add_spiral("8,8,8", 4, 2, 0, 10, 2.0, "minecraft:stone",
                           session, registry)
    assert "spiral_inverted_radii" in codes(res)


def test_add_spiral_inverted_y(session, registry):
    res = check_add_spiral("8,8,8", 1, 4, 10, 4, 2.0, "minecraft:stone",
                           session, registry)
    assert "inverted_bounds" in errors(res)


def test_add_plane_bad_axis(session, registry):
    res = check_add_plane("w", 0, 1, "minecraft:stone", session, registry)
    assert "bad_axis" in errors(res)


def test_add_plane_out_of_bounds(session, registry):
    res = check_add_plane("x", 100, 1, "minecraft:stone", session, registry)
    assert "out_of_bounds" in codes(res)


def test_add_plane_zero_thickness(session, registry):
    res = check_add_plane("x", 0, 0, "minecraft:stone", session, registry)
    assert "zero_thickness" in codes(res)


# ---- check_replace / check_fill -------------------------------------------

def test_replace_same_warns(registry):
    res = check_replace("minecraft:stone", "minecraft:stone", registry)
    assert "replace_same" in codes(res)


def test_replace_unknown_block(registry):
    res = check_replace("minecraft:not_a_block", "minecraft:dirt", registry)
    assert "unknown_block" in errors(res)


def test_fill_air_warns(registry):
    res = check_fill("minecraft:air", registry)
    assert "fill_air" in codes(res)


def test_fill_ok(registry):
    res = check_fill("minecraft:stone", registry)
    assert res == []


# ---- check_mirror / check_rotate ------------------------------------------

def test_mirror_bad_axis():
    res = check_mirror("w")
    assert "bad_axis" in errors(res)


def test_mirror_ok():
    assert check_mirror("x") == []


def test_rotate_bad_axes():
    res = check_rotate(1, "abc")
    assert "bad_axes" in errors(res)


def test_rotate_ok():
    assert check_rotate(1, "xz") == []


# ---- check_clone_translate / clone_cardinal -------------------------------

def test_clone_translate_zero_offset_warns(session):
    res = check_clone_translate("0,0,0", "2,2,2", "0,0,0", 2, session)
    assert "zero_offset" in codes(res)


def test_clone_translate_nonpositive_count(session):
    res = check_clone_translate("0,0,0", "2,2,2", "1,0,0", 0, session)
    assert "nonpositive_count" in errors(res)


def test_clone_translate_source_out_of_bounds(session):
    res = check_clone_translate("100,0,0", "102,2,2", "1,0,0", 2, session)
    assert "clone_source_out_of_bounds" in errors(res)


def test_clone_cardinal_bad_center(session):
    res = check_clone_cardinal("0,0,0", "2,2,2", "xyz", session)
    assert "bad_coords" in errors(res)


# ---- check_generate_tree / generate_wfc -----------------------------------

def test_generate_tree_out_of_bounds(session):
    res = check_generate_tree("100,1,1", 5, session)
    assert "out_of_bounds" in codes(res)


def test_generate_tree_nonpositive_height(session):
    res = check_generate_tree("8,1,1", 0, session)
    assert "nonpositive_height" in errors(res)


def test_generate_wfc_inverted_bounds(session):
    res = check_generate_wfc("5,5,5", "0,0,0", session)
    assert "inverted_bounds" in errors(res)


# ---- check_export / save / load / preview ---------------------------------

def test_export_empty_path():
    res = check_export("")
    assert "empty_path" in errors(res)


def test_export_bad_extension_warns():
    res = check_export("output.txt")
    assert "bad_extension" in codes(res)


def test_export_ok():
    res = check_export("out.schem")
    assert res == []


def test_save_empty_path():
    res = check_save("")
    assert "empty_path" in errors(res)


def test_save_ok():
    assert check_save("s.json") == []


def test_load_missing_file(tmp_path):
    res = check_load(str(tmp_path / "nope.json"))
    assert "missing_file" in errors(res)


def test_load_bad_extension_warns(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("{}", encoding="utf-8")
    res = check_load(str(p))
    assert "bad_extension" in codes(res)


def test_load_ok(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text("{}", encoding="utf-8")
    res = check_load(str(p))
    assert res == []


def test_preview_empty_outdir_warns():
    res = check_preview("")
    assert "empty_outdir" in codes(res)


def test_preview_ok():
    assert check_preview("out") == []


# ---- blockstate axis check ------------------------------------------------

def test_add_box_bad_axis_state(session, registry):
    res = check_add_box("0,0,0", "2,2,2", "minecraft:oak_log[axis=w]",
                        False, session, registry)
    assert "bad_state_value" in errors(res)
