"""Golden fixture regression tests.

Verifies that export output and preview PNGs match committed golden
artifacts under ``tests/fixtures/``. Intentional format changes should be
refreshed with ``python -m tests.gen_fixtures``.

PNG regression uses a perceptual dhash (via Pillow) so tiny renderer
differences (anti-aliasing, matplotlib version drift) do not cause spurious
failures; only substantial visual changes trip the test.
"""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from schematica.export.litematic import write_litematic
from schematica.export.mcedit import write_mcedit
from schematica.export.sponge import write_sponge
from schematica.render.preview import preview
from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere

FIX = Path(__file__).resolve().parent / "fixtures"


def _build_stone_pillar() -> Session:
    s = Session.new((8, 8, 8), version="1.20.1")
    s.add(Box(0, 0, 0, 7, 0, 7), "minecraft:stone")
    s.add(Sphere(4, 4, 4, 2), "minecraft:dirt")
    return s


def _dhash(path: Path, hash_size: int = 8) -> int:
    """Compute a perceptual dhash of an image (Pillow). Returns an int.

    Based on the standard imagehash dhash: resize to (hash_size+1, hash_size),
    grayscale, then compare adjacent pixels per row.
    """
    from PIL import Image

    img = Image.open(path).convert("L").resize((hash_size + 1, hash_size))
    px = list(img.tobytes())  # grayscale bytes, width*(hash_size) values
    width = hash_size + 1
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = px[row * width + col]
            right = px[row * width + col + 1]
            bits = (bits << 1) | (1 if right > left else 0)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---- byte-equal export golden tests -----------------------------------
#
# We compare the *decompressed* NBT payload, not the raw gzip bytes, because
# gzip embeds a timestamp and OS byte in its header that varies run-to-run.

def _read_schem_nbt(path: Path) -> bytes:
    return gzip.decompress(path.read_bytes())


@pytest.mark.golden
def test_golden_sponge_byte_equal(tmp_path):
    s = _build_stone_pillar()
    out = tmp_path / "stone_pillar.schem"
    write_sponge(s.grid, out)
    golden = FIX / "stone_pillar.schem"
    assert golden.exists(), "run `python -m tests.gen_fixtures` first"
    assert _read_schem_nbt(out) == _read_schem_nbt(golden)


@pytest.mark.golden
def test_golden_mcedit_byte_equal(tmp_path):
    s = _build_stone_pillar()
    out = tmp_path / "stone_pillar.schematic"
    write_mcedit(s.grid, out)
    golden = FIX / "stone_pillar.schematic"
    assert golden.exists()
    assert _read_schem_nbt(out) == _read_schem_nbt(golden)


@pytest.mark.golden
def test_golden_litematic_byte_equal(tmp_path):
    s = _build_stone_pillar()
    out = tmp_path / "stone_pillar.litematic"
    write_litematic(s.grid, out)
    golden = FIX / "stone_pillar.litematic"
    assert golden.exists()
    assert _read_schem_nbt(out) == _read_schem_nbt(golden)


# ---- PNG perceptual regression (dhash) --------------------------------

@pytest.mark.golden
@pytest.mark.parametrize("view", ["top", "front", "right", "iso"])
def test_golden_preview_dhash(tmp_path, view):
    s = _build_stone_pillar()
    out_dir = tmp_path / "previews"
    preview(s.grid, out_dir)
    golden = FIX / "stone_pillar_previews" / f"preview_{view}.png"
    assert golden.exists(), "run `python -m tests.gen_fixtures` first"
    new = out_dir / f"preview_{view}.png"
    # dhash distance should be small (allow minor renderer drift).
    dist = _hamming(_dhash(new), _dhash(golden))
    assert dist <= 4, f"preview {view} dhash distance {dist} > 4 (golden drift)"
