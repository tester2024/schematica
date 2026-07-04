"""Unit tests for schematica.shapes.heightmap."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.shapes.heightmap import Heightmap


def test_heightmap_solid_below_fills_column():
    heights = np.array([[3, 5], [2, 4]], dtype=np.int32)
    hm = Heightmap(heights=heights, y_base=0, solid_below=True)
    mask = hm.mask((2, 8, 2))
    assert mask.shape == (2, 8, 2)
    # column (0,0) height 3 -> voxels y=0..2 are True, y>=3 False
    assert mask[0, 0, 0] == True  # noqa: E712
    assert mask[0, 1, 0] == True  # noqa: E712
    assert mask[0, 2, 0] == True  # noqa: E712
    assert mask[0, 3, 0] == False  # noqa: E712
    # column (0,1) height 5 -> y=0..4 True
    assert mask[0, 4, 1] == True  # noqa: E712
    assert mask[0, 5, 1] == False  # noqa: E712


def test_heightmap_shell_only_surface():
    heights = np.array([[3, 5], [2, 4]], dtype=np.int32)
    hm = Heightmap(heights=heights, y_base=0, solid_below=False)
    mask = hm.mask((2, 8, 2))
    # Only y == height is True.
    assert mask[0, 3, 0] == True  # noqa: E712
    assert mask[0, 2, 0] == False  # noqa: E712
    assert mask[0, 0, 1] == False  # noqa: E712
    assert mask[0, 5, 1] == True  # noqa: E712


def test_heightmap_y_base_offset():
    heights = np.array([[2]], dtype=np.int32)
    hm = Heightmap(heights=heights, y_base=3, solid_below=True)
    mask = hm.mask((1, 8, 1))
    # target_y = y_base + height = 3 + 2 = 5; mask is Y < 5, so y=0..4 are True.
    assert mask[0, 3, 0] == True  # noqa: E712
    assert mask[0, 4, 0] == True  # noqa: E712
    assert mask[0, 5, 0] == False  # noqa: E712
    assert mask[0, 0, 0] == True  # noqa: E712 (y=0 is below the curve)


def test_heightmap_wrong_shape_raises():
    heights = np.array([[1, 2, 3]], dtype=np.int32)  # (1, 3) but grid is (1, 4, 2)
    hm = Heightmap(heights=heights)
    with pytest.raises(ValueError, match="heights"):
        hm.mask((1, 4, 2))


def test_heightmap_bounds():
    heights = np.zeros((2, 2), dtype=np.int32)
    hm = Heightmap(heights=heights, y_base=1)
    b = hm.bounds((4, 8, 4))
    assert b == (0, 1, 0, 3, 7, 3)


def test_heightmap_from_image(tmp_path):
    from PIL import Image

    # Build a 4x4 grayscale gradient 0..255.
    arr = np.array([[0, 64, 128, 255]], dtype=np.uint8).repeat(4, axis=0)
    img = Image.fromarray(arr, mode="L")
    p = tmp_path / "h.png"
    img.save(p)

    from schematica.shapes.heightmap import from_image

    hm = from_image(str(p), max_height=10)
    assert hm.heights.shape == (4, 4)
    # First column is 0, last column ~10.
    assert int(hm.heights[0, 0]) == 0
    assert int(hm.heights[0, 3]) == 10
    # Mid column ~2.5 -> rounded to 2 or 3.
    assert int(hm.heights[0, 1]) in (2, 3)
