"""Wave function collapse over a 3D voxel grid.

A tile-based WFC solver: each cell starts in a superposition of all possible
blocks; constraints propagate so neighbouring blocks agree on adjacent faces;
the lowest-entropy cell is collapsed (observed) each iteration until every
cell is decided or a contradiction is reached.

This is the simplest correct WFC: it does not attempt to be fast on big grids
(it keeps a (N, *cells) bool array of allowed blocks per cell), but it converges
or raises ``ContradictionError`` within an iteration cap. Use it for mossy
ruins, tapestries, textured surfaces -- patterns where neighbours must agree
on edges (e.g. mossy_cobblestone next to cobblestone, vines next to logs).

Example::

    from schematica.generators.wfc import WFC, TileSet, run_wfc

    tiles = TileSet([
        ("minecraft:stone",        "minecraft:stone",      "minecraft:stone"),
        ("minecraft:cobblestone",   "minecraft:mossy_cobblestone", "minecraft:cobblestone"),
    ])
    blocks = run_wfc((8, 8, 1), tiles, seed=42)
    for x in range(8):
        for z in range(8):
            session.set(x, 0, z, blocks[x, 0, z])
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class ContradictionError(RuntimeError):
    """Raised when a cell has no compatible tile and cannot collapse."""


@dataclass(frozen=True)
class Tile:
    """A single WFC tile: a 1-voxel block with an optional rotation id.

    ``block`` is the blockstate string placed when this tile is observed.
    ``edges`` is a 6-tuple of edge labels ``(+x, -x, +y, -y, +z, -z)`` used to
    check adjacency compatibility: two tiles are compatible on face F if the
    label on tile_a's +F edge equals tile_b's -F edge.
    """
    block: str
    edges: tuple[str, str, str, str, str, str] = ("*",) * 6

    def rotated(self) -> Tile:
        """Return this tile rotated 90° about Y (swap +x/+z edges)."""
        px, nx, py, ny, pz, nz = self.edges
        return Tile(block=self.block, edges=(pz, nz, py, ny, px, nx))


@dataclass
class TileSet:
    """A collection of tiles + their adjacency compatibility table.

    ``tiles`` is a list of ``Tile``. Two tiles are compatible on a face if the
    edge labels match (or either is ``"*"``, the wildcard).
    """
    tiles: list[Tile]
    _index: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = {t.block: i for i, t in enumerate(self.tiles)}

    def __len__(self) -> int:
        return len(self.tiles)

    def compatible(self, a: int, b: int, face: str) -> bool:
        """face is '+x','-x','+y','-y','+z','-z' -- the face of a touching b."""
        ta = self.tiles[a]
        tb = self.tiles[b]
        # b sits on the +x side of a => a's +x edge must match b's -x edge.
        pairs = {
            "+x": (ta.edges[0], tb.edges[1]),
            "-x": (ta.edges[1], tb.edges[0]),
            "+y": (ta.edges[2], tb.edges[3]),
            "-y": (ta.edges[3], tb.edges[2]),
            "+z": (ta.edges[4], tb.edges[5]),
            "-z": (ta.edges[5], tb.edges[4]),
        }
        ea, eb = pairs[face]
        return ea == eb or ea == "*" or eb == "*"

    def block_for(self, idx: int) -> str:
        return self.tiles[idx].block


_NEIGHBOURS = {
    "+x": (1, 0, 0),
    "-x": (-1, 0, 0),
    "+y": (0, 1, 0),
    "-y": (0, -1, 0),
    "+z": (0, 0, 1),
    "-z": (0, 0, -1),
}
_OPPOSITE = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y", "+z": "-z", "-z": "+z"}


@dataclass
class WFC:
    """Wave function collapse state over a 3D grid.

    ``wave`` is a boolean array of shape ``(n_tiles, sx, sy, sz)`` where
    ``wave[i, x, y, z]`` is True iff tile ``i`` is still allowed at that cell.
    """
    shape: tuple[int, int, int]
    tileset: TileSet
    wave: np.ndarray = field(init=False)
    rng: np.random.Generator = field(init=False)

    def __post_init__(self) -> None:
        n = len(self.tileset)
        self.wave = np.ones((n,) + self.shape, dtype=bool)
        self.rng = np.random.default_rng()

    def seed(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def _entropy(self) -> np.ndarray:
        """Count of allowed tiles per cell; collapsed cells have count 1."""
        return self.wave.sum(axis=0)

    def _propagate(self, start: tuple[int, int, int]) -> None:
        """Ban tiles that are incompatible with already-decided neighbours."""
        stack: list[tuple[int, int, int]] = [start]
        sx, sy, sz = self.shape
        while stack:
            x, y, z = stack.pop()
            cur = self.wave[:, x, y, z]
            # For each face, restrict the neighbour's wave to tiles compatible
            # with at least one allowed tile here.
            for face, (dx, dy, dz) in _NEIGHBOURS.items():
                nx, ny, nz = x + dx, y + dy, z + dz
                if not (0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz):
                    continue
                # Allowed neighbour tiles = union over allowed cur tiles of
                # tiles compatible with cur on `face`.
                allowed_here = np.where(cur)[0]
                if allowed_here.size == 0:
                    raise ContradictionError(f"cell ({x},{y},{z}) has no allowed tiles")
                allowed_nb = np.zeros(len(self.tileset), dtype=bool)
                for t in allowed_here:
                    for cand in range(len(self.tileset)):
                        if self.tileset.compatible(t, cand, face):
                            allowed_nb[cand] = True
                # If wildcard tileset, everything compatible -> skip.
                if allowed_nb.all():
                    continue
                # Restrict the neighbour.
                old = self.wave[:, nx, ny, nz].copy()
                self.wave[:, nx, ny, nz] = old & allowed_nb
                if not self.wave[:, nx, ny, nz].any():
                    raise ContradictionError(
                        f"cell ({nx},{ny},{nz}) contradicts ({x},{y},{z})"
                    )
                if not np.array_equal(old, self.wave[:, nx, ny, nz]):
                    stack.append((nx, ny, nz))

    def _collapse_lowest_entropy(self) -> tuple[int, int, int] | None:
        """Pick the uncollapsed cell with the fewest allowed tiles, observe it."""
        ent = self._entropy()
        # Uncollapsed = entropy > 1
        uncollapsed = ent > 1
        if not uncollapsed.any():
            return None
        # Mask of minimum entropy among uncollapsed.
        min_e = ent[uncollapsed].min()
        cand = (ent == min_e) & uncollapsed
        # Pick a random candidate cell.
        idxs = np.argwhere(cand)
        x, y, z = idxs[self.rng.integers(len(idxs))]
        x, y, z = int(x), int(y), int(z)
        # Observe: pick one allowed tile at random.
        allowed = np.where(self.wave[:, x, y, z])[0]
        chosen = int(self.rng.choice(allowed))
        self.wave[:, x, y, z] = False
        self.wave[chosen, x, y, z] = True
        return (x, y, z)

    def step(self) -> bool:
        """Collapse one cell and propagate. Returns False when done."""
        cell = self._collapse_lowest_entropy()
        if cell is None:
            return False
        self._propagate(cell)
        return True

    def run(self, max_iter: int = 10_000) -> np.ndarray:
        """Run to completion. Returns a (sx, sy, sz) int array of tile indices."""
        for _ in range(max_iter):
            if not self.step():
                break
        else:
            raise ContradictionError(f"did not converge in {max_iter} iterations")
        ent = self._entropy()
        if (ent != 1).any():
            raise ContradictionError("some cells remain uncollapsed")
        return self.wave.argmax(axis=0)


def run_wfc(shape: tuple[int, int, int], tileset: TileSet, *,
            seed: int = 0, max_iter: int = 10_000) -> np.ndarray:
    """Run WFC over ``shape`` with ``tileset``. Returns a (sx,sy,sz) array of
    blockstate strings ready to feed into ``Session.set``.

    Raises ``ContradictionError`` if the wave cannot collapse.
    """
    wfc = WFC(shape=shape, tileset=tileset)
    wfc.seed(seed)
    idx_grid = wfc.run(max_iter=max_iter)
    out = np.empty(shape, dtype=object)
    for x in range(shape[0]):
        for y in range(shape[1]):
            for z in range(shape[2]):
                out[x, y, z] = tileset.block_for(int(idx_grid[x, y, z]))
    return out


# ---- bundled tile sets ------------------------------------------------

_MOSSY_RUINS = TileSet([
    Tile("minecraft:stone",             ("s", "s", "s", "s", "s", "s")),
    Tile("minecraft:cobblestone",       ("c", "c", "c", "c", "c", "c")),
    Tile("minecraft:mossy_cobblestone", ("c", "c", "m", "m", "c", "c")),
    Tile("minecraft:mossy_stone_bricks",("b", "b", "m", "m", "b", "b")),
    Tile("minecraft:stone_bricks",      ("b", "b", "b", "b", "b", "b")),
    Tile("minecraft:cracked_stone_bricks", ("b", "b", "b", "b", "b", "b")),
])


def tileset_mossy_ruins() -> TileSet:
    """A stone / cobblestone / mossy brick tile set for ruined walls."""
    return _MOSSY_RUINS


def tileset_wildcard(tiles: list[str]) -> TileSet:
    """Build a permissive tileset where every tile is compatible with every
    other (all-``"*`` edges). Useful for uniform random fills with no real
    constraints but the WFC API.
    """
    return TileSet([Tile(b) for b in tiles])
