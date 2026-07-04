"""Spatial planning utilities: walkability, clearance, connectivity checks.

These tools analyse the 3D voxel grid to answer questions about the build's
usability for gameplay:

- **Walkability**: is a voxel position walkable (solid below, air above)?
- **Clearance**: does a position have enough headroom for a player?
- **Connectivity**: are two positions reachable by walking on the surface?
- **Reachable area**: flood-fill the walkable surface from a starting point.

They operate read-only on the grid and do not modify it.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

Grid = VoxelGrid | ChunkedGrid

# Blocks that are considered "solid" (walkable floor) but not full cubes.
# These are treated as solid for floor detection but NOT as headroom blockers.
# By default we treat any non-air block as solid. Callers can customise.
_NON_SOLID_NAMES = frozenset({
    "minecraft:air",
    "minecraft:water",
    "minecraft:lava",
    "minecraft:torch",
    "minecraft:wall_torch",
    "minecraft:redstone_torch",
    "minecraft:redstone_wall_torch",
    "minecraft:snow",
    "minecraft:vine",
    "minecraft:lily_pad",
    "minecraft:fern",
    "minecraft:grass",
    "minecraft:dead_bush",
    "minecraft:flower",
    "minecraft:dandelion",
    "minecraft:poppy",
    "minecraft:azure_bluet",
    "minecraft:cornflower",
    "minecraft:orchid",
    "minecraft:allium",
    "minecraft:oxeye_daisy",
    "minecraft:wither_rose",
    "minecraft:ladder",
    "minecraft:scaffolding",
    "minecraft:cobweb",
})

# Blocks that are non-solid for headroom checks (player can walk through).
_PASSABLE_NAMES = _NON_SOLID_NAMES | frozenset({
    "minecraft:oak_sign", "minecraft:spruce_sign", "minecraft:birch_sign",
    "minecraft:jungle_sign", "minecraft:acacia_sign", "minecraft:dark_oak_sign",
    "minecraft:oak_wall_sign", "minecraft:spruce_wall_sign",
    "minecraft:birch_wall_sign", "minecraft:jungle_wall_sign",
    "minecraft:acacia_wall_sign", "minecraft:oak_hanging_sign", "minecraft:spruce_hanging_sign",
    "minecraft:birch_hanging_sign", "minecraft:jungle_hanging_sign",
    "minecraft:acacia_hanging_sign", "minecraft:dark_oak_hanging_sign",
    "minecraft:rail", "minecraft:powered_rail", "minecraft:detector_rail",
    "minecraft:activator_rail",
    "minecraft:redstone_wire",
    "minecraft:lever",
    "minecraft:stone_button", "minecraft:oak_button",
    "minecraft:stone_pressure_plate", "minecraft:oak_pressure_plate",
    "minecraft:tripwire", "minecraft:tripwire_hook",
    "minecraft:carpet",
    "minecraft:white_carpet", "minecraft:orange_carpet",
})


def _is_solid_block(grid: Grid, x: int, y: int, z: int) -> bool:
    """Return True if the voxel at (x,y,z) is a solid, walkable block."""
    sx, sy, sz = grid.shape
    if not (0 <= x < sx and 0 <= y < sy and 0 <= z < sz):
        return False
    b = grid.get(x, y, z)
    return b.name not in _NON_SOLID_NAMES


def _is_passable(grid: Grid, x: int, y: int, z: int) -> bool:
    """Return True if the voxel at (x,y,z) does not block player movement."""
    sx, sy, sz = grid.shape
    if not (0 <= x < sx and 0 <= y < sy and 0 <= z < sz):
        return False  # out of bounds = wall
    b = grid.get(x, y, z)
    return b.name in _PASSABLE_NAMES


def walkable_at(grid: Grid, x: int, y: int, z: int) -> bool:
    """Return True if a player can stand at (x, y, z).

    A position is walkable if:
    - The voxel at (x, y, z) is passable (air or non-blocking).
    - The voxel at (x, y+1, z) is also passable (headroom).
    - The voxel at (x, y-1, z) is solid (floor to stand on).
    """
    if not _is_passable(grid, x, y, z):
        return False
    if not _is_passable(grid, x, y + 1, z):
        return False
    if not _is_solid_block(grid, x, y - 1, z):
        return False
    return True


def clearance_at(grid: Grid, x: int, y: int, z: int, *, height: int = 2) -> int:
    """Return the vertical clearance (free blocks above) starting at (x,y,z).

    Counts consecutive passable blocks from y upward, up to ``height``.
    Returns 0 if (x,y,z) itself is not passable.
    """
    sx, sy, sz = grid.shape
    if not (0 <= x < sx and 0 <= y < sy and 0 <= z < sz):
        return 0
    count = 0
    for dy in range(height):
        cy = y + dy
        if cy >= sy:
            break
        if not _is_passable(grid, x, cy, z):
            break
        count += 1
    return count


def walkable_map(grid: Grid, *, floor_y: int | None = None) -> np.ndarray:
    """Return a 2D boolean array of walkable positions at a given Y level.

    If ``floor_y`` is given, checks if players can stand at that Y (air at
    floor_y, solid at floor_y - 1). If None, scans all Y levels and returns
    a 2D (x, z) map where True means at least one walkable Y exists in that
    column.
    """
    sx, sy, sz = grid.shape
    if floor_y is not None:
        out = np.zeros((sx, sz), dtype=bool)
        for x in range(sx):
            for z in range(sz):
                if walkable_at(grid, x, floor_y, z):
                    out[x, z] = True
        return out
    # Scan all Y levels.
    out = np.zeros((sx, sz), dtype=bool)
    for y in range(sy):
        for x in range(sx):
            for z in range(sz):
                if out[x, z]:
                    continue
                if walkable_at(grid, x, y, z):
                    out[x, z] = True
    return out


def reachable_area(grid: Grid, start: tuple[int, int, int],
                   *, max_steps: int = 0) -> np.ndarray:
    """Flood-fill walkable positions reachable from ``start`` by walking.

    Movement allows:
    - Horizontal steps (N/S/E/W) to adjacent walkable positions at the same Y.
    - Step up 1 block (if destination +1 Y is walkable).
    - Step down 1 block (if destination -1 Y is walkable and has clearance).
    - No jumping more than 1 block.

    Returns a 3D boolean array marking all reachable walkable voxels.
    If ``max_steps`` > 0, limits the BFS to that many steps.
    """
    sx, sy, sz = grid.shape
    visited = np.zeros((sx, sy, sz), dtype=bool)
    sx0, sy0, sz0 = start
    if not (0 <= sx0 < sx and 0 <= sy0 < sy and 0 <= sz0 < sz):
        return visited
    if not walkable_at(grid, sx0, sy0, sz0):
        return visited

    queue: deque[tuple[int, int, int, int]] = deque()
    queue.append((sx0, sy0, sz0, 0))
    visited[sx0, sy0, sz0] = True

    # 4 horizontal directions + 2 vertical (up/down by 1).
    moves = [
        (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1),  # horizontal
        (0, 1, 0), (0, -1, 0),  # vertical step up/down
    ]

    while queue:
        cx, cy, cz, dist = queue.popleft()
        if max_steps > 0 and dist >= max_steps:
            continue
        for dx, dy, dz in moves:
            nx, ny, nz = cx + dx, cy + dy, cz + dz
            if not (0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz):
                continue
            if visited[nx, ny, nz]:
                continue
            if not walkable_at(grid, nx, ny, nz):
                continue
            visited[nx, ny, nz] = True
            queue.append((nx, ny, nz, dist + 1))

    return visited


def is_connected(grid: Grid, a: tuple[int, int, int],
                 b: tuple[int, int, int]) -> bool:
    """Return True if a player can walk from position ``a`` to position ``b``."""
    reached = reachable_area(grid, a)
    return bool(reached[b[0], b[1], b[2]])


def shortest_path(grid: Grid, a: tuple[int, int, int],
                  b: tuple[int, int, int]) -> list[tuple[int, int, int]] | None:
    """BFS shortest walking path from ``a`` to ``b``.

    Returns the list of (x, y, z) positions from start to end (inclusive),
    or None if unreachable.
    """
    sx, sy, sz = grid.shape
    ax, ay, az = a
    bx, by, bz = b
    if not (0 <= ax < sx and 0 <= ay < sy and 0 <= az < sz):
        return None
    if not (0 <= bx < sx and 0 <= by < sy and 0 <= bz < sz):
        return None
    if not walkable_at(grid, ax, ay, az) or not walkable_at(grid, bx, by, bz):
        return None

    visited = np.zeros((sx, sy, sz), dtype=bool)
    parent: dict[tuple[int, int, int], tuple[int, int, int] | None] = {}
    queue: deque[tuple[int, int, int]] = deque()
    queue.append((ax, ay, az))
    visited[ax, ay, az] = True
    parent[(ax, ay, az)] = None

    moves = [
        (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1),
        (0, 1, 0), (0, -1, 0),
    ]

    found = False
    while queue:
        cx, cy, cz = queue.popleft()
        if (cx, cy, cz) == (bx, by, bz):
            found = True
            break
        for dx, dy, dz in moves:
            nx, ny, nz = cx + dx, cy + dy, cz + dz
            if not (0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz):
                continue
            if visited[nx, ny, nz]:
                continue
            if not walkable_at(grid, nx, ny, nz):
                continue
            visited[nx, ny, nz] = True
            parent[(nx, ny, nz)] = (cx, cy, cz)
            queue.append((nx, ny, nz))

    if not found:
        return None

    # Reconstruct path.
    path: list[tuple[int, int, int]] = []
    cur: tuple[int, int, int] | None = (bx, by, bz)
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def _dense_view(grid: Grid) -> np.ndarray:
    """Return the dense uint16 data array (read-only is fine)."""
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data
