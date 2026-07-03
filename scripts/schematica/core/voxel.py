"""VoxelGrid: a 3D array of palette indices plus the palette itself.

Coordinate convention:
  - shape == (sx, sy, sz)  (x width, y height, z depth)
  - grid[x, y, z]          (numpy array, dtype uint16)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..blocks.block import AIR, Block
from .palette import Palette


@dataclass
class VoxelGrid:
    shape: tuple[int, int, int]
    palette: Palette = field(default_factory=Palette)
    data: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 1), dtype=np.uint16))

    def __post_init__(self) -> None:
        if self.data is None or self.data.shape != self.shape:
            self.data = np.zeros(self.shape, dtype=np.uint16)

    @classmethod
    def from_array(cls, data: np.ndarray, palette: Palette | None = None) -> VoxelGrid:
        data = np.ascontiguousarray(data, dtype=np.uint16)
        if data.ndim != 3:
            raise ValueError("VoxelGrid expects a 3D array")
        return cls(shape=data.shape, palette=palette or Palette(), data=data)

    @property
    def size(self) -> tuple[int, int, int]:
        return self.shape

    @property
    def volume(self) -> int:
        return int(np.prod(self.shape))

    def _in_bounds(self, x: int, y: int, z: int) -> bool:
        sx, sy, sz = self.shape
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x: int, y: int, z: int) -> Block:
        if not self._in_bounds(x, y, z):
            raise IndexError((x, y, z))
        return self.palette[int(self.data[x, y, z])]

    def set(self, x: int, y: int, z: int, block: Block) -> None:
        if not self._in_bounds(x, y, z):
            raise IndexError((x, y, z))
        idx = self.palette.add(block)
        self.data[x, y, z] = idx

    def fill(self, block: Block) -> None:
        idx = self.palette.add(block)
        self.data[...] = idx

    def fill_air(self) -> None:
        self.data[...] = 0

    def apply_mask(self, mask: np.ndarray, block: Block) -> None:
        """Set all voxels where mask is True to ``block``.

        mask must be broadcastable to self.shape. Bounds-checked.
        """
        if mask.shape != self.shape:
            try:
                mask = np.broadcast_to(mask, self.shape)
            except ValueError as e:
                raise ValueError(f"mask shape {mask.shape} incompatible with grid {self.shape}") from e
        idx = self.palette.add(block)
        self.data[mask.astype(bool)] = idx

    def erase_mask(self, mask: np.ndarray) -> None:
        """Set voxels where mask is True to air."""
        self.apply_mask(mask, AIR)

    def paint_mask(self, mask: np.ndarray, block: Block) -> None:
        """Repaint only already-solid voxels (non-air) matching mask."""
        solid = self.data != 0
        combined = solid & np.broadcast_to(mask, self.shape).astype(bool)
        idx = self.palette.add(block)
        self.data[combined] = idx

    def replace(self, src: Block | str, dst: Block | str) -> int:
        if isinstance(src, str):
            src = Block.parse(src)
        if isinstance(dst, str):
            dst = Block.parse(dst)
        src_idx = self.palette.index_of(src)
        if src_idx is None:
            return 0
        dst_idx = self.palette.add(dst)
        count = int(np.count_nonzero(self.data == src_idx))
        self.data[self.data == src_idx] = dst_idx
        return count

    def count(self, block: Block | str) -> int:
        if isinstance(block, str):
            block = Block.parse(block)
        idx = self.palette.index_of(block)
        if idx is None:
            return 0
        return int(np.count_nonzero(self.data == idx))

    def nonempty_count(self) -> int:
        return int(np.count_nonzero(self.data != 0))

    def slice_y(self, y: int) -> np.ndarray:
        return self.data[:, y, :].copy()

    def slice_x(self, x: int) -> np.ndarray:
        return self.data[x, :, :].copy()

    def slice_z(self, z: int) -> np.ndarray:
        return self.data[:, :, z].copy()

    def subregion(self, corner: tuple[int, int, int], size: tuple[int, int, int]) -> VoxelGrid:
        x0, y0, z0 = corner
        sx, sy, sz = size
        sx_t, sy_t, sz_t = self.shape
        if x0 < 0 or y0 < 0 or z0 < 0 or x0 + sx > sx_t or y0 + sy > sy_t or z0 + sz > sz_t:
            raise ValueError("subregion out of bounds")
        return VoxelGrid.from_array(self.data[x0:x0 + sx, y0:y0 + sy, z0:z0 + sz].copy(), self.palette)

    def copy(self) -> VoxelGrid:
        return VoxelGrid.from_array(self.data.copy(), Palette.from_blocks(self.palette.blocks()))

    def rotate(self, times: int, axes: str = "xy") -> VoxelGrid:
        """Rotate by 90*times degrees in the plane of two axes."""
        times %= 4
        if times == 0:
            return self.copy()
        k = times
        ax_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
        if axes not in ax_map:
            raise ValueError(f"unknown axes pair {axes}")
        a, b = ax_map[axes]
        out = np.rot90(self.data, k=k, axes=(a, b))
        out = np.ascontiguousarray(out)
        return VoxelGrid.from_array(out, self.palette)

    def mirror(self, axis: int) -> VoxelGrid:
        if axis not in (0, 1, 2):
            raise ValueError("axis must be 0,1,2")
        return VoxelGrid.from_array(np.flip(self.data, axis=axis).copy(), self.palette)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, VoxelGrid)
            and self.shape == other.shape
            and np.array_equal(self.data, other.data)
            and self.palette == other.palette
        )

    def __repr__(self) -> str:
        return f"VoxelGrid(shape={self.shape}, palette_size={len(self.palette)}, solid={self.nonempty_count()})"
