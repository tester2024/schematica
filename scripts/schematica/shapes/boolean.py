"""Boolean ops over shape masks (union, intersect, subtract, xor)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Shape, bounds_default, intersect_bbox


def _shape_bounds(s: Shape, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    if hasattr(s, "bounds"):
        b = s.bounds(grid_shape)
        if b is not None:
            return tuple(int(v) for v in b)  # type: ignore[return-value]
    return bounds_default(grid_shape)


def _bbox_union(a: tuple[int, int, int, int, int, int] | None,
                b: tuple[int, int, int, int, int, int] | None
                ) -> tuple[int, int, int, int, int, int] | None:
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]),
            max(a[3], b[3]), max(a[4], b[4]), max(a[5], b[5]))


@dataclass(frozen=True)
class Union:
    shapes: tuple[Shape, ...]

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        acc = None
        for s in self.shapes:
            acc = _bbox_union(acc, _shape_bounds(s, grid_shape))
        return acc if acc is not None else bounds_default(grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        out = np.zeros(shape, dtype=bool)
        for s in self.shapes:
            out |= s.mask(shape).astype(bool)
        return out


@dataclass(frozen=True)
class Intersect:
    shapes: tuple[Shape, ...]

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        if not self.shapes:
            return bounds_default(grid_shape)
        acc = _shape_bounds(self.shapes[0], grid_shape)
        for s in self.shapes[1:]:
            ib = intersect_bbox(acc, _shape_bounds(s, grid_shape))
            if ib is None:
                return (0, 0, 0, -1, -1, -1)
            acc = ib
        return acc

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        if not self.shapes:
            return np.zeros(shape, dtype=bool)
        out = self.shapes[0].mask(shape).astype(bool)
        for s in self.shapes[1:]:
            out &= s.mask(shape).astype(bool)
        return out


@dataclass(frozen=True)
class Subtract:
    a: Shape
    b: Shape

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        # Subtract touches at most the bbox of a.
        return _shape_bounds(self.a, grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return np.asarray(self.a.mask(shape) & ~self.b.mask(shape).astype(bool))


@dataclass(frozen=True)
class Xor:
    a: Shape
    b: Shape

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        result = _bbox_union(_shape_bounds(self.a, grid_shape), _shape_bounds(self.b, grid_shape))
        return result if result is not None else bounds_default(grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return np.asarray(self.a.mask(shape).astype(bool) ^ self.b.mask(shape).astype(bool))
