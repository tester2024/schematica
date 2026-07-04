"""Export validation system: cross-format round-trip integrity checks.

Validates that a schematic file, once written, can be read back and matches
the original grid's block content. Supports Sponge (.schem), Litematica
(.litematic), and MCEdit (.schematic) formats.

Usage::

    from schematica.export.validation import validate_export

    result = validate_export(grid, "build.schem", fmt="sponge")
    if result.ok:
        print("round-trip clean")
    else:
        for issue in result.issues:
            print(issue)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..blocks.block import AIR, Block
from ..core.chunked import ChunkedGrid
from ..core.palette import Palette
from ..core.voxel import VoxelGrid

Grid = VoxelGrid | ChunkedGrid


@dataclass
class ValidationResult:
    """Outcome of a format validation round-trip."""
    ok: bool
    format: str
    path: str
    issues: list[str] = field(default_factory=list)
    missing_blocks: list[str] = field(default_factory=list)
    extra_blocks: list[str] = field(default_factory=list)
    voxel_mismatches: int = 0
    total_voxels: int = 0

    def __str__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        base = f"[{self.format}] {status} ({self.path})"
        if self.issues:
            base += "\n  " + "\n  ".join(self.issues)
        if self.missing_blocks:
            base += f"\n  missing: {self.missing_blocks}"
        if self.extra_blocks:
            base += f"\n  extra: {self.extra_blocks}"
        if self.voxel_mismatches:
            base += f"\n  voxel mismatches: {self.voxel_mismatches}/{self.total_voxels}"
        return base


def validate_export(grid: Grid, path: str | Path, *,
                    fmt: str = "sponge",
                    data_version: int = 3465) -> ValidationResult:
    """Write a schematic and validate it round-trips correctly.

    ``fmt`` is one of ``"sponge"``, ``"litematic"``, ``"mcedit"``.

    For ``mcedit``, unmapped modern blocks become air and are reported as
    ``missing_blocks`` (this is expected data loss, not a bug).

    Returns a ``ValidationResult``.
    """
    p = Path(path)
    fmt = fmt.lower().strip()
    result = ValidationResult(ok=True, format=fmt, path=str(p))

    # Write the file.
    if fmt == "sponge":
        from .sponge import write_sponge
        write_sponge(grid, p, data_version=data_version)
        read_back = _read_sponge(p)
    elif fmt == "litematic":
        from .litematic import write_litematic
        write_litematic(grid, p, data_version=data_version)
        read_back = _read_litematic(p)
    elif fmt == "mcedit":
        from .mcedit import write_mcedit
        write_mcedit(grid, p)
        read_back = _read_mcedit(p, grid.shape)
    else:
        result.ok = False
        result.issues.append(f"unknown format: {fmt}")
        return result

    if read_back is None:
        result.ok = False
        result.issues.append("failed to read back file")
        return result

    # Compare palette.
    orig_palette = grid.palette.blocks()
    read_palette = read_back.palette.blocks()
    orig_set = {b.to_blockstate_str() for b in orig_palette}
    read_set = {b.to_blockstate_str() for b in read_palette}
    missing = orig_set - read_set
    extra = read_set - orig_set
    if missing:
        result.missing_blocks = sorted(missing)
        if fmt != "mcedit":  # mcedit is expected to lose blocks
            result.issues.append(f"palette lost {len(missing)} blocks in round-trip")
            result.ok = False
    if extra:
        result.extra_blocks = sorted(extra)
        result.issues.append(f"palette gained {len(extra)} unexpected blocks")
        result.ok = False

    # Compare voxel data.
    orig_dense = _to_dense(grid)
    read_dense = read_back.data
    if orig_dense.shape != read_dense.shape:
        result.issues.append(
            f"shape mismatch: orig={orig_dense.shape} read={read_dense.shape}"
        )
        result.ok = False
    else:
        mismatches = int(np.count_nonzero(orig_dense != read_dense))
        total = int(np.prod(orig_dense.shape))
        result.voxel_mismatches = mismatches
        result.total_voxels = total
        # For mcedit, mismatches are expected where blocks were unmapped.
        if fmt == "mcedit":
            # Only flag mismatches where the original block WAS mapped.
            # Find positions where original block is in the read-back palette.
            # If orig had a block that became air in mcedit, that's expected.
            expected_loss = 0
            for i, b in enumerate(orig_palette):
                if b.name == "minecraft:air":
                    continue
                bs = b.to_blockstate_str()
                if bs not in read_set and bs not in {rb.to_blockstate_str() for rb in read_palette}:
                    # This block was unmapped; count voxels that had it.
                    expected_loss += int(np.count_nonzero(orig_dense == i))
            unexpected_mismatches = mismatches - expected_loss
            if unexpected_mismatches > 0:
                result.issues.append(
                    f"{unexpected_mismatches} unexpected voxel mismatches "
                    f"({expected_loss} expected from unmapped blocks)"
                )
                result.ok = False
        elif mismatches > 0:
            result.issues.append(f"{mismatches} voxel mismatches out of {total}")
            result.ok = False

    return result


def validate_all(grid: Grid, dir_path: str | Path, *,
                 data_version: int = 3465) -> list[ValidationResult]:
    """Validate all three formats, writing files into ``dir_path``.

    Returns one ``ValidationResult`` per format.
    """
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)
    results: list[ValidationResult] = []
    for fmt, ext in [("sponge", "schem"), ("litematic", "litematic"),
                     ("mcedit", "schematic")]:
        p = d / f"validation.{ext}"
        try:
            r = validate_export(grid, p, fmt=fmt, data_version=data_version)
        except Exception as e:
            r = ValidationResult(ok=False, format=fmt, path=str(p))
            r.issues.append(f"exception: {e}")
        results.append(r)
    return results


# ---- format readers ----------------------------------------------------

def _read_sponge(path: Path) -> VoxelGrid | None:
    """Read a Sponge .schem file back into a VoxelGrid."""
    try:
        import nbtlib
        tag = nbtlib.load(str(path), gzipped=True)
        sch = _sponge_root(tag)
        sx = int(sch["Width"])
        sy = int(sch["Height"])
        sz = int(sch["Length"])
        palette_comp = dict(sch["Palette"])
        # Build palette.
        palette = Palette()
        blockstate_to_idx: dict[int, Block] = {}
        for bs_str, idx in palette_comp.items():
            b = Block.parse(str(bs_str))
            palette_idx = palette.add(b)
            blockstate_to_idx[int(idx)] = palette_idx
        # Read block data (varint).
        block_data = bytes(sch["BlockData"])
        data = np.zeros((sx, sy, sz), dtype=np.uint16)
        i = 0
        for y in range(sy):
            for z in range(sz):
                for x in range(sx):
                    if i >= len(block_data):
                        break
                    val, i = _read_varint(block_data, i)
                    data[x, y, z] = blockstate_to_idx.get(val, 0)
        return VoxelGrid(shape=(sx, sy, sz), palette=palette, data=data)
    except Exception:
        return None


def _sponge_root(tag: Any) -> Any:
    """Return the Sponge schematic compound.

    Older Schematica builds nested the data under a child compound named
    ``Schematic``. Current exports use the standard named root compound.
    """
    if "Width" in tag and "Palette" in tag and "BlockData" in tag:
        return tag
    return tag["Schematic"]


def _read_litematic(path: Path) -> VoxelGrid | None:
    """Read a Litematica .litematic file back into a VoxelGrid."""
    try:
        import nbtlib
        tag = nbtlib.load(str(path), gzipped=True)
        regions = tag["Regions"]
        # Take the first region.
        region_name = list(regions.keys())[0]
        region = regions[region_name]
        size = region["Size"]
        sx = abs(int(size["x"]))
        sy = abs(int(size["y"]))
        sz = abs(int(size["z"]))
        # Read block state palette.
        palette_nbt = list(region["BlockStatePalette"])
        palette = Palette()
        nbt_to_idx: list[int] = []
        for entry in palette_nbt:
            name = str(entry["Name"])
            props = entry.get("Properties")
            if props and len(props) > 0:
                states = tuple(sorted(
                    (str(k), str(v)) for k, v in props.items()
                ))
                b = Block(name=name, states=states)
            else:
                b = Block(name=name)
            nbt_to_idx.append(palette.add(b))
        # Read block states (packed long array).
        block_states = list(region["BlockStates"])
        bits = max(2, int(np.ceil(np.log2(max(len(palette_nbt), 2)))))
        data = _unpack_bits(block_states, bits, sx, sy, sz)
        # Map from NBT palette index to our palette index.
        remapped = np.zeros_like(data)
        for nbt_idx, our_idx in enumerate(nbt_to_idx):
            remapped[data == nbt_idx] = our_idx
        return VoxelGrid(shape=(sx, sy, sz), palette=palette, data=remapped)
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _read_mcedit(path: Path, expected_shape: tuple[int, int, int]) -> VoxelGrid | None:
    """Read a legacy MCEdit .schematic file back into a VoxelGrid."""
    try:
        import nbtlib
        tag = nbtlib.load(str(path), gzipped=True)
        sx = int(tag["Width"])
        sy = int(tag["Height"])
        sz = int(tag["Length"])
        blocks = bytes(tag["Blocks"])
        # We can't reverse the legacy ID mapping fully (it's lossy), so we
        # build a palette from just air + stone as placeholders. The validation
        # will compare structural integrity (shape + solid/air pattern).
        palette = Palette()
        palette.add(AIR)
        palette.add(Block(name="minecraft:stone"))
        data = np.zeros((sx, sy, sz), dtype=np.uint16)
        i = 0
        for y in range(sy):
            for z in range(sz):
                for x in range(sx):
                    if i < len(blocks):
                        b = blocks[i]
                        data[x, y, z] = 0 if b == 0 else 1
                        i += 1
        return VoxelGrid(shape=(sx, sy, sz), palette=palette, data=data)
    except Exception:
        return None


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    """Read a varint from ``data`` starting at ``i``; return (value, next_i)."""
    val = 0
    shift = 0
    while i < len(data):
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return val, i


def _unpack_bits(longs: list, bits: int, sx: int, sy: int, sz: int) -> np.ndarray:
    """Unpack a litematica packed long array into a uint16 3D array."""
    n = sx * sy * sz
    n_longs = len(longs)
    # Explicitly convert nbtlib types to Python ints, then to numpy.
    arr = np.array([int(x) for x in longs], dtype=np.int64).astype(np.uint64)
    flat = np.zeros(n, dtype=np.uint16)
    mask = (1 << bits) - 1
    for i in range(n):
        bit_offset = i * bits
        long_idx = bit_offset // 64
        intra_offset = bit_offset % 64
        if long_idx >= n_longs:
            break
        if intra_offset + bits <= 64:
            val = int(arr[long_idx] >> np.uint64(intra_offset)) & mask
        else:
            # Cross-long: bits span two consecutive longs.
            lo = int(arr[long_idx]) >> intra_offset
            hi = int(arr[long_idx + 1]) << (64 - intra_offset) if long_idx + 1 < n_longs else 0
            val = (lo | hi) & mask
        flat[i] = val
    # Litematica order: (y * sz + z) * sx + x
    data = np.zeros((sx, sy, sz), dtype=np.uint16)
    idx = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                data[x, y, z] = flat[idx]
                idx += 1
    return data


def _to_dense(grid: Grid) -> np.ndarray:
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data
