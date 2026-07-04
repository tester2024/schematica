"""Write Sponge schematic v2/v3 (.schem) via nbtlib.

Sponge v2 spec (data version 2):
  Named root tag "Schematic":
    Version (int)
    Width, Height, Length (short)
    DataVersion (int)
    Palette (compound: blockstate_str -> int)
    PaletteMax (int)
    BlockData (byte array, varint-block-per-volume)
    Metadata (optional)
    Offset (int array of 3)

Supports both ``VoxelGrid`` (dense) and ``ChunkedGrid`` (sparse). For chunked
grids the encoder streams voxels in XZY order without ever allocating a full
dense array: it stitches chunk-local arrays into the varint stream one Y-row
at a time, keeping peak memory bounded by ``chunk_size**2``.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import nbtlib
import numpy as np
from nbtlib import Byte, ByteArray, Compound, Int, IntArray, List, Short

from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

_PRE_FLATTENING_DATA_VERSION = 1451
_MODERN_ONLY_PREFIXES = (
    "white_", "orange_", "magenta_", "light_blue_", "yellow_", "lime_",
    "pink_", "gray_", "light_gray_", "cyan_", "purple_", "blue_", "brown_",
    "green_", "red_", "black_",
)
_MODERN_ONLY_SUFFIXES = ("_wool", "_stained_glass", "_terracotta", "_concrete")


def _varint_encode(value: int) -> bytes:
    out = bytearray()
    v = value & 0xFFFFFFFF
    while True:
        if (v & ~0x7F) == 0:
            out.append(v & 0x7F)
            break
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(out)


def _encode_block_data_dense(grid: VoxelGrid) -> bytes:
    """Encode palette indices in XZY order with per-block varint."""
    data = grid.data
    sx, sy, sz = grid.shape
    out = bytearray()
    flat = np.zeros(sx * sy * sz, dtype=np.uint32)
    idx = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                flat[idx] = data[x, y, z]
                idx += 1
    for v in flat:
        out += _varint_encode(int(v))
    return bytes(out)


def _encode_block_data_chunked(grid: ChunkedGrid) -> bytes:
    """Stream XZY varint block data without materialising a full dense array.

    Sponge ordering: index = (y*length + z)*width + x, i.e. outer y, then z,
    then x. For each (y, z, x) we look up the chunk that owns (x, y, z); if the
    chunk exists, read the local voxel; otherwise emit air (0).

    To avoid per-voxel chunk lookups we iterate chunk-by-chunk in XZ stripes per
    Y-row: build the Y-row's (sx, sz) plane from touched chunks, then emit in
    the required order.
    """
    sx, sy, sz = grid.shape
    cs = grid.chunk_size
    out = bytearray()
    # Pre-bucket chunks by cy for fast per-Y-row access.
    chunks_by_cy: dict[int, dict[tuple[int, int], np.ndarray]] = {}
    for (cx, cy, cz), arr in grid._chunks.items():
        chunks_by_cy.setdefault(cy, {})[(cx, cz)] = arr
    for y in range(sy):
        cy = y // cs
        ly = y % cs
        row_chunks = chunks_by_cy.get(cy, {})
        if not row_chunks:
            # Whole Y-row is air.
            out += b"\x00" * (sx * sz)
            continue
        # Build the (sx, sz) plane for this Y.
        plane = np.zeros((sx, sz), dtype=np.uint16)
        for (cx, cz), arr in row_chunks.items():
            ox = cx * cs
            oz = cz * cs
            sx_a, sy_a, sz_a = arr.shape
            if ly >= sy_a:
                continue
            plane[ox:ox + sx_a, oz:oz + sz_a] = arr[:, ly, :]
        # Emit in z-outer, x-inner order.
        for z in range(sz):
            for x in range(sx):
                out += _varint_encode(int(plane[x, z]))
    return bytes(out)


def write_sponge(grid: VoxelGrid | ChunkedGrid, path: str | Path, *, data_version: int = 3465,
                  offset: tuple[int, int, int] = (0, 0, 0),
                  metadata: dict[str, Any] | None = None) -> Path:
    """Write a Sponge schematic (.schem) for the given grid.

    data_version 3465 ≈ MC 1.20.1. Works with dense VoxelGrid or sparse
    ChunkedGrid; the latter streams without a full dense allocation.
    """
    path = Path(path)
    sx, sy, sz = grid.shape
    palette = grid.palette
    _warn_on_legacy_palette(data_version, [b.to_blockstate_str() for b in palette.blocks()])
    palette_comp: dict[str, nbtlib.Int] = {}
    for i, b in enumerate(palette.blocks()):
        palette_comp[b.to_blockstate_str()] = Int(i)
    if isinstance(grid, ChunkedGrid):
        block_bytes = _encode_block_data_chunked(grid)
    else:
        block_bytes = _encode_block_data_dense(grid)
    root = Compound({
        "Version": Int(2),
        "DataVersion": Int(data_version),
        "Width": Short(sx),
        "Height": Short(sy),
        "Length": Short(sz),
        "PaletteMax": Int(len(palette)),
        "Palette": Compound(palette_comp),
        "BlockData": ByteArray([b if b < 128 else b - 256 for b in block_bytes]),
        "Offset": IntArray([Int(offset[0]), Int(offset[1]), Int(offset[2])]),
    })
    if metadata:
        root["Metadata"] = Compound({k: _to_nbt(v) for k, v in metadata.items()})
    file = nbtlib.File(root, gzipped=True, root_name="Schematic")
    file.save(path)
    return path


def _warn_on_legacy_palette(data_version: int, blockstates: list[str]) -> None:
    if data_version >= _PRE_FLATTENING_DATA_VERSION:
        return
    risky: list[str] = []
    for blockstate in blockstates:
        name = blockstate.split("[", 1)[0].removeprefix("minecraft:")
        if "[" in blockstate or (
            name.startswith(_MODERN_ONLY_PREFIXES) and name.endswith(_MODERN_ONLY_SUFFIXES)
        ):
            risky.append(blockstate)
    if risky:
        sample = ", ".join(risky[:5])
        warnings.warn(
            f"data_version={data_version} is pre-1.13, but the palette contains "
            f"modern blockstates ({sample}); use MCEdit export for legacy metadata "
            f"or a post-flattening data_version",
            RuntimeWarning,
            stacklevel=2,
        )


def _to_nbt(v: object) -> object:
    if isinstance(v, bool):
        return Byte(1 if v else 0)
    if isinstance(v, int):
        return Int(v)
    if isinstance(v, str):
        return nbtlib.String(v)
    if isinstance(v, dict):
        return Compound({k: _to_nbt(val) for k, val in v.items()})
    if isinstance(v, (list, tuple)):
        return List([_to_nbt(x) for x in v])
    raise TypeError(f"unsupported NBT type {type(v)}")
