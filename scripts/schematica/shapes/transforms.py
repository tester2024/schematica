"""Geometric transforms: translate, rotate, mirror, scale, repeat/array."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Shape, bounds_default


def _shape_bounds(s: Shape, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    if hasattr(s, "bounds"):
        b = s.bounds(grid_shape)
        if b is not None:
            return tuple(int(v) for v in b)  # type: ignore[return-value]
    return bounds_default(grid_shape)


@dataclass(frozen=True)
class Translated:
    shape: Shape
    dx: int
    dy: int
    dz: int

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        x0, y0, z0, x1, y1, z1 = _shape_bounds(self.shape, grid_shape)
        return (int(max(x0 + self.dx, 0)), int(max(y0 + self.dy, 0)), int(max(z0 + self.dz, 0)),
                int(min(x1 + self.dx, grid_shape[0] - 1)), int(min(y1 + self.dy, grid_shape[1] - 1)), int(min(z1 + self.dz, grid_shape[2] - 1)))

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        sx, sy, sz = shape
        dx, dy, dz = self.dx, self.dy, self.dz
        # Compute the shape's mask in a canvas large enough to hold the
        # translated version, then copy only the in-bounds region. This avoids
        # np.roll's wrap-around which would scatter voxels to the opposite edge.
        x0 = max(dx, 0)
        y0 = max(dy, 0)
        z0 = max(dz, 0)
        x1 = min(sx + dx, sx)
        y1 = min(sy + dy, sy)
        z1 = min(sz + dz, sz)
        if x1 <= x0 or y1 <= y0 or z1 <= z0:
            return np.zeros(shape, dtype=bool)
        # Evaluate the shape over its own coords, then copy the sub-window.
        # We evaluate at full grid size (shape unchanged), then slice the
        # source window [max(-dx,0) : min(sx-dx, sx), ...] and place into
        # [x0:x1, ...].
        src = self.shape.mask(shape).astype(bool)
        sx0 = max(-dx, 0)
        sy0 = max(-dy, 0)
        sz0 = max(-dz, 0)
        sx1 = min(sx - dx, sx)
        sy1 = min(sy - dy, sy)
        sz1 = min(sz - dz, sz)
        out = np.zeros(shape, dtype=bool)
        out[x0:x1, y0:y1, z0:z1] = src[sx0:sx1, sy0:sy1, sz0:sz1]
        return out


@dataclass(frozen=True)
class Mirror:
    shape: Shape
    axis: int  # 0=x,1=y,2=z

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return _shape_bounds(self.shape, grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        return np.flip(self.shape.mask(shape), axis=self.axis).copy()


@dataclass(frozen=True)
class Rotated90:
    """Rotate a shape's mask by 90*times in the plane of two axes (k from np.rot90)."""
    shape: Shape
    times: int = 1
    axes: str = "xy"

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return _shape_bounds(self.shape, grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        ax_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
        a, b = ax_map[self.axes]
        return np.ascontiguousarray(np.rot90(self.shape.mask(shape), k=self.times, axes=(a, b)))


@dataclass(frozen=True)
class Rotated:
    """Rotate a shape's mask by an arbitrary angle in a coordinate plane.

    Unlike :class:`Rotated90` (which only supports multiples of 90 degrees),
    this transform resamples the mask at any angle via nearest-neighbour
    interpolation. ``angle_deg`` is the rotation angle in degrees, applied
    in the plane named by ``axes`` (``"xy"``, ``"xz"`` or ``"yz"``). The
    rotation is about the grid centre in the rotation plane; the third axis
    is left unchanged.

    This unlocks high-fidelity diagonals (e.g. 30°, 45°) without needing
    full matrix rotations or external trimesh voxelization.
    """
    shape: Shape
    angle_deg: float = 0.0
    axes: str = "xy"
    order: int = 0  # 0 = nearest neighbour, 1 = bilinear (then thresholded)

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        # Conservative: assume the rotated mask could touch the full plane.
        return _shape_bounds(self.shape, grid_shape)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        ax_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
        if self.axes not in ax_map:
            raise ValueError(f"axes must be one of {list(ax_map)}; got {self.axes!r}")
        a, b = ax_map[self.axes]
        base = self.shape.mask(shape).astype(np.float32)
        theta = float(np.deg2rad(self.angle_deg))
        # Rotation about the centre of the rotation plane.
        sa, sb = shape[a], shape[b]
        ca = (sa - 1) / 2.0
        cb = (sb - 1) / 2.0
        # Build index grids for the output (rotated) frame.
        idx_a = np.arange(sa, dtype=np.float32)
        idx_b = np.arange(sb, dtype=np.float32)
        ga, gb = np.meshgrid(idx_a, idx_b, indexing="ij")
        # Inverse-rotate output coords back to source coords.
        src_a = ca + np.cos(theta) * (ga - ca) - np.sin(theta) * (gb - cb)
        src_b = cb + np.sin(theta) * (ga - ca) + np.cos(theta) * (gb - cb)
        # Map to source indices (round for nearest-neighbour).
        ia = np.rint(src_a).astype(np.int32)
        ib = np.rint(src_b).astype(np.int32)
        valid = (ia >= 0) & (ia < sa) & (ib >= 0) & (ib < sb)
        ia_c = np.clip(ia, 0, sa - 1)
        ib_c = np.clip(ib, 0, sb - 1)
        # We need to gather along axes a and b of the 3D base array.
        # Build a per-(a,b) sample then broadcast over the third axis.
        out = np.zeros_like(base)
        # Build 2D sample of base collapsed along the third axis via any()
        # is wrong — we need to gather per third-axis slice. Do it via
        # advanced indexing: for each third-axis index, gather base[ia, ib, k].
        # We do this vectorised by broadcasting the 2D lookup.
        if a == 0 and b == 1:
            for k in range(shape[2]):
                sl = base[:, :, k]
                gathered = np.where(valid, sl[ia_c, ib_c], 0.0)
                out[:, :, k] = gathered
        elif a == 0 and b == 2:
            for k in range(shape[1]):
                sl = base[:, k, :]
                gathered = np.where(valid, sl[ia_c, ib_c], 0.0)
                out[:, k, :] = gathered
        else:  # a == 1, b == 2
            for k in range(shape[0]):
                sl = base[k, :, :]
                gathered = np.where(valid, sl[ia_c, ib_c], 0.0)
                out[k, :, :] = gathered
        return (out > 0.5).astype(bool)


@dataclass(frozen=True)
class Array:
    """Repeat a shape N times along an axis with spacing."""
    shape: Shape
    count: int
    axis: int  # 0,1,2
    spacing: int

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        x0, y0, z0, x1, y1, z1 = _shape_bounds(self.shape, grid_shape)
        span = (self.count - 1) * self.spacing
        if self.axis == 0:
            return (x0, y0, z0, min(x1 + span, grid_shape[0] - 1), y1, z1)
        if self.axis == 1:
            return (x0, y0, z0, x1, min(y1 + span, grid_shape[1] - 1), z1)
        return (x0, y0, z0, x1, y1, min(z1 + span, grid_shape[2] - 1))

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

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        b = _shape_bounds(self.shape, grid_shape)
        x0 = max(b[0] - self.amplitude, 0)
        y0 = max(b[1] - self.amplitude, 0)
        z0 = max(b[2] - self.amplitude, 0)
        x1 = min(b[3] + self.amplitude, grid_shape[0] - 1)
        y1 = min(b[4] + self.amplitude, grid_shape[1] - 1)
        z1 = min(b[5] + self.amplitude, grid_shape[2] - 1)
        return (x0, y0, z0, x1, y1, z1)

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        base = self.shape.mask(shape).astype(bool)
        if self.amplitude <= 0:
            return base
        try:
            from ..generators.noise import perlin2d
        except ImportError:
            return base
        # Build a 3D-ish noise by sampling perlin2d on (x+z, y) planes.
        # Target ordering is (sx, sy, sz); transpose each planar noise so the
        # repeat along the missing axis broadcasts cleanly.
        sx, sy, sz = shape
        n1 = perlin2d((sx, sy), scale=self.scale, seed=self.seed)        # (sx, sy)
        n2 = perlin2d((sz, sy), scale=self.scale, seed=self.seed + 1)    # (sz, sy)
        n3 = perlin2d((sx, sz), scale=self.scale, seed=self.seed + 2)    # (sx, sz)
        # Stack into 3D: average of the three planar noises -> (sx, sy, sz).
        noise = (n1[:, :, None].repeat(sz, axis=2) +
                 n2.T[None, :, :].repeat(sx, axis=0) +     # (sy, sz) -> (sx, sy, sz)
                 n3[:, None, :].repeat(sy, axis=1)) / 3.0
        # noise is in [0,1]; shift to [-0.5, 0.5]
        noise = noise - 0.5
        # Compute distance-from-edge approximation: dilate - erode.
        try:
            from scipy import ndimage as _ndi
        except ImportError:
            # Graceful fallback: numpy-only erosion/dilation via np.roll.
            eroded = base & np.roll(base, 1, axis=0) & np.roll(base, -1, axis=0) \
                & np.roll(base, 1, axis=1) & np.roll(base, -1, axis=1) \
                & np.roll(base, 1, axis=2) & np.roll(base, -1, axis=2)
            dilated = base | np.roll(base, 1, axis=0) | np.roll(base, -1, axis=0) \
                | np.roll(base, 1, axis=1) | np.roll(base, -1, axis=1) \
                | np.roll(base, 1, axis=2) | np.roll(base, -1, axis=2)
        else:
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

    def bounds(self, grid_shape: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
        return _shape_bounds(self.shape, grid_shape)

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
            return np.asarray(base & ~eroded)
        eroded = _ndi.binary_erosion(base, iterations=self.thickness)
        return np.asarray(base & ~eroded)
