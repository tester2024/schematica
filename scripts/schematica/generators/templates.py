"""Procedural generators that emit shapes / apply to a Session."""
from __future__ import annotations

import numpy as np

from ..session.session import Session
from ..shapes.heightmap import Heightmap
from .noise import perlin2d


def terrain_heightmap(shape: tuple[int, int, int], *, seed: int = 0,
                      base_height: int | None = None,
                      amplitude: int = 8, scale: float = 0.06) -> Heightmap:
    sx, sy, sz = shape
    base = base_height if base_height is not None else sy // 2
    n = perlin2d((sx, sz), scale=scale, seed=seed)
    heights = np.rint(base + (n - 0.5) * 2 * amplitude).astype(np.int32)
    return Heightmap(heights=heights, y_base=0, solid_below=True)


def apply_terrain(session: Session, *, seed: int = 0, amplitude: int = 8,
                  scale: float = 0.06,
                  top: str = "minecraft:grass_block",
                  filler: str = "minecraft:dirt",
                  bedrock: str = "minecraft:bedrock") -> None:
    hm = terrain_heightmap(session.grid.shape, seed=seed, amplitude=amplitude, scale=scale)
    session.add(hm, filler)
    # paint top layer
    X, _, Z = np.meshgrid(np.arange(session.grid.shape[0]),
                          np.arange(session.grid.shape[1]),
                          np.arange(session.grid.shape[2]), indexing="ij")
    h = hm.heights
    top_mask = (_y_grid(session.grid.shape) == (h[X, Z] - 1))

    class _TopLayer:
        def mask(self, shp: tuple[int, int, int]) -> np.ndarray:
            return np.asarray(top_mask)
    session.paint(_TopLayer(), top)


def _y_grid(shape: tuple[int, int, int]) -> np.ndarray:
    return np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), np.arange(shape[2]), indexing="ij")[1]


def apply_tree(session: Session, *, x: int, z: int, height: int = 6,
                trunk: str = "minecraft:oak_log",
                leaves: str = "minecraft:oak_leaves") -> None:
    from ..shapes.primitives import Box, Sphere
    # trunk
    session.add(Box(x, 0, z, x, height - 1, z), trunk)
    # leaves canopy
    session.add(Sphere(x, height, z, 3), leaves)
