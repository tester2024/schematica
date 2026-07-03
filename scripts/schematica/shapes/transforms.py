"""Geometric transforms: translate, rotate, mirror, scale, repeat/array."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Shape


@dataclass(frozen=True)
class Translated:
    shape: Shape
    dx: int
    dy: int
    dz: int

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sx, sy, sz = shape
        dx, dy, dz = self.dx, self.dy, self.dz
        # Build the shape's mask in a shifted canvas.
        # Compute required extent, allocate, draw into it.
        sub = self.shape.mask(shape)  # then roll within bounds
        return np.roll(np.roll(np.roll(sub, dx, axis=0), dy, axis=1), dz, axis=2)


@dataclass(frozen=True)
class Mirror:
    shape: Shape
    axis: int  # 0=x,1=y,2=z

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return np.flip(self.shape.mask(shape), axis=self.axis).copy()


@dataclass(frozen=True)
class Rotated90:
    """Rotate a shape's mask by 90*times in the plane of two axes (k from np.rot90)."""
    shape: Shape
    times: int = 1
    axes: str = "xy"

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        ax_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
        a, b = ax_map[self.axes]
        return np.ascontiguousarray(np.rot90(self.shape.mask(shape), k=self.times, axes=(a, b)))


@dataclass(frozen=True)
class Array:
    """Repeat a shape N times along an axis with spacing."""
    shape: Shape
    count: int
    axis: int  # 0,1,2
    spacing: int

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        out = np.zeros(shape, dtype=bool)
        base = self.shape.mask(shape)
        for i in range(self.count):
            off = i * self.spacing
            sl = [slice(None), slice(None), slice(None)]
            if self.axis == 0:
                sl[0] = slice(0, shape[0] - off)
            elif self.axis == 1:
                sl[1] = slice(0, shape[1] - off)
            else:
                sl[2] = slice(0, shape[2] - off)
            dst = [slice(None), slice(None), slice(None)]
            dst[self.axis] = slice(off, shape[self.axis])
            sub = base[tuple(sl)]
            # crop to fit
            tgt = out[tuple(dst)]
            m = sub.shape
            tgt_shape = tgt.shape
            cut = tuple(slice(0, min(m[i], tgt_shape[i])) for i in range(3))
            tgt[cut] = sub[cut]
        return out


@dataclass(frozen=True)
class NoiseDeformed:
    """Take a base shape and perturb its mask edges with Perlin noise.

    Each voxel just inside the base mask may be removed, and each just outside
    may be added, based on a noise threshold. `amplitude` controls how many
    voxels of deformation are possible; `scale` is the noise frequency.
    """
    shape: Shape
    amplitude: int = 2
    scale: float = 0.1
    seed: int = 0

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        base = self.shape.mask(shape).astype(bool)
        if self.amplitude <= 0:
            return base
        try:
            from ..generators.noise import perlin2d
        except ImportError:
            return base
        # Build a 3D-ish noise by sampling perlin2d on (x+z, y) planes.
        sx, sy, sz = shape
        n1 = perlin2d((sx, sy), scale=self.scale, seed=self.seed)
        n2 = perlin2d((sz, sy), scale=self.scale, seed=self.seed + 1)
        n3 = perlin2d((sx, sz), scale=self.scale, seed=self.seed + 2)
        # Stack into 3D: average of the three planar noises.
        noise = (n1[:, :, None].repeat(sz, axis=2) +
                 n2[None, :, :].repeat(sx, axis=0) +
                 n3[:, None, :].repeat(sy, axis=1)) / 3.0
        # noise is in [0,1]; shift to [-0.5, 0.5]
        noise = noise - 0.5
        # Compute distance-from-edge approximation: dilate - erode.
        from scipy import ndimage as _ndi
        eroded = _ndi.binary_erosion(base)
        dilated = _ndi.binary_dilation(base)
        edge_inner = base & ~eroded        # voxels that could be removed
        edge_outer = dilated & ~base       # voxels that could be added
        thresh = self.amplitude / 10.0
        remove = edge_inner & (noise < -thresh)
        add = edge_outer & (noise > thresh)
        out = base.copy()
        out[remove] = False
        out[add] = True
        return out


@dataclass(frozen=True)
class Shell:
    """Keep only the outer N-voxel shell of any shape (hollow it out)."""
    shape: Shape
    thickness: int = 1

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        base = self.shape.mask(shape).astype(bool)
        if self.thickness <= 0:
            return base
        try:
            from scipy import ndimage as _ndi
        except ImportError:
            # Fallback: manual erosion via slicing
            eroded = base.copy()
            for _ in range(self.thickness):
                eroded = (
                    eroded &
                    np.roll(eroded, 1, axis=0) & np.roll(eroded, -1, axis=0) &
                    np.roll(eroded, 1, axis=1) & np.roll(eroded, -1, axis=1) &
                    np.roll(eroded, 1, axis=2) & np.roll(eroded, -1, axis=2)
                )
            return base & ~eroded
        eroded = _ndi.binary_erosion(base, iterations=self.thickness)
        return base & ~eroded
