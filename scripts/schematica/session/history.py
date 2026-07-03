"""Undo/redo history via compressed mask deltas.

Each delta records which voxels changed and their old/new palette indices.
Cheap for large grids where edits touch only a small fraction of voxels.

For chunked grids, deltas store world-space coordinates so undo/redo can
address individual voxels across chunks (allocating a chunk if redo re-fills
an emptied one).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class Delta:
    coords: tuple[np.ndarray, np.ndarray, np.ndarray]
    old_values: np.ndarray
    new_values: np.ndarray


class History:
    def __init__(self, limit: int = 100) -> None:
        self._undo: list[Delta] = []
        self._redo: list[Delta] = []
        self.limit = limit

    def push(self, delta: Delta) -> None:
        self._undo.append(delta)
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def apply_inverse(self, target: Any) -> None:
        """Apply the inverse of the top undo delta.

        ``target`` is either a ``np.ndarray`` (dense grid) or a ``ChunkedGrid``.
        """
        d = self._undo.pop()
        self._apply_values(target, d.coords, d.old_values)
        self._redo.append(d)

    def apply_redo(self, target: Any) -> None:
        d = self._redo.pop()
        self._apply_values(target, d.coords, d.new_values)
        self._undo.append(d)

    def _apply_values(self, target: Any, coords: tuple[np.ndarray, np.ndarray, np.ndarray],
                      values: np.ndarray) -> None:
        if isinstance(target, np.ndarray):
            target[coords] = values
            return
        # ChunkedGrid: write per-voxel via set(), materialising chunks on demand.
        cs = target.chunk_size
        xs, ys, zs = coords
        for i in range(len(values)):
            x, y, z = int(xs[i]), int(ys[i]), int(zs[i])
            v = int(values[i])
            cx, cy, cz = x // cs, y // cs, z // cs
            arr = target._ensure_chunk(cx, cy, cz)
            lx, ly, lz = x % cs, y % cs, z % cs
            arr[lx, ly, lz] = v
            if v == 0:
                target._drop_chunk_if_empty(cx, cy, cz)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()


def diff_delta(data: np.ndarray, new: np.ndarray) -> Delta:
    mask = data != new
    coords = np.nonzero(mask)
    return Delta(
        coords=coords,
        old_values=data[mask].copy(),
        new_values=new[mask].copy(),
    )
