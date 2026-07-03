"""Session: the orchestrator holding grid + palette + version + history.

This is the primary library API surface. The CLI is a thin shell over it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..blocks.block import AIR, Block
from ..blocks.registry import BlockRegistry
from ..core.palette import Palette
from ..core.voxel import VoxelGrid
from ..shapes.base import Shape
from .history import History, diff_delta


@dataclass
class Session:
    version: str = "1.20.1"
    grid: VoxelGrid = field(default_factory=lambda: VoxelGrid(shape=(16, 16, 16)))
    history: History = field(default_factory=History)
    metadata: dict = field(default_factory=dict)
    registry: BlockRegistry = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.registry is None:
            self.registry = BlockRegistry.for_version(self.version)

    @classmethod
    def new(cls, shape: tuple[int, int, int], version: str = "1.20.1",
            fill: Block = AIR) -> Session:
        reg = BlockRegistry.for_version(version)
        grid = VoxelGrid(shape=shape)
        if fill != AIR:
            grid.fill(fill)
        return cls(version=version, grid=grid, registry=reg)

    def _resolve(self, block: Block | str) -> Block:
        if isinstance(block, str):
            block = Block.parse(block)
        return self.registry.resolve(block)

    def _record(self, new_data: np.ndarray) -> None:
        delta = diff_delta(self.grid.data, new_data)
        self.history.push(delta)
        self.grid.data = new_data

    def add(self, shape: Shape, block: Block | str = "minecraft:stone") -> Session:
        b = self._resolve(block)
        mask = shape.mask(self.grid.shape)
        new = self.grid.data.copy()
        idx = self.grid.palette.add(b)
        new[mask.astype(bool)] = idx
        self._record(new)
        return self

    def subtract(self, shape: Shape) -> Session:
        mask = shape.mask(self.grid.shape)
        new = self.grid.data.copy()
        new[mask.astype(bool)] = 0
        self._record(new)
        return self

    def intersect(self, shape: Shape, block: Block | str) -> Session:
        b = self._resolve(block)
        mask = shape.mask(self.grid.shape)
        new = self.grid.data.copy()
        solid = new != 0
        sel = solid & mask.astype(bool)
        idx = self.grid.palette.add(b)
        new[sel] = idx
        self._record(new)
        return self

    def paint(self, shape: Shape, block: Block | str) -> Session:
        b = self._resolve(block)
        mask = shape.mask(self.grid.shape)
        new = self.grid.data.copy()
        solid = new != 0
        sel = solid & mask.astype(bool)
        idx = self.grid.palette.add(b)
        new[sel] = idx
        self._record(new)
        return self

    def replace(self, src: Block | str, dst: Block | str) -> int:
        src_b = self._resolve(src)
        dst_b = self._resolve(dst)
        src_idx = self.grid.palette.index_of(src_b)
        if src_idx is None:
            return 0
        new = self.grid.data.copy()
        sel = new == src_idx
        dst_idx = self.grid.palette.add(dst_b)
        new[sel] = dst_idx
        self._record(new)
        return int(np.count_nonzero(sel))

    def fill_all(self, block: Block | str) -> Session:
        b = self._resolve(block)
        new = np.zeros_like(self.grid.data)
        idx = self.grid.palette.add(b)
        new[...] = idx
        self._record(new)
        return self

    def clear(self) -> Session:
        new = np.zeros_like(self.grid.data)
        self._record(new)
        return self

    def transform_rotate(self, times: int, axes: str = "xy") -> Session:
        new = np.ascontiguousarray(np.rot90(self.grid.data, k=times, axes={"xy":(0,1),"xz":(0,2),"yz":(1,2)}[axes]))
        self.grid = VoxelGrid.from_array(new, self.grid.palette)
        return self

    def transform_mirror(self, axis: int) -> Session:
        new = np.flip(self.grid.data, axis=axis).copy()
        self.grid = VoxelGrid.from_array(new, self.grid.palette)
        return self

    def undo(self) -> bool:
        if not self.history.can_undo():
            return False
        self.history.apply_inverse(self.grid.data)
        return True

    def redo(self) -> bool:
        if not self.history.can_redo():
            return False
        self.history.apply_redo(self.grid.data)
        return True

    def snapshot(self) -> dict:
        return {
            "version": self.version,
            "shape": list(self.grid.shape),
            "palette": self.grid.palette.to_json(),
            "data_b64": _np_to_b64(self.grid.data),
            "metadata": self.metadata,
        }

    @classmethod
    def restore(cls, snap: dict) -> Session:
        s = cls.new(tuple(snap["shape"]), version=snap["version"])
        s.grid.palette = Palette.from_json(snap["palette"])
        s.grid.data = _b64_to_np(snap["data_b64"], tuple(snap["shape"]))
        s.metadata = dict(snap.get("metadata", {}))
        return s

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.snapshot()), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> Session:
        return cls.restore(json.loads(Path(path).read_text(encoding="utf-8")))

    def stats(self) -> dict:
        return {
            "shape": list(self.grid.shape),
            "volume": self.grid.volume,
            "solid": self.grid.nonempty_count(),
            "palette_size": len(self.grid.palette),
        }


def _np_to_b64(arr: np.ndarray) -> str:
    import base64

    return base64.b64encode(arr.tobytes()).decode("ascii")


def _b64_to_np(s: str, shape: tuple[int, int, int]) -> np.ndarray:
    import base64

    raw = base64.b64decode(s)
    return np.frombuffer(raw, dtype=np.uint16).reshape(shape).copy()
