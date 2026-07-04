"""Constraint system: declarative build constraints enforced during edits.

A ``ConstraintSet`` holds a list of named constraints that are checked before
and after each session operation. If a constraint would be violated, the
operation is either rejected (pre-check) or reported (post-check).

Constraint types:

- **HeightLimit**: no solid block above Y max_y.
- **BlockBan**: certain blockstates are forbidden.
- **BlockAllowlist**: only blocks in a whitelist are allowed (except air).
- **Symmetry**: require the build to be symmetric about an axis.
- **BoxBounds**: no solid block outside a bounding box.
- **MaxBlockCount**: at most N blocks of a given name.
- **PaletteLimit**: palette size must not exceed N (for export format limits).
- **MinSolidRatio**: at least fraction of the volume must be solid.
- **MaxSolidRatio**: at most fraction of the volume may be solid.

Usage::

    from schematica.constraints import ConstraintSet, HeightLimit, BlockBan

    cs = ConstraintSet([
        HeightLimit(max_y=31),
        BlockBan({"minecraft:bedrock", "minecraft:barrier"}),
    ])
    cs.attach(session)
    # Now session.add(...) will raise ConstraintViolation if a constraint breaks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from .blocks.block import AIR, Block
from .core.chunked import ChunkedGrid
from .core.voxel import VoxelGrid

Grid = VoxelGrid | ChunkedGrid


class ConstraintViolation(Exception):
    """Raised when a constraint is violated."""
    def __init__(self, name: str, message: str) -> None:
        super().__init__(f"[{name}] {message}")
        self.constraint_name = name
        self.message = message


class Constraint(Protocol):
    """A build constraint. ``name`` identifies it; ``check`` validates a grid."""
    name: str

    def check(self, grid: Grid) -> list[str]:
        """Return a list of violation messages (empty if OK)."""
        ...


# ---- concrete constraints -----------------------------------------------

@dataclass
class HeightLimit:
    """No solid block above ``max_y`` (inclusive)."""
    max_y: int
    name: str = "height_limit"

    def check(self, grid: Grid) -> list[str]:
        sx, sy, sz = grid.shape
        if self.max_y >= sy - 1:
            return []
        dense = _dense_view(grid)
        above = dense[:, self.max_y + 1:, :]
        count = int(np.count_nonzero(above != 0))
        if count > 0:
            return [f"{count} solid voxels above y={self.max_y}"]
        return []


@dataclass
class BlockBan:
    """Certain block names are forbidden."""
    banned: set[str]
    name: str = "block_ban"

    def check(self, grid: Grid) -> list[str]:
        violations: list[str] = []
        for b in grid.palette.blocks():
            if b.name in self.banned:
                count = _count_block(grid, b)
                if count > 0:
                    violations.append(f"banned block {b.to_blockstate_str()} present ({count} voxels)")
        return violations


@dataclass
class BlockAllowlist:
    """Only blocks in the allowlist are permitted (air is always allowed)."""
    allowed: set[str]
    name: str = "block_allowlist"

    def check(self, grid: Grid) -> list[str]:
        violations: list[str] = []
        for b in grid.palette.blocks():
            if b.name == "minecraft:air":
                continue
            if b.name not in self.allowed:
                count = _count_block(grid, b)
                if count > 0:
                    violations.append(
                        f"non-allowlisted block {b.to_blockstate_str()} present ({count} voxels)"
                    )
        return violations


@dataclass
class Symmetry:
    """Require the build to be symmetric about an axis.

    ``axis`` is 0 (x), 1 (y), or 2 (z). The build must be a mirror image
    across the central plane perpendicular to that axis.
    """
    axis: int
    name: str = "symmetry"

    def check(self, grid: Grid) -> list[str]:
        dense = _dense_view(grid)
        sx, sy, sz = dense.shape
        ax = self.axis
        if ax == 0:
            flipped = dense[::-1, :, :]
        elif ax == 1:
            flipped = dense[:, ::-1, :]
        else:
            flipped = dense[:, :, ::-1]
        mismatches = int(np.count_nonzero(dense != flipped))
        if mismatches > 0:
            total = int(np.prod(dense.shape))
            return [f"not symmetric on axis {ax}: {mismatches}/{total} voxel mismatches"]
        return []


@dataclass
class BoxBounds:
    """No solid block outside the inclusive bounding box."""
    min_corner: tuple[int, int, int]
    max_corner: tuple[int, int, int]
    name: str = "box_bounds"

    def check(self, grid: Grid) -> list[str]:
        dense = _dense_view(grid)
        solid = dense != 0
        x0, y0, z0 = self.min_corner
        x1, y1, z1 = self.max_corner
        sx, sy, sz = dense.shape
        outside = np.ones(dense.shape, dtype=bool)
        outside[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1] = False
        count = int(np.count_nonzero(solid & outside))
        if count > 0:
            return [f"{count} solid voxels outside bounds {self.min_corner}..{self.max_corner}"]
        return []


@dataclass
class MaxBlockCount:
    """At most ``max_count`` voxels of the given block name."""
    block_name: str
    max_count: int
    name: str = "max_block_count"

    def check(self, grid: Grid) -> list[str]:
        total = 0
        for b in grid.palette.blocks():
            if b.name == self.block_name:
                total += _count_block(grid, b)
        if total > self.max_count:
            return [f"block {self.block_name} has {total} voxels (max {self.max_count})"]
        return []


@dataclass
class PaletteLimit:
    """Palette size (including air) must not exceed ``max_size``."""
    max_size: int
    name: str = "palette_limit"

    def check(self, grid: Grid) -> list[str]:
        size = len(grid.palette)
        if size > self.max_size:
            return [f"palette has {size} entries (max {self.max_size})"]
        return []


@dataclass
class SolidRatio:
    """Solid volume fraction must be between ``min_frac`` and ``max_frac``."""
    min_frac: float = 0.0
    max_frac: float = 1.0
    name: str = "solid_ratio"

    def check(self, grid: Grid) -> list[str]:
        dense = _dense_view(grid)
        total = int(np.prod(dense.shape))
        solid = int(np.count_nonzero(dense != 0))
        frac = solid / max(total, 1)
        violations: list[str] = []
        if frac < self.min_frac:
            violations.append(f"solid ratio {frac:.3f} < min {self.min_frac:.3f}")
        if frac > self.max_frac:
            violations.append(f"solid ratio {frac:.3f} > max {self.max_frac:.3f}")
        return violations


# ---- constraint set -----------------------------------------------------

@dataclass
class ConstraintSet:
    """A collection of constraints that can be attached to a session."""
    constraints: list[Constraint] = field(default_factory=list)
    _session: Any = None
    _original_record: Any = None

    def add(self, constraint: Constraint) -> ConstraintSet:
        self.constraints.append(constraint)
        return self

    def check_all(self, grid: Grid) -> dict[str, list[str]]:
        """Run all constraints and return ``{name: [messages]}`` for violations."""
        results: dict[str, list[str]] = {}
        for c in self.constraints:
            msgs = c.check(grid)
            if msgs:
                results[c.name] = msgs
        return results

    def check_or_raise(self, grid: Grid) -> None:
        """Raise ``ConstraintViolation`` if any constraint fails."""
        for c in self.constraints:
            msgs = c.check(grid)
            if msgs:
                raise ConstraintViolation(c.name, "; ".join(msgs))

    def attach(self, session: Any) -> None:
        """Attach to a session, wrapping its ``_record`` to enforce constraints.

        After attaching, every dense-grid operation that calls ``_record`` will
        be validated. If a constraint is violated, the operation's history delta
        is undone and ``ConstraintViolation`` is raised.

        Only works for dense (non-chunked) sessions.
        """
        self._session = session
        if session.is_chunked:
            # For chunked sessions we can't easily intercept; just store for
            # manual ``check_or_raise`` calls.
            return
        original = session._record

        def guarded_record(new_data: np.ndarray) -> None:
            # Save the old data so we can restore it if a constraint fails.
            old_data = session.grid.data
            # Temporarily set new_data so constraints see the post-op state.
            session.grid.data = new_data
            try:
                violations = self.check_all(session.grid)
                if violations:
                    # Restore old data before raising.
                    session.grid.data = old_data
                    name = next(iter(violations))
                    raise ConstraintViolation(name, "; ".join(violations[name]))
            except Exception:
                session.grid.data = old_data
                raise
            # All clear: call the original _record.
            session.grid.data = old_data
            original(new_data)

        session._record = guarded_record
        self._original_record = original

    def detach(self) -> None:
        """Restore the session's original ``_record`` method."""
        if self._session and self._original_record:
            self._session._record = self._original_record
            self._original_record = None


# ---- helpers ------------------------------------------------------------

def _dense_view(grid: Grid) -> np.ndarray:
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data


def _count_block(grid: Grid, block: Block) -> int:
    idx = grid.palette.index_of(block)
    if idx is None:
        return 0
    dense = _dense_view(grid)
    return int(np.count_nonzero(dense == idx))