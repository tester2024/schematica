"""Block identity and state handling.

A Block is an immutable (name, states) pair. The serialized form follows the
Minecraft blockstate string convention used by Sponge schematics:

    minecraft:stone
    minecraft:oak_log[axis=y]
    minecraft:stairs[facing=north,half=top,shape=straight]
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


def _fmt_state_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_state_value(raw: str) -> object:
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        return raw


@dataclass(frozen=True, order=True)
class Block:
    """A single blockstate.

    States are stored as a tuple of (name, value) pairs to preserve a canonical
    insertion order, which keeps the blockstate string deterministic regardless
    of how the caller built the mapping.
    """

    name: str
    states: tuple[tuple[str, object], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Block name cannot be empty")
        if ":" not in self.name:
            object.__setattr__(self, "name", f"minecraft:{self.name}")
        object.__setattr__(self, "name", self.name.lower())

    @classmethod
    def parse(cls, blockstate_str: str) -> Block:
        """Parse a blockstate string like 'minecraft:oak_log[axis=y]'.

        Tolerant: accepts names without 'minecraft:' prefix.
        """
        s = blockstate_str.strip()
        if "[" not in s:
            return cls(name=s)
        name, _, states_raw = s.partition("[")
        states_raw = states_raw.rstrip("]")
        pairs: list[tuple[str, object]] = []
        if states_raw:
            for part in states_raw.split(","):
                k, _, v = part.partition("=")
                pairs.append((k.strip(), _parse_state_value(v.strip())))
        return cls(name=name.strip(), states=tuple(pairs))

    def to_blockstate_str(self) -> str:
        if not self.states:
            return self.name
        inner = ",".join(f"{k}={_fmt_state_value(v)}" for k, v in self.states)
        return f"{self.name}[{inner}]"

    @classmethod
    def from_mapping(cls, name: str, states: Mapping[str, object] | None = None) -> Block:
        pairs = tuple(sorted((states or {}).items())) if states else ()
        return cls(name=name, states=pairs)

    def __str__(self) -> str:
        return self.to_blockstate_str()

    def __repr__(self) -> str:
        return f"Block({self.to_blockstate_str()!r})"


AIR = Block(name="minecraft:air")
