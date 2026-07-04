"""Tests for spatial planning utilities: walkability, clearance, connectivity."""
from __future__ import annotations

from schematica.analysis.spatial import (
    clearance_at,
    is_connected,
    reachable_area,
    shortest_path,
    walkable_at,
    walkable_map,
)
from schematica.cli.repl import dispatch
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _floor_and_walls():
    """Build a 8x8x8 room with a stone floor at y=0 and walls on the perimeter."""
    s = Session.new((8, 8, 8))
    # Floor at y=0.
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    # Walls around the perimeter (x=0, x=7, z=0, z=7) from y=1 to y=3.
    s.add(Box(0, 1, 0, 0, 3, 7), "minecraft:stone")  # x=0 wall
    s.add(Box(7, 1, 0, 7, 3, 7), "minecraft:stone")  # x=7 wall
    s.add(Box(0, 1, 0, 7, 3, 0), "minecraft:stone")  # z=0 wall
    s.add(Box(0, 1, 7, 7, 3, 7), "minecraft:stone")  # z=7 wall
    return s


def test_walkable_at_floor():
    s = _floor_and_walls()
    # At (1, 1, 1): floor below (y=0 = stone), air at y=1 and y=2.
    assert walkable_at(s.grid, 1, 1, 1) is True
    # At (0, 1, 0): wall block, not walkable.
    assert walkable_at(s.grid, 0, 1, 0) is False
    # At (4, 0, 4): floor block itself, not walkable (need air at y=0).
    assert walkable_at(s.grid, 4, 0, 4) is False
    # At (4, 1, 4): air above floor = walkable.
    assert walkable_at(s.grid, 4, 1, 4) is True


def test_walkable_at_out_of_bounds():
    s = _floor_and_walls()
    assert walkable_at(s.grid, -1, 0, 0) is False
    assert walkable_at(s.grid, 0, 99, 0) is False


def test_clearance_at():
    s = _floor_and_walls()
    # At (4, 1, 4) with floor at y=0: clearance should be high (no ceiling).
    assert clearance_at(s.grid, 4, 1, 4, height=5) == 5
    # At (1, 1, 1) inside the room: walls are at y=1-3 but (1,1,1) is interior.
    # The room has no ceiling, so clearance goes all the way up.
    assert clearance_at(s.grid, 1, 1, 1, height=7) == 7


def test_walkable_map_floor_level():
    s = _floor_and_walls()
    wm = walkable_map(s.grid, floor_y=1)
    # Interior positions (1-6, 1-6) should be walkable.
    assert bool(wm[1, 1]) is True
    assert bool(wm[4, 4]) is True
    # Wall positions should not be walkable.
    assert bool(wm[0, 0]) is False
    assert bool(wm[7, 7]) is False


def test_reachable_area_open_room():
    s = _floor_and_walls()
    mask = reachable_area(s.grid, (1, 1, 1))
    # All interior floor positions should be reachable.
    # Interior is x=1..6, z=1..6 = 36 positions.
    count = int(mask.sum())
    assert count == 36


def test_is_connected_adjacent():
    s = _floor_and_walls()
    assert is_connected(s.grid, (1, 1, 1), (2, 1, 1)) is True
    assert is_connected(s.grid, (1, 1, 1), (6, 1, 6)) is True


def test_is_connected_blocked():
    """Two areas separated by a wall should not be connected."""
    s = Session.new((8, 8, 8))
    # Floor.
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    # Wall dividing the room at x=4, from y=1 to y=3.
    s.add(Box(4, 1, 0, 4, 3, 7), "minecraft:stone")
    assert is_connected(s.grid, (1, 1, 1), (6, 1, 1)) is False
    # But within the same side, should be connected.
    assert is_connected(s.grid, (1, 1, 1), (3, 1, 6)) is True


def test_shortest_path():
    s = _floor_and_walls()
    path = shortest_path(s.grid, (1, 1, 1), (6, 1, 6))
    assert path is not None
    assert path[0] == (1, 1, 1)
    assert path[-1] == (6, 1, 6)
    # Path has 10 steps = 11 nodes (including start and end).
    assert len(path) == 11  # |6-1| + |6-1| + 1 (start) = 11


def test_shortest_path_unreachable():
    s = Session.new((8, 8, 8))
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    s.add(Box(4, 1, 0, 4, 3, 7), "minecraft:stone")
    path = shortest_path(s.grid, (1, 1, 1), (6, 1, 1))
    assert path is None


def test_dispatch_walkable():
    s = _floor_and_walls()
    r = dispatch(s, "walkable x=4 y=1 z=4")
    assert "walkable=True" in r


def test_dispatch_connected():
    s = _floor_and_walls()
    r = dispatch(s, "connected a=1,1,1 b=6,1,6")
    assert "connected=True" in r


def test_dispatch_reachable():
    s = _floor_and_walls()
    r = dispatch(s, "reachable x=1 y=1 z=1")
    assert "reachable area" in r


def test_dispatch_path():
    s = _floor_and_walls()
    r = dispatch(s, "path a=1,1,1 b=6,1,6")
    assert "path" in r and "11" in r
