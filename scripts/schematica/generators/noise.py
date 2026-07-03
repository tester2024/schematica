"""Perlin/simplex noise helpers (via the `noise` package)."""
from __future__ import annotations

import numpy as np


def perlin2d(shape: tuple[int, int], scale: float = 0.05, octaves: int = 4,
             persistence: float = 0.5, lacunarity: float = 2.0,
             seed: int = 0) -> np.ndarray:
    try:
        from noise import snoise2
    except ImportError as e:
        raise RuntimeError("install the 'noise' package") from e
    w, h = shape
    out = np.zeros((w, h), dtype=np.float32)
    for x in range(w):
        for y in range(h):
            out[x, y] = snoise2(x * scale, y * scale, octaves=octaves,
                                persistence=persistence, lacunarity=lacunarity,
                                repeatx=1024, repeaty=1024, base=seed)
    # normalize to [0,1]
    out = (out - out.min()) / (out.max() - out.min() + 1e-9)
    return out


def fbm2d(shape: tuple[int, int], scale: float = 0.05, octaves: int = 4,
          seed: int = 0) -> np.ndarray:
    return perlin2d(shape, scale=scale, octaves=octaves, seed=seed)
