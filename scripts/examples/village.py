"""Example: a small village -- several houses on a plaza, chunked for scale.

Run with:  python -m examples.village
Output:     village.schem + village_previews/
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schematica.session.session import Session
from schematica.shapes.primitives import Box, Cylinder
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview


def house(s: Session, ox: int, oy: int, oz: int, *, w: int = 6, h: int = 4,
          d: int = 6, wall: str = "minecraft:oak_planks",
          roof: str = "minecraft:red_wool") -> None:
    """Build a small house: hollow walls + a roof slab."""
    s.add(Box(ox, oy, oz, ox + w, oy + h, oz + d, hollow=True), wall)
    # Roof: a single-slab cap.
    s.add(Box(ox, oy + h + 1, oz, ox + w, oy + h + 1, oz + d), roof)


def main() -> None:
    # 96x32x96 village plaza on a chunked grid (6x6x6 chunks possible, but
    # only the ones we build in get allocated).
    s = Session.new((96, 32, 96), version="1.20.1", chunked=True, chunk_size=16)
    # Stone plaza.
    s.add(Box(0, 0, 0, 95, 0, 95), "minecraft:stone")
    # A few houses spaced around.
    house(s, 8, 1, 8, w=8, h=5, d=8)
    house(s, 40, 1, 10, w=10, h=6, d=8, wall="minecraft:bricks",
          roof="minecraft:blue_wool")
    house(s, 70, 1, 30, w=12, h=7, d=10, wall="minecraft:stone_bricks",
          roof="minecraft:black_wool")
    house(s, 20, 1, 60, w=8, h=4, d=8)
    # A central well.
    s.add(Cylinder(48, 1, 48, 2, 3, hollow=True), "minecraft:cobblestone")

    write_sponge(s.grid, "village.schem")
    preview(s.grid, "village_previews")
    st = s.stats()
    print(f"Wrote village.schem ({st['chunks']} chunks, {st['solid']} solid, "
          f"{st['memory_bytes']}B)")


if __name__ == "__main__":
    main()