"""Write Sponge schematic v2/v3 (.schem) via nbtlib.

Sponge v2 spec (data version 2):
  Root tag "Schematic":
    Width, Height, Length (short)
    DataVersion (int)
    Palette (compound: blockstate_str -> int)
    PaletteMax (int)
    BlockData (byte array, varint-block-per-volume)
    Metadata (optional)
    Offset (int array of 3)
"""
from __future__ import annotations

from pathlib import Path

import nbtlib
import numpy as np
from nbtlib import Byte, ByteArray, Compound, Int, IntArray, List, Short

from ..core.voxel import VoxelGrid


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


def _encode_block_data(grid: VoxelGrid) -> bytes:
    """Encode palette indices in XZY order with per-block varint."""
    # Sponge block ordering: for x in width: for y in height: for z in length
    data = grid.data
    sx, sy, sz = grid.shape
    out = bytearray()
    # reshape to (y, z, x) ? Spec: index = (y*length + z)*width + x
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


def write_sponge(grid: VoxelGrid, path: str | Path, *, data_version: int = 3465,
                 offset: tuple[int, int, int] = (0, 0, 0),
                 metadata: dict | None = None) -> Path:
    """Write a Sponge schematic (.schem) for the given grid.

    data_version 3465 ≈ MC 1.20.1.
    """
    path = Path(path)
    sx, sy, sz = grid.shape
    palette = grid.palette
    palette_comp: dict[str, nbtlib.Int] = {}
    for i, b in enumerate(palette.blocks()):
        palette_comp[b.to_blockstate_str()] = Int(i)
    block_bytes = _encode_block_data(grid)
    root = Compound({
        "Schematic": Compound({
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
    })
    if metadata:
        root["Schematic"]["Metadata"] = Compound({k: _to_nbt(v) for k, v in metadata.items()})
    file = nbtlib.File(root, gzipped=True)
    file.save(path)
    return path


def _to_nbt(v):
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
