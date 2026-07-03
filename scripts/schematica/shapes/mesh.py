"""Voxelize arbitrary meshes (OBJ/STL/glTF) into VoxelGrid masks via trimesh."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class MeshShape:
    mesh: object  # trimesh.Trimesh
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: float = 1.0

    def mask(self, shape: tuple[int, int, int]) -> np.ndarray:
        import trimesh

        m = self.mesh.copy()
        m.apply_scale(self.scale)
        ox, oy, oz = self.origin
        m.apply_translation((ox, oy, oz))
        # Use trimesh voxelization aligned to grid cells.
        vg = trimesh.voxelize.VoxelGrid(m, pitch=1.0)
        # vg.matrix is (nx, ny, nz) bool with origin vg.origin
        mat = vg.matrix
        o = vg.origin
        out = np.zeros(shape, dtype=bool)
        # Place matrix into out at floor(origin)
        ox0 = int(np.floor(o[0]))
        oy0 = int(np.floor(o[1]))
        oz0 = int(np.floor(o[2]))
        nx, ny, nz = mat.shape
        i0 = max(0, -ox0)
        j0 = max(0, -oy0)
        k0 = max(0, -oz0)
        di = min(nx - i0, shape[0] - max(ox0, 0))
        dj = min(ny - j0, shape[1] - max(oy0, 0))
        dk = min(nz - k0, shape[2] - max(oz0, 0))
        if di <= 0 or dj <= 0 or dk <= 0:
            return out
        out[max(ox0, 0):max(ox0, 0) + di,
            max(oy0, 0):max(oy0, 0) + dj,
            max(oz0, 0):max(oz0, 0) + dk] = mat[i0:i0 + di, j0:j0 + dj, k0:k0 + dk]
        return out


def load_mesh(path: str | Path, origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
              scale: float = 1.0) -> MeshShape:
    import trimesh

    m = trimesh.load(Path(path), force="mesh")
    return MeshShape(mesh=m, origin=origin, scale=scale)
