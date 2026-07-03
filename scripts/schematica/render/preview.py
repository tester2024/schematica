"""Render VoxelGrid to PNG previews (top/front/right/iso) via matplotlib voxels."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..blocks.block import Block
from ..core.chunked import ChunkedGrid
from ..core.palette import Palette
from ..core.voxel import VoxelGrid

# Hand-picked block colors for common blocks. Falls back to gray.
_BLOCK_COLORS: dict[str, tuple[float, float, float]] = {
    "minecraft:air": (0.0, 0.0, 0.0),
    "minecraft:stone": (0.5, 0.5, 0.5),
    "minecraft:grass_block": (0.35, 0.65, 0.25),
    "minecraft:dirt": (0.55, 0.40, 0.25),
    "minecraft:cobblestone": (0.45, 0.45, 0.48),
    "minecraft:oak_planks": (0.65, 0.50, 0.30),
    "minecraft:oak_log": (0.45, 0.30, 0.18),
    "minecraft:glass": (0.7, 0.85, 0.95),
    "minecraft:bricks": (0.60, 0.30, 0.25),
    "minecraft:obsidian": (0.08, 0.05, 0.12),
    "minecraft:bedrock": (0.25, 0.25, 0.25),
    "minecraft:sand": (0.85, 0.78, 0.55),
    "minecraft:glowstone": (0.85, 0.75, 0.40),
    "minecraft:end_stone": (0.85, 0.82, 0.70),
    "minecraft:sea_lantern": (0.85, 0.90, 0.75),
    "minecraft:packed_ice": (0.60, 0.80, 0.95),
    "minecraft:red_sand": (0.70, 0.35, 0.20),
    "minecraft:quartz_block": (0.92, 0.92, 0.92),
    "minecraft:prismarine": (0.30, 0.55, 0.55),
    "minecraft:purple_stained_glass": (0.55, 0.20, 0.75),
    "minecraft:oak_fence": (0.50, 0.35, 0.20),
}


def _color_for(block: Block) -> tuple[float, float, float]:
    c = _BLOCK_COLORS.get(block.name)
    if c:
        return c
    # Hash name -> stable color
    h = abs(hash(block.name)) % 0xFFFFFF
    r = ((h >> 16) & 0xFF) / 255.0
    g = ((h >> 8) & 0xFF) / 255.0
    b = (h & 0xFF) / 255.0
    # lighten a bit
    return (min(r + 0.2, 1.0), min(g + 0.2, 1.0), min(b + 0.2, 1.0))


def _build_color_array(grid: VoxelGrid) -> np.ndarray:
    sx, sy, sz = grid.shape
    rgba = np.zeros((sx, sy, sz, 4), dtype=float)
    palette = grid.palette.blocks()
    for i, b in enumerate(palette):
        r, g, bcol = _color_for(b)
        sel = grid.data == i
        rgba[sel] = (r, g, bcol, 1.0 if b.name != "minecraft:air" else 0.0)
    return rgba


def _render_view(grid: VoxelGrid, elev: int, azim: int, out: Path, *, title: str,
                  size: tuple[int, int] = (6, 6)) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    sx, sy, sz = grid.shape
    fig = plt.figure(figsize=size, dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title(title)
    ax.set_box_aspect((sx, sy, sz))
    rgba = _build_color_array(grid)
    filled = grid.data != 0
    # matplotlib voxels wants full-shape arrays
    rgba_vox = rgba.copy()
    rgba_vox[..., 3] = np.where(filled, 1.0, 0.0)
    ax.voxels(filled, facecolors=rgba_vox, edgecolors=(0.05, 0.05, 0.05, 0.25))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    plt.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def preview(grid: VoxelGrid | ChunkedGrid, out_dir: str | Path,
            views: tuple[str, ...] = ("top", "front", "right", "iso")) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(grid, ChunkedGrid):
        return preview_chunked(grid, out_dir, views)
    views_map: dict[str, tuple[int, int]] = {
        "top": (90, -90),
        "front": (0, -90),
        "right": (0, 0),
        "iso": (30, 45),
    }
    paths: list[Path] = []
    for v in views:
        elev, azim = views_map.get(v, (30, 45))
        out = out_dir / f"preview_{v}.png"
        _render_view(grid, elev, azim, out, title=v)
        paths.append(out)
    return paths


def _color_array_from_palette(palette: Palette) -> dict[int, tuple[float, float, float, float]]:
    out: dict[int, tuple[float, float, float, float]] = {}
    for i, b in enumerate(palette.blocks()):
        r, g, bcol = _color_for(b)
        out[i] = (r, g, bcol, 0.0 if b.name == "minecraft:air" else 1.0)
    return out


def preview_chunked(grid: ChunkedGrid, out_dir: str | Path,
                     views: tuple[str, ...] = ("top", "front", "right", "iso"),
                     *, max_dim: int = 256) -> list[Path]:
    """Render a ChunkedGrid without materialising a full dense array.

    Builds per-view 2D images by projecting touched chunks. ``max_dim``
    caps the longest axis of the rendered image so memory stays bounded for
    maps spanning hundreds of chunks.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sx, sy, sz = grid.shape
    # Downsample factor so no rendered side exceeds max_dim.
    ds = max(1, max(sx, sy, sz) // max_dim)
    colors = _color_array_from_palette(grid.palette)
    paths: list[Path] = []
    view_specs = {
        "top": ("xz", "y", "top"),
        "front": ("xz", "y", "front"),
        "right": ("yz", "x", "right"),
        "iso": ("xz", "y", "iso"),
    }
    for v in views:
        plane, depth_axis, title = view_specs.get(v, ("xz", "y", v))
        img = _project_chunked(grid, plane, depth_axis, colors, ds)
        fig = plt.figure(figsize=(6, 6), dpi=100)
        ax = fig.add_subplot(111)
        ax.imshow(np.rot90(img), origin="upper")
        ax.set_title(f"{title} (ds={ds})")
        ax.axis("off")
        out = out_dir / f"preview_{v}.png"
        fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        paths.append(out)
    return paths


def _project_chunked(grid: ChunkedGrid, plane: str, depth_axis: str,
                     colors: dict[int, tuple[float, float, float, float]],
                     ds: int) -> np.ndarray:
    """Project touched chunks onto a 2D plane, downsampling by ``ds``.

    plane is 'xz' (top/front) or 'yz' (right). depth_axis selects which axis
    collapses ('y' for top, etc.) -- we use max-projection (frontmost solid
    voxel wins) so the result looks like a silhouette.
    """
    sx, sy, sz = grid.shape
    if plane == "xz":
        w, h = sx // ds, sz // ds
        img = np.zeros((w, h, 4), dtype=float)
    else:  # yz
        w, h = sy // ds, sz // ds
        img = np.zeros((w, h, 4), dtype=float)
    # Initialize with transparent.
    for (cx, cy, cz), arr in grid._chunks.items():
        cs = grid.chunk_size
        ox = cx * cs
        oy = cy * cs
        oz = cz * cs
        sx_a, sy_a, sz_a = arr.shape
        if plane == "xz":
            # Collapse y; for each (x, z) pick the topmost non-air voxel.
            for i in range(sx_a):
                for k in range(sz_a):
                    wx = (ox + i) // ds
                    wz = (oz + k) // ds
                    if wx >= w or wz >= h:
                        continue
                    col = img[wx, wz]
                    if col[3] >= 1.0:
                        continue
                    # Find topmost solid in this column within the chunk.
                    for j in range(sy_a - 1, -1, -1):
                        v = int(arr[i, j, k])
                        if v != 0:
                            img[wx, wz] = colors.get(v, (0.5, 0.5, 0.5, 1.0))
                            break
        else:  # yz, collapse x
            for j in range(sy_a):
                for k in range(sz_a):
                    wy = (oy + j) // ds
                    wz = (oz + k) // ds
                    if wy >= w or wz >= h:
                        continue
                    col = img[wy, wz]
                    if col[3] >= 1.0:
                        continue
                    for i in range(sx_a - 1, -1, -1):
                        v = int(arr[i, j, k])
                        if v != 0:
                            img[wy, wz] = colors.get(v, (0.5, 0.5, 0.5, 1.0))
                            break
    return img
