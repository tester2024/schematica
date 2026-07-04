"""Pre-export compatibility reports.

Reports which palette entries are supported or degraded for each export
format, so the AI can fix blocks *before* writing a schematic instead of
discovering data loss on import.
"""
from __future__ import annotations

from typing import Any

from ..blocks.registry import BlockRegistry
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid
from .mcedit import DEFAULT_LEGACY_IDS, _resolve_id


def palette_report(grid: VoxelGrid | ChunkedGrid,
                    registry: BlockRegistry | None = None) -> dict[str, Any]:
    """Summarise the grid palette for AI review.

    Returns a dict with:

    - ``palette_size``: number of distinct blockstates.
    - ``block_count``: number of non-air blocks in the grid.
    - ``unknown_blocks``: palette entries not in ``registry`` (empty if no registry).
    - ``mcedit_unmapped``: non-air palette entries that would become air in MCEdit.
    - ``sponge_ok``: True if every non-air block resolves under the registry.
    """
    blocks = grid.palette.blocks()
    non_air = [b for b in blocks if b.name != "minecraft:air"]

    unknown: list[str] = []
    if registry is not None:
        for b in non_air:
            if b.name not in registry:
                unknown.append(b.to_blockstate_str())

    mcedit_unmapped: list[str] = []
    for b in non_air:
        if _resolve_id(b.to_blockstate_str(), DEFAULT_LEGACY_IDS) == 0:
            mcedit_unmapped.append(b.to_blockstate_str())

    sponge_ok = registry is not None and not unknown

    return {
        "palette_size": len(blocks),
        "block_count": grid.nonempty_count(),
        "unknown_blocks": unknown,
        "mcedit_unmapped": mcedit_unmapped,
        "sponge_ok": sponge_ok,
    }


def format_report(report: dict[str, Any]) -> str:
    """Human-readable one-line summary of ``palette_report`` output."""
    parts = [
        f"palette={report['palette_size']}",
        f"blocks={report['block_count']}",
    ]
    if report["unknown_blocks"]:
        parts.append(f"unknown={len(report['unknown_blocks'])}")
    if report["mcedit_unmapped"]:
        parts.append(f"mcedit_unmapped={len(report['mcedit_unmapped'])}")
    if report["sponge_ok"]:
        parts.append("sponge=ok")
    return " ".join(parts)