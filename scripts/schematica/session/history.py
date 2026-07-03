"""Undo/redo history via compressed mask deltas.

Each delta records which voxels changed and their old/new palette indices.
Cheap for large grids where edits touch only a small fraction of voxels.
"""
from __future__ import annotations

from dataclasses import dataclass

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

    def apply_inverse(self, data: np.ndarray) -> None:
        d = self._undo.pop()
        data[d.coords] = d.old_values
        self._redo.append(d)

    def apply_redo(self, data: np.ndarray) -> None:
        d = self._redo.pop()
        data[d.coords] = d.new_values
        self._undo.append(d)

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
