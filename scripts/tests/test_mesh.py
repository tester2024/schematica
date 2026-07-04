"""Unit tests for schematica.shapes.mesh (trimesh voxelization).

Skipped when trimesh is not installed.
"""
from __future__ import annotations

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from schematica.shapes.mesh import MeshShape, load_mesh  # noqa: E402


def _box_mesh(extents=(4.0, 4.0, 4.0)) -> trimesh.Trimesh:
    # trimesh.creation.box is centred at the origin; we offset it later via
    # MeshShape.origin so it lands inside the grid.
    return trimesh.creation.box(extents=extents)


def test_mesh_shape_mask_basic():
    m = _box_mesh((4.0, 4.0, 4.0))
    # Box is centred at origin (range -2..2); shift so it sits at 0..4.
    shape = MeshShape(mesh=m, origin=(2.0, 2.0, 2.0), scale=1.0)
    mask = shape.mask((8, 8, 8))
    assert mask.shape == (8, 8, 8)
    assert mask.dtype == bool
    assert mask.any()
    # Voxels should sit in the 0..4 range.
    coords = np.where(mask)
    assert coords[0].min() >= 0 and coords[0].max() <= 4
    # Outside the box.
    assert mask[7, 7, 7] == False  # noqa: E712


def test_mesh_shape_mask_origin_offset():
    m = _box_mesh((2.0, 2.0, 2.0))
    # Box spans world [-1, 1] + origin 5 -> world [4, 6] -> voxels 4..6.
    shape = MeshShape(mesh=m, origin=(5.0, 1.0, 1.0), scale=1.0)
    mask = shape.mask((8, 8, 8))
    coords = np.where(mask)
    assert coords[0].min() >= 4
    assert coords[0].max() <= 6


def test_mesh_shape_mask_entirely_outside_returns_zeros():
    m = _box_mesh((2.0, 2.0, 2.0))
    shape = MeshShape(mesh=m, origin=(100.0, 100.0, 100.0), scale=1.0)
    mask = shape.mask((8, 8, 8))
    assert mask.shape == (8, 8, 8)
    assert not mask.any()


def test_mesh_shape_mask_scale_grows_box():
    m = _box_mesh((2.0, 2.0, 2.0))
    # Box spans [-1, 1] * scale 2 -> [-2, 2] + origin 2 -> [0, 4].
    shape = MeshShape(mesh=m, origin=(2.0, 2.0, 2.0), scale=2.0)
    mask = shape.mask((8, 8, 8))
    assert mask.any()
    coords = np.where(mask)
    assert coords[0].min() >= 0
    assert coords[0].max() <= 4


def test_load_mesh_reads_obj(tmp_path):
    m = _box_mesh((3.0, 3.0, 3.0))
    obj_path = tmp_path / "box.obj"
    m.export(str(obj_path))
    loaded = load_mesh(str(obj_path), origin=(2.0, 2.0, 2.0))
    assert isinstance(loaded, MeshShape)
    mask = loaded.mask((8, 8, 8))
    assert mask.any()


def test_mesh_shape_does_not_mutate_input_mesh():
    m = _box_mesh((2.0, 2.0, 2.0))
    original_bounds = np.asarray(m.bounds).copy()
    shape = MeshShape(mesh=m, origin=(1.0, 1.0, 1.0), scale=2.0)
    _ = shape.mask((8, 8, 8))
    # The implementation copies the mesh; original must be unchanged.
    assert np.allclose(m.bounds, original_bounds)
