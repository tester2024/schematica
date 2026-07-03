"""Example: build a small castle with towers, walls, and a staircase.

Run with:  python -m examples.castle
Output:     castle.schem + castle_previews/ in the current directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schematica.session.session import Session
from schematica.shapes.primitives import Box, Cylinder, Dome, Staircase
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview


def main() -> None:
    s = Session.new((32, 32, 32), version="1.20.1")
    # Hollow outer walls.
    s.add(Box(2, 1, 2, 29, 12, 29, hollow=True), "minecraft:stone")
    # Four corner towers + glass domes.
    for cx, cz in [(2, 2), (29, 2), (2, 29), (29, 29)]:
        s.add(Cylinder(cx, cz, 2, 1, 16, hollow=True), "minecraft:stone")
        s.add(Dome(cx, 17, cz, 2), "minecraft:purple_stained_glass")
    # Internal staircase.
    s.add(Staircase(4, 1, 4, 12, step_width=2, step_depth=1, axis="x"),
          "minecraft:oak_planks")
    # Gate: carve a doorway, leave an arch above.
    s.subtract(Box(14, 1, 2, 17, 5, 2))

    write_sponge(s.grid, "castle.schem")
    preview(s.grid, "castle_previews")
    print("Wrote castle.schem and castle_previews/")


if __name__ == "__main__":
    main()