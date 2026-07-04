"""Unit tests for schematica.blocks.download (no real network access).

All HTTP calls are mocked so the tests run offline.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from schematica.blocks import download as dl

# ---- _default_cache_root --------------------------------------------------

def test_default_cache_root_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SCHEMATICA_MINECRAFT_DATA", str(tmp_path))
    assert dl._default_cache_root() == tmp_path


def test_default_cache_root_no_env(monkeypatch):
    monkeypatch.delenv("SCHEMATICA_MINECRAFT_DATA", raising=False)
    root = dl._default_cache_root()
    assert isinstance(root, Path)


# ---- is_version_cached ----------------------------------------------------

def test_is_version_cached_false(tmp_path):
    assert dl.is_version_cached("1.20.1", cache_root=tmp_path) is False


def test_is_version_cached_true(tmp_path):
    vdir = tmp_path / "data" / "pc" / "1.20.1"
    vdir.mkdir(parents=True)
    (vdir / "blocks.json").write_text("[]", encoding="utf-8")
    assert dl.is_version_cached("1.20.1", cache_root=tmp_path) is True


# ---- download_version -----------------------------------------------------

def _fake_get_blocks(url: str, timeout: float = 30.0) -> bytes:
    if url.endswith("blocks.json"):
        return json.dumps([{"id": 1, "name": "minecraft:stone",
                            "displayName": "Stone"}]).encode("utf-8")
    if url.endswith("version.json"):
        return json.dumps({"minecraftVersion": "1.20.1"}).encode("utf-8")
    return b"{}"


def test_download_version_writes_files(tmp_path):
    with patch.object(dl, "_http_get", side_effect=_fake_get_blocks):
        out = dl.download_version("1.20.1", cache_root=tmp_path)
    assert out == tmp_path / "data" / "pc" / "1.20.1"
    assert (out / "blocks.json").exists()
    assert (out / "version.json").exists()
    data = json.loads((out / "blocks.json").read_text(encoding="utf-8"))
    assert data[0]["name"] == "minecraft:stone"


def test_download_version_skips_when_cached(tmp_path):
    vdir = tmp_path / "data" / "pc" / "1.20.1"
    vdir.mkdir(parents=True)
    (vdir / "blocks.json").write_text("existing", encoding="utf-8")
    with patch.object(dl, "_http_get", side_effect=AssertionError("no network")):
        out = dl.download_version("1.20.1", cache_root=tmp_path)
    # Should not have touched the existing file.
    assert (out / "blocks.json").read_text(encoding="utf-8") == "existing"


def test_download_version_force_overwrites(tmp_path):
    vdir = tmp_path / "data" / "pc" / "1.20.1"
    vdir.mkdir(parents=True)
    (vdir / "blocks.json").write_text("old", encoding="utf-8")
    with patch.object(dl, "_http_get", side_effect=_fake_get_blocks):
        out = dl.download_version("1.20.1", cache_root=tmp_path, force=True)
    assert (out / "blocks.json").read_text(encoding="utf-8") != "old"


def test_download_version_blocks_failure_raises(tmp_path):
    def boom(url, timeout=30.0):
        raise RuntimeError("404")
    with patch.object(dl, "_http_get", side_effect=boom):
        with pytest.raises(RuntimeError, match="404"):
            dl.download_version("1.20.1", cache_root=tmp_path)


def test_download_version_version_json_failure_is_ignored(tmp_path, capsys):
    def partial(url, timeout=30.0):
        if url.endswith("version.json"):
            raise RuntimeError("missing")
        return _fake_get_blocks(url)
    with patch.object(dl, "_http_get", side_effect=partial):
        out = dl.download_version("1.20.1", cache_root=tmp_path)
    assert (out / "blocks.json").exists()
    assert not (out / "version.json").exists()


# ---- list_available_versions ---------------------------------------------

def test_list_available_versions_dict_entries():
    payload = json.dumps([
        {"minecraftVersion": "1.20.1"},
        {"minecraftVersion": "1.19.2"},
    ]).encode("utf-8")
    with patch.object(dl, "_http_get", return_value=payload):
        versions = dl.list_available_versions()
    assert "1.20.1" in versions
    assert "1.19.2" in versions


def test_list_available_versions_string_entries():
    payload = json.dumps(["1.20.1", "1.19.2"]).encode("utf-8")
    with patch.object(dl, "_http_get", return_value=payload):
        versions = dl.list_available_versions()
    assert "1.20.1" in versions


def test_list_available_versions_dedupes():
    payload = json.dumps([
        {"minecraftVersion": "1.20.1"},
        {"minecraftVersion": "1.20.1"},
    ]).encode("utf-8")
    with patch.object(dl, "_http_get", return_value=payload):
        versions = dl.list_available_versions()
    assert versions.count("1.20.1") == 1


# ---- _main CLI ------------------------------------------------------------

def test_main_list(capsys):
    payload = json.dumps([{"minecraftVersion": "1.20.1"}]).encode("utf-8")
    with patch.object(dl, "_http_get", return_value=payload):
        rc = dl._main(["--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1.20.1" in out


def test_main_download(tmp_path):
    with patch.object(dl, "_http_get", side_effect=_fake_get_blocks):
        rc = dl._main(["1.20.1", "--cache-root", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "data" / "pc" / "1.20.1" / "blocks.json").exists()


def test_main_download_network_error(capsys):
    def boom(url, timeout=30.0):
        raise RuntimeError("boom")
    with patch.object(dl, "_http_get", side_effect=boom):
        rc = dl._main(["1.20.1", "--cache-root", str(_tmp())])
    assert rc == 2


def _tmp() -> str:
    import tempfile
    return tempfile.mkdtemp()


def test_main_requires_version():
    with pytest.raises(SystemExit):
        dl._main([])


def test_main_force_flag(tmp_path):
    vdir = tmp_path / "data" / "pc" / "1.20.1"
    vdir.mkdir(parents=True)
    (vdir / "blocks.json").write_text("old", encoding="utf-8")
    with patch.object(dl, "_http_get", side_effect=_fake_get_blocks):
        rc = dl._main(["1.20.1", "--force", "--cache-root", str(tmp_path)])
    assert rc == 0
    assert (vdir / "blocks.json").read_text(encoding="utf-8") != "old"
