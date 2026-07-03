"""Boolean ops over shape masks (union, intersect, subtract, xor)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Shape


@dataclass(frozen=True)
class Union:
    shapes: tuple[Shape, ...]

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        out = np.zeros(shape, dtype=bool)
        for s in self.shapes:
            out |= s.mask(shape).astype(bool)
        return out


@dataclass(frozen=True)
class Intersect:
    shapes: tuple[Shape, ...]

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

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return self.a.mask(shape) & ~self.b.mask(shape).astype(bool)


@dataclass(frozen=True)
class Xor:
    a: Shape
    b: Shape

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return self.a.mask(shape).astype(bool) ^ self.b.mask(shape).astype(bool)
