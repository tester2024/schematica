"""Heightmap shape: a surface defined by a 2-D height array (or image).

The heightmap is laid over the (X, Z) plane; for each (x, z) it fills voxels
from y=0 up to height[x, z]. Useful for terrain and relief.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import coords_grid


@dataclass(frozen=True)
class Heightmap:
    heights: np.ndarray  # shape (sx, sz), int values
    y_base: int = 0
    solid_below: bool = True  # fill from y_base upward (True) or just a shell (False)

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return (0, self.y_base, 0, grid_shape[0] - 1, grid_shape[1] - 1, grid_shape[2] - 1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sx, sy, sz = shape
        h = np.asarray(self.heights)
        if h.shape != (sx, sz):
            raise ValueError(f"heights {h.shape} != ({sx},{sz})")
        X, Y, Z = coords_grid(shape)
        hmap = h[X, Z]  # (sx,sy,sz)
        target_y = self.y_base + hmap
        if self.solid_below:
            return np.asarray(Y < target_y)
        return np.asarray(Y == target_y)


def from_image(path: str, max_height: int = 64) -> Heightmap:
    from PIL import Image

    img = Image.open(path).convert("L")
    arr = np.asarray(img, dtype=np.float64)
    arr = (arr / 255.0) * max_height
    return Heightmap(heights=np.rint(arr).astype(np.int32))
