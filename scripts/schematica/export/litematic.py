"""Write Litematica `.litematic` files (NBT, used by the Litematica mod).

Litematica stores one or more "regions" each holding a 3D block palette +
a packed bit array of palette indices. The schema (Litematica 1.16+):

  File (gzipped)
  └── Compound (root, no name)
      ├── MinecraftDataVersion: Int
      ├── Version: Int(5)
      └── Regions: Compound
          └── "<region_name>": Compound
              ├── Position: Compound { x,y,z }            # world origin
              ├── Size: Compound { x,y,z }                # signed extents
              ├── TileEntities: List
              ├── Entities: List
              └── BlockStatePalette: List[Compound]        # one blockstate per entry
              └── BlockStates: LongArray                   # packed bit array

The BlockStates long array packs palette indices using
``bits = max(2, ceil(log2(palette_size)))`` bits per voxel, LSB-first, 64 bits
per long. Voxels are ordered X-first, then Z, then Y (the litematica order is
``index = (y * size_z + z) * size_x + x``).
"""
from __future__ import annotations

from pathlib import Path

import nbtlib
import numpy as np
from nbtlib import Compound, Int, List, LongArray

from ..blocks.block import Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid


def _pack_bits(indices: np.ndarray, bits: int) -> bytes:
    """Pack a flat uint array into a long array (big-endian int64) using
    ``bits`` bits per value, LSB-first within each long.

    Litematica packs 64 bits per long, values LSB-first. The number of longs
    is ``ceil(n_values * bits / 64)``.
    """
    n = indices.size
    n_longs = (n * bits + 63) // 64
    out = np.zeros(n_longs, dtype=np.uint64)
    flat = indices.astype(np.uint64).ravel()
    mask = np.uint64((1 << bits) - 1)
    for i in range(n):
        val = flat[i] & mask
        bit_offset = i * bits
        long_idx = bit_offset // 64
        intra_offset = bit_offset % 64
        if intra_offset + bits <= 64:
            out[long_idx] |= val << np.uint64(intra_offset)
        else:
            # Cross-long boundary.
            first_bits = 64 - intra_offset
            out[long_idx] |= (val & ((np.uint64(1) << np.uint64(first_bits)) - np.uint64(1))) << np.uint64(intra_offset)
            if long_idx + 1 < n_longs:
                out[long_idx + 1] |= val >> np.uint64(first_bits)
    return out.astype(">i8").tobytes()


def _encode_dense(grid: VoxelGrid) -> tuple[list[Compound], bytes, int]:
    palette = grid.palette.blocks()
    palette_nbt: list[Compound] = [_block_to_nbt(b) for b in palette]
    bits = max(2, int(np.ceil(np.log2(max(len(palette), 2)))))
    sx, sy, sz = grid.shape
    # Litematica index: (y * sz + z) * sx + x  (X innermost)
    indices = np.zeros(sx * sy * sz, dtype=np.uint64)
    i = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                indices[i] = int(grid.data[x, y, z])
                i += 1
    packed = _pack_bits(indices, bits)
    return palette_nbt, packed, bits


def _encode_chunked(grid: ChunkedGrid) -> tuple[list[Compound], bytes, int]:
    palette = grid.palette.blocks()
    palette_nbt: list[Compound] = [_block_to_nbt(b) for b in palette]
    bits = max(2, int(np.ceil(np.log2(max(len(palette), 2)))))
    sx, sy, sz = grid.shape
    indices = np.zeros(sx * sy * sz, dtype=np.uint64)
    cs = grid.chunk_size
    chunks_by_cy: dict[int, dict[tuple[int, int], np.ndarray]] = {}
    for (cx, cy, cz), arr in grid._chunks.items():
        chunks_by_cy.setdefault(cy, {})[(cx, cz)] = arr
    for y in range(sy):
        cy = y // cs
        ly = y % cs
        row = chunks_by_cy.get(cy, {})
        plane = np.zeros((sx, sz), dtype=np.uint16)
        for (cx, cz), arr in row.items():
            ox = cx * cs
            oz = cz * cs
            sx_a, sy_a, sz_a = arr.shape
            if ly >= sy_a:
                continue
            plane[ox:ox + sx_a, oz:oz + sz_a] = arr[:, ly, :]
        base = y * sx * sz
        for z in range(sz):
            rowoff = base + z * sx
            for x in range(sx):
                indices[rowoff + x] = int(plane[x, z])
    packed = _pack_bits(indices, bits)
    return palette_nbt, packed, bits


def _block_to_nbt(b: Block) -> Compound:
    """Build the Litematica blockstate NBT compound for one Block."""
    props = Compound()
    for k, v in b.states:
        if isinstance(v, bool):
            props[k] = nbtlib.String("true" if v else "false")
        else:
            props[k] = nbtlib.String(str(v))
    return Compound({
        "Name": nbtlib.String(b.name),
        "Properties": props,
    })


def write_litematic(grid: VoxelGrid | ChunkedGrid, path: str | Path, *,
                    region_name: str = "Main",
                    origin: tuple[int, int, int] = (0, 0, 0),
                    data_version: int = 3465) -> Path:
    """Write a `.litematic` file containing a single region from ``grid``.

    Litematica's size axes use a signed convention; we emit positive sizes.
    ``origin`` is the world position where the region's min corner sits.
    """
    path = Path(path)
    sx, sy, sz = grid.shape
    if isinstance(grid, ChunkedGrid):
        palette_nbt, packed, _bits = _encode_chunked(grid)
    else:
        palette_nbt, packed, _bits = _encode_dense(grid)
    n_longs = len(packed) // 8
    longs = LongArray(np.frombuffer(packed, dtype='>i8'))
    root = Compound({
        "MinecraftDataVersion": Int(data_version),
        "Version": Int(5),
        "Regions": Compound({
            region_name: Compound({
                "Position": Compound({"x": Int(origin[0]), "y": Int(origin[1]), "z": Int(origin[2])}),
                "Size": Compound({"x": Int(sx), "y": Int(sy), "z": Int(sz)}),
                "TileEntities": List(),
                "Entities": List(),
                "BlockStatePalette": List(palette_nbt),
                "BlockStates": longs,
            }),
        }),
    })
    file = nbtlib.File(root, gzipped=True)
    file.save(path)
    return path
