# Sponge `.schem` format and encoder

## What the exporter writes

`schematica.export.sponge.write_sponge(grid, path, data_version=3465,
offset=(0,0,0), metadata=None)` writes a gzip-compressed NBT file conforming
to the Sponge schematic v2 schema. The default `data_version=3465`
corresponds to Minecraft Java 1.20.1.

## NBT structure (produced)

```
File (gzipped)
└── Named root "Schematic": Compound
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
assert f.root_name == "Schematic"
width = int(f["Width"])
height = int(f["Height"])
length = int(f["Length"])
palette = {k: int(v) for k, v in f["Palette"].items()}
block_data = bytes(f["BlockData"])
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
assert f.root_name == "Schematic"
assert int(f["Version"]) == 2
assert int(f["Width"]) * int(f["Height"]) * int(f["Length"]) <= len(bytes(f["BlockData"]))
```
(The varint makes the byte count >= voxel count, never less; the assertion
above is a lower bound check.)

## Loading in Minecraft

The `.schem` is loadable by:
- WorldEdit / FastAsyncWorldEdit (`//load build` then `//paste`).
- Litematica mod (import as Sponge schematic).
- Any tool that reads Sponge v2.

## Legacy data versions

`data_version < 1451` means pre-flattening Minecraft (1.12 and older). Sponge
can still store palette strings, but modern names such as `minecraft:red_wool`
do not represent legacy numeric IDs plus metadata. `write_sponge` emits a
`RuntimeWarning` when a legacy data version is paired with modern flattened
names or blockstate properties. For 1.7-1.12 workflows, prefer
`write_mcedit(..., path="build.schematic")` when metadata matters.

## Other exporters

The toolkit also includes built-in `write_mcedit` and `write_litematic`
exporters. `amulet-core` remains an optional future/backend integration, not a
requirement for these formats.
