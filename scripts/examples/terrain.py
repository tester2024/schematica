"""Example: procedural terrain with a few trees, exported as a chunked map.

Demonstrates the chunked backend for bigger maps: a 64x32x64 terrain where
only the chunks containing solid voxels are allocated.

Run with:  python -m examples.terrain
Output:     terrain.schem + terrain_previews/
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schematica.session.session import Session
from schematica.generators.templates import apply_terrain, apply_tree
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview


def main() -> None:
    # Chunked backend: only touched chunks are allocated, so a 64x32x64 map
    # with sparse terrain costs a few KB, not 256 KB dense.
    s = Session.new((64, 32, 64), version="1.20.1", chunked=True, chunk_size=16)
    apply_terrain(s, seed=7, amplitude=6)
    # Scatter a few trees.
    for (x, z) in [(10, 10), (40, 12), (20, 50), (55, 55), (30, 30)]:
        apply_tree(s, x=x, z=z, height=6)

    write_sponge(s.grid, "terrain.schem")
    preview(s.grid, "terrain_previews")
    st = s.stats()
    print(f"Wrote terrain.schem ({st['chunks']} chunks, {st['solid']} solid, "
          f"{st['memory_bytes']}B)")


if __name__ == "__main__":
    main()