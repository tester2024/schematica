"""Block palette: ordered, deduped list of blockstates used by a VoxelGrid.

Palette index 0 is always air by convention so an all-zero grid is empty.
"""
from __future__ import annotations

from collections.abc import Iterator

from ..blocks.block import AIR, Block


class Palette:
    def __init__(self) -> None:
        self._blocks: list[Block] = [AIR]
        self._index: dict[Block, int] = {AIR: 0}

    @classmethod
    def from_blocks(cls, blocks: list[Block]) -> Palette:
        p = cls()
        for b in blocks:
            p.add(b)
        return p

    def add(self, block: Block) -> int:
        idx = self._index.get(block)
        if idx is not None:
            return idx
        idx = len(self._blocks)
        self._blocks.append(block)
        self._index[block] = idx
        return idx

    def __getitem__(self, idx: int) -> Block:
        return self._blocks[idx]

    def index_of(self, block: Block) -> int | None:
        return self._index.get(block)

    def __len__(self) -> int:
        return len(self._blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self._blocks)

    def blocks(self) -> list[Block]:
        return list(self._blocks)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Palette) and self._blocks == other._blocks

    def __repr__(self) -> str:
        return f"Palette({self._blocks!r})"

    def to_json(self) -> list[str]:
        return [b.to_blockstate_str() for b in self._blocks]

    @classmethod
    def from_json(cls, items: list[str]) -> Palette:
        return cls.from_blocks([Block.parse(s) for s in items])
