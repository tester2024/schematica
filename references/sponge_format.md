# Sponge `.schem` format and encoder

## What the exporter writes

`schematica.export.sponge.write_sponge(grid, path, data_version=3465,
offset=(0,0,0), metadata=None)` writes a gzip-compressed NBT file conforming
to the Sponge schematic v2 schema. The default `data_version=3465`
corresponds to Minecraft Java 1.20.1.

## NBT structure (produced)

```
File (gzipped)
└── Schematic: Compound
    ├── Version: Int(2)
    ├── DataVersion: Int(3465)
    ├── Width: Short(sx)
    ├── Height: Short(sy)
    ├── Length: Short(sz)
    ├── PaletteMax: Int(N)
    ├── Palette: Compound
    │   └── "<blockstate_str>": Int(index)   # one per palette entry
    ├── BlockData: ByteArray                   # varint-encoded indices
    ├── Offset: IntArray([ox, oy, oz])
    └── Metadata: Compound (optional)          # only if metadata= passed
```

## Block ordering

Sponge v2 orders blocks as:
```
index = (y * Length + z) * Width + x
```
The encoder iterates `for y: for z: for x:` and appends each palette index as
a Protocol Buffer-style varint.

## Varint encoding

Each voxel's palette index is written as a base-128 varint (little-endian,
7 bits per byte, MSB continuation bit). Index 0 (air) encodes as a single
zero byte. The encoder lives in `_varint_encode` in `sponge.py`.

## Reading back

The tests round-trip the file via `nbtlib.File.parse(io.BytesIO(gzip.decompress(...)))`.
To read a `.schem` programmatically:

```python
import gzip, io
import nbtlib
from pathlib import Path

f = nbtlib.File.parse(io.BytesIO(gzip.decompress(Path("build.schem").read_bytes())))
sch = f["Schematic"]
width = int(sch["Width"])
height = int(sch["Height"])
length = int(sch["Length"])
palette = {k: int(v) for k, v in sch["Palette"].items()}
block_data = bytes(sch["BlockData"])
```

## Limitations

- **Block entities** (chests, signs) are not written — only blockstates.
- **Biomes** are not written (Sponge v3 adds biomes; we emit v2).
- **Tile entities / NBT data** per block is not supported.
- The `Metadata` compound is freeform; pass `metadata={"name": "My Build",
  "author": "agent"}` to annotate.
- `Offset` is the world position where the schematic should paste; default
  `(0,0,0)`.

## Validating output

Sanity-check a written file:
```python
import gzip, io, nbtlib
from pathlib import Path
f = nbtlib.File.parse(io.BytesIO(gzip.decompress(Path("build.schem").read_bytes())))
sch = f["Schematic"]
assert int(sch["Version"]) == 2
assert int(sch["Width"]) * int(sch["Height"]) * int(sch["Length"]) == len(bytes(sch["BlockData"]))
```
(The varint makes the byte count >= voxel count, never less; the assertion
above is a lower bound check.)

## Loading in Minecraft

The `.schem` is loadable by:
- WorldEdit / FastAsyncWorldEdit (`//load build` then `//paste`).
- Litematica mod (import as Sponge schematic).
- Any tool that reads Sponge v2.

## Switching to amulet-core

For multi-format output (MCEdit, litematic), install `amulet-core` (Python
3.11-3.13 only) and replace the exporter. The `Session.grid` (VoxelGrid) is
already a numpy-backed 3D array, directly convertible to amulet's
`BlockManager` + chunk format. See `references/roadmap.md`.