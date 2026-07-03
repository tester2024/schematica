# Preview rendering

## `schematica.render.preview`

### `preview(grid, out_dir, views=("top", "front", "right", "iso"), max_voxels=96**3, max_dim=256) -> list[Path]`
Renders the VoxelGrid to PNG files in `out_dir`. Creates the directory if it
does not exist. Returns the list of written paths.

Files are named `preview_<view>.png`. Views:
- `top`   — looking down the Y axis (`view_init(elev=90, azim=-90)`).
- `front` — looking along Z (`elev=0, azim=-90`).
- `right` — along X (`elev=0, azim=0`).
- `iso`   — angled (`elev=30, azim=45`).

## Backend

Small dense grids use `matplotlib`'s `mpl_toolkits.mplot3d.Axes3D.voxels` under
the `Agg` backend (headless). The renderer:
1. Builds an `(sx, sy, sz, 4)` RGBA array from the palette.
2. Fills voxels where `grid.data != 0` (non-air) with their block's color and
   alpha 1.0; air voxels get alpha 0.0 (transparent).
3. Calls `ax.voxels(filled, facecolors=rgba, edgecolors=(0.05, 0.05, 0.05, 0.25))`.
4. Sets `view_init(elev, azim)` per view, `set_box_aspect((sx, sy, sz))` so the
   aspect ratio matches the grid.
5. Saves at 100 dpi, 6×6 inches.

Large dense grids above `max_voxels` emit a `RuntimeWarning` and switch to
downsampled 2D projected previews. `ChunkedGrid` previews always use projected
rendering and do not materialise a full dense array. `max_dim` caps the longest
rendered image axis.

## Color map

`schematica/render/preview.py::_BLOCK_COLORS` (inside `scripts/`) is a hand-picked dict of
`block_name -> (r, g, b)` for common vanilla blocks. Examples:
- `minecraft:grass_block` -> `(0.35, 0.65, 0.25)` green
- `minecraft:stone` -> `(0.5, 0.5, 0.5)` gray
- `minecraft:glass` -> `(0.7, 0.85, 0.95)` light blue
- `minecraft:obsidian` -> `(0.08, 0.05, 0.12)` near-black
- `minecraft:oak_log` -> `(0.45, 0.30, 0.18)` brown

Unknown blocks get a stable color derived from `abs(hash(name)) % 0xFFFFFF`,
lightened by +0.2 in each channel. This makes every build visually
distinguishable but not necessarily accurate to in-game textures.

## Extending colors

Edit `_BLOCK_COLORS` in `preview.py` to add or override:
```python
_BLOCK_COLORS["minecraft:polished_andesite"] = (0.78, 0.78, 0.78)
```
Tests do not assert on colors, so this is safe to change without breaking the
suite. The `test_preview.py` test only checks that PNGs are written and
non-trivially sized (>100 bytes).

## Performance

- Comfortable 3D voxel rendering is still around ~32³. At larger sizes the
  projected fallback is intentionally less detailed but much safer.
- For visual debugging on large maps, use `views=("top",)` first, then add
  `front` or `right` only if needed.
- For final beauty shots, render a small `subregion(...)` with the 3D path.

## Reading previews as an agent

Agents cannot see images, but can verify:
```python
from pathlib import Path
for p in Path("previews").glob("preview_*.png"):
    assert p.stat().st_size > 1000   # non-empty PNG
```
A tiny or zero-byte PNG indicates a render failure; check stderr from the
schematica process for matplotlib exceptions.
