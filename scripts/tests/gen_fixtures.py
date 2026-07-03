"""Generate golden fixture files for regression tests.

Run this script once (or after an intentional format change) to refresh the
golden artifacts under ``tests/fixtures/``::

    python -m tests.gen_fixtures
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schematica.export.litematic import write_litematic
from schematica.export.mcedit import write_mcedit
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere


FIX = Path(__file__).resolve().parent / "fixtures"


def build_stone_pillar() -> Session:
    s = Session.new((8, 8, 8), version="1.20.1")
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    s.add(Sphere(4, 4, 4, 2), "minecraft:dirt")
    return s


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    s = build_stone_pillar()
    write_sponge(s.grid, FIX / "stone_pillar.schem")
    write_mcedit(s.grid, FIX / "stone_pillar.schematic")
    write_litematic(s.grid, FIX / "stone_pillar.litematic")
    preview(s.grid, FIX / "stone_pillar_previews")
    print(f"Wrote fixtures to {FIX}")


if __name__ == "__main__":
    main()