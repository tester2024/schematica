"""Texture palette generator: noise-driven block distribution.

Generates a 2D or 3D noise field and uses it to select blocks from a weighted
palette, producing natural-looking texture variation (e.g. a stone wall that
mixes stone / cobblestone / mossy_cobblestone / cracked_stone_bricks in
organic blotches).

Two noise flavours are supported:

- **Perlin/fBm** (smooth blobs) via the existing ``noise`` package.
- **Worley/Voronoi** (cell-like patches) via a pure-numpy implementation here
  -- no extra dependency needed. Good for cracked / tiled patterns.

The output is either:
- a dense ``np.ndarray`` of blockstate strings (for direct ``set`` loops), or
- applied directly to a session/grid via ``apply_texture``.

Example::

    from schematica.generators.texture import TexturePalette, apply_texture

    tp = TexturePalette(
        blocks=["minecraft:stone", "minecraft:cobblestone",
                "minecraft:mossy_cobblestone", "minecraft:stone_bricks"],
        weights=[0.55, 0.25, 0.10, 0.10],
        noise="perlin", scale=0.15, seed=42,
    )
    # Paint a 32x1x32 floor with the texture.
    apply_texture(session, tp, (0,0,0), (31,0,31))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from ..core.chunked import ChunkedGrid

# ---- noise primitives ------------------------------------------------

def perlin_field(shape: tuple[int, ...], scale: float = 0.1,
                 octaves: int = 4, seed: int = 0) -> np.ndarray:
    """2D/3D Perlin noise field normalised to [0, 1]."""
    from .noise import perlin2d
    if len(shape) == 2:
        return perlin2d(shape, scale=scale, octaves=octaves, seed=seed)
    # 3D: stack 2D planes along the 3rd axis using offset seeds.
    sx, sy, sz = shape
    out = np.zeros(shape, dtype=np.float32)
    for z in range(sz):
        plane = perlin2d((sx, sy), scale=scale, octaves=octaves, seed=seed + z)
        out[:, :, z] = plane
    return out


def worley_field(shape: tuple[int, ...], num_points: int = 16,
                 seed: int = 0) -> np.ndarray:
    """Worley/Voronoi noise: distance to nearest random point, in [0, 1].

    Pure numpy, no extra deps. Produces cell-like patches -- good for cracked
    stone or tiled mosaic textures.
    """
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 1, size=(num_points, len(shape)))
    # Build coordinate grids.
    grids = np.meshgrid(*[np.arange(s, dtype=np.float32) / max(s - 1, 1) for s in shape],
                         indexing="ij")
    # For each voxel compute the min distance to any point (normalised by
    # diagonal of the unit cube).
    flat = np.stack([g.ravel() for g in grids], axis=-1)  # (N, D)
    # Compute distances in batches to avoid O(N*M) memory blowup on big grids.
    n = flat.shape[0]
    min_d = np.full(n, np.inf, dtype=np.float32)
    batch = 4096
    for i in range(0, num_points, batch):
        chunk = pts[i:i + batch]  # (B, D)
        d = np.linalg.norm(flat[:, None, :] - chunk[None, :, :], axis=-1)  # (N, B)
        min_d = np.minimum(min_d, d.min(axis=1))
    min_d = min_d.reshape(shape)
    # Normalise: divide by sqrt(D) (max distance in unit cube).
    min_d = min_d / (np.sqrt(len(shape)) + 1e-9)
    return np.asarray(np.clip(min_d, 0.0, 1.0))


# ---- texture palette --------------------------------------------------

@dataclass
class TexturePalette:
    """A weighted block palette driven by a noise field.

    ``blocks`` is the list of blockstate strings to choose from. ``weights``
    is the relative probability of each block (need not sum to 1). At each
    voxel the noise value (in [0, 1]) is mapped to a cumulative-weight
    threshold and the corresponding block is selected.

    ``noise`` is one of ``"perlin"`` or ``"worley"``.
    ``scale`` is the noise frequency (smaller = bigger blotches).
    """
    blocks: list[str]
    weights: list[float] = field(default_factory=lambda: [1.0])
    noise: Literal["perlin", "worley"] = "perlin"
    scale: float = 0.1
    octaves: int = 4
    seed: int = 0
    worley_points: int = 16

    def __post_init__(self) -> None:
        if len(self.weights) != len(self.blocks):
            # Default to uniform weights.
            self.weights = [1.0] * len(self.blocks)
        # Normalise weights to a cumulative distribution in [0, 1].
        w = np.asarray(self.weights, dtype=np.float64)
        self._cum = np.cumsum(w) / w.sum()

    def sample(self, shape: tuple[int, ...]) -> np.ndarray:
        """Return an int array of shape ``shape`` with palette indices.

        The caller maps indices to ``self.blocks`` to get blockstate strings.
        """
        if self.noise == "perlin":
            field_arr = perlin_field(shape, scale=self.scale,
                                      octaves=self.octaves, seed=self.seed)
        else:
            field_arr = worley_field(shape, num_points=self.worley_points,
                                     seed=self.seed)
        # Map noise value -> palette index via cumulative weights.
        flat = field_arr.ravel()
        # For each value find the first cumulative bin it falls into.
        idx = np.searchsorted(self._cum, flat, side="right")
        idx = np.clip(idx, 0, len(self.blocks) - 1)
        return idx.reshape(shape)

    def blockstate_grid(self, shape: tuple[int, ...]) -> np.ndarray:
        """Return an object array of blockstate strings of shape ``shape``."""
        idx = self.sample(shape)
        out = np.empty(shape, dtype=object)
        for i, b in enumerate(self.blocks):
            out[idx == i] = b
        return out


# ---- apply to session/grid -------------------------------------------

def apply_texture(session: Any, palette: TexturePalette,
                  frm: tuple[int, int, int], to: tuple[int, int, int]) -> int:
    """Paint a region of ``session.grid`` with blocks sampled from ``palette``.

    Voxels that are currently *air* are left as air (the texture only fills
    existing solid voxels, like ``paint``). To fill empty space, use
    ``apply_texture_fill`` instead.

    Returns the number of voxels painted.
    """
    from ..blocks.block import Block
    x0, y0, z0 = frm
    x1, y1, z1 = to
    shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
    if any(d <= 0 for d in shape):
        return 0
    idx_grid = palette.sample(shape)
    blocks = palette.blocks
    count = 0
    grid = session.grid
    # Pre-resolve blocks once.
    resolved = [Block.parse(b) for b in blocks]
    # For chunked grids we walk touched chunks; for dense grids we vectorise.
    if isinstance(grid, ChunkedGrid):
        for xx in range(shape[0]):
            for yy in range(shape[1]):
                for zz in range(shape[2]):
                    b = resolved[int(idx_grid[xx, yy, zz])]
                    wx, wy, wz = x0 + xx, y0 + yy, z0 + zz
                    if 0 <= wx < grid.shape[0] and 0 <= wy < grid.shape[1] and 0 <= wz < grid.shape[2]:
                        cur = grid.get(wx, wy, wz)
                        if cur.name != "minecraft:air":
                            grid.set(wx, wy, wz, b)
                            count += 1
    else:
        data = grid.data
        # Build a palette-index array matching grid.palette for each texture block.
        tex_indices = np.array([grid.palette.add(b) for b in resolved], dtype=np.uint16)
        # Mask: region that is currently solid.
        region = data[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1]
        solid = region != 0
        # Map sampled texture indices to grid palette indices.
        new_vals = tex_indices[idx_grid]
        # Apply only where solid.
        region[solid] = new_vals[solid]
        count = int(np.count_nonzero(solid))
    return count


def apply_texture_fill(session: Any, palette: TexturePalette,
                       frm: tuple[int, int, int], to: tuple[int, int, int]) -> int:
    """Fill a region (overwriting air too) with blocks sampled from ``palette``.

    Returns the number of voxels written.
    """
    from ..blocks.block import Block
    x0, y0, z0 = frm
    x1, y1, z1 = to
    shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
    if any(d <= 0 for d in shape):
        return 0
    idx_grid = palette.sample(shape)
    blocks = palette.blocks
    grid = session.grid
    resolved = [Block.parse(b) for b in blocks]
    count = 0
    if isinstance(grid, ChunkedGrid):
        for xx in range(shape[0]):
            for yy in range(shape[1]):
                for zz in range(shape[2]):
                    b = resolved[int(idx_grid[xx, yy, zz])]
                    wx, wy, wz = x0 + xx, y0 + yy, z0 + zz
                    if 0 <= wx < grid.shape[0] and 0 <= wy < grid.shape[1] and 0 <= wz < grid.shape[2]:
                        grid.set(wx, wy, wz, b)
                        count += 1
    else:
        data = grid.data
        tex_indices = np.array([grid.palette.add(b) for b in resolved], dtype=np.uint16)
        new_vals = tex_indices[idx_grid]
        region = data[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1]
        region[...] = new_vals
        count = int(np.prod(shape))
    return count
