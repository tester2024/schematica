"""Unit tests for schematica.cli.parser.parse_line."""
from __future__ import annotations

from schematica.cli.parser import ParsedCommand, parse_line


def test_parse_line_basic_key_value():
    cmd = parse_line("add.box frm=0,0,0 to=2,2,2 block=minecraft:stone")
    assert isinstance(cmd, ParsedCommand)
    assert cmd.name == "add.box"
    assert cmd.args["frm"] == "0,0,0"
    assert cmd.args["to"] == "2,2,2"
    assert cmd.args["block"] == "minecraft:stone"


def test_parse_line_blank_returns_none():
    assert parse_line("") is None
    assert parse_line("   ") is None


def test_parse_line_comment_returns_none():
    assert parse_line("# this is a comment") is None
    assert parse_line("  # indented comment") is None


def test_parse_line_positional_tokens_collected():
    cmd = parse_line("session.new 24x24x24")
    assert cmd is not None
    assert cmd.name == "session.new"
    assert cmd.args["__positional__"] == "24x24x24"


def test_parse_line_mixed_positional_and_kv():
    cmd = parse_line("export 1 2 3 path=out.schem")
    assert cmd is not None
    assert cmd.args["path"] == "out.schem"
    assert cmd.args["__positional__"] == "1 2 3"


def test_parse_line_quoted_value_preserves_spaces():
    cmd = parse_line('echo msg="hello world"')
    assert cmd is not None
    assert cmd.args["msg"] == "hello world"


def test_parse_line_quoted_value_with_equals():
    cmd = parse_line('set note="a=b inside"')
    assert cmd is not None
    assert cmd.args["note"] == "a=b inside"


def test_parse_line_strips_whitespace():
    cmd = parse_line("   stats   ")
    assert cmd is not None
    assert cmd.name == "stats"


def test_parse_line_no_args():
    cmd = parse_line("stats")
    assert cmd is not None
    assert cmd.name == "stats"
    assert cmd.args["__positional__"] == ""


def test_parse_line_value_without_equals_is_positional():
    cmd = parse_line("foo bar baz key=val")
    assert cmd is not None
    assert cmd.args["key"] == "val"
    assert cmd.args["__positional__"] == "bar baz"


def test_parse_line_empty_positional_default():
    cmd = parse_line("foo key=val")
    assert cmd is not None
    assert cmd.args["__positional__"] == ""


def test_parse_line_command_with_dots_and_slashes():
    cmd = parse_line("clone.translate frm=0,0,0")
    assert cmd is not None
    assert cmd.name == "clone.translate"
