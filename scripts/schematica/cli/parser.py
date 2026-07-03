"""Tokenizer for REPL command lines: supports key=value, quoted strings."""
from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    name: str
    args: dict[str, str]


def parse_line(line: str) -> ParsedCommand | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = shlex.split(line)
    name = parts[0]
    args: dict[str, str] = {}
    positional: list[str] = []
    for p in parts[1:]:
        if "=" in p:
            k, _, v = p.partition("=")
            args[k] = v
        else:
            positional.append(p)
    # positional -> arg names by spec order happens at dispatch
    args["__positional__"] = " ".join(positional)  # store for later
    return ParsedCommand(name=name, args=args)
