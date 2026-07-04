"""Bootstrap utility: download minecraft-data for a target version on demand.

Without a vendored PrismarineJS/minecraft-data tree, the toolkit falls back to
a limited built-in block catalog. This module fetches the relevant JSON files
directly from the PrismarineJS GitHub repository on demand and caches them
locally so the agent gets full per-version blockstate registries without
manually cloning the submodule.

Usage::

    # Python
    from schematica.blocks.download import download_version
    download_version("1.20.1")          # -> Path to cached data/pc/1.20.1
    download_version("1.20.1", force=True)

    # CLI
    python -m schematica.blocks.download 1.20.1
    python -m schematica.blocks.download --list
    python -m schematica.blocks.download 1.20.1 --force

The cache is written under ``<cache_root>/data/pc/<version>/``. ``cache_root``
defaults to the same directory the registry loader searches
(``SCHEMATICA_MINECRAFT_DATA`` env var, the skill root, or the scripts dir),
so a successful download is immediately visible to ``BlockRegistry.for_version``.

Network access uses ``urllib.request`` from the standard library only, so this
utility has zero external dependencies beyond Python 3.11+.

Only the files the registry needs are fetched: ``blocks.json`` and the
version manifest ``data/pc/<version>/version.json``. The full minecraft-data
tree is intentionally not mirrored.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# PrismarineJS/minecraft-data repository. We use the GitHub raw endpoint so
# each file is one HTTP GET with no API rate limits.
_REPO_OWNER = "PrismarineJS"
_REPO_NAME = "minecraft-data"
_BRANCH = "master"
_RAW_BASE = f"https://raw.githubusercontent.com/{_REPO_OWNER}/{_REPO_NAME}/{_BRANCH}/"
# Manifests listing every known version.
_VERSIONS_PC_JSON = "data/pc/common/versions.json"
# Files we want per version. ``blocks.json`` is the registry's canonical source.
_VERSION_FILES = (
    "blocks.json",
    "version.json",
)

_USER_AGENT = "schematica-blocks-downloader/1.0"


def _http_get(url: str, timeout: float = 30.0) -> bytes:
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted github URL
            data = resp.read()
            return bytes(data) if not isinstance(data, bytes) else data
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}: {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"network error fetching {url}: {e.reason}") from e


def _default_cache_root() -> Path:
    """Return the cache root the registry loader will also search."""
    env = os.environ.get("SCHEMATICA_MINECRAFT_DATA")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    scripts_root = here.parent.parent.parent
    for cand in (scripts_root.parent / "minecraft_data", scripts_root / "minecraft_data"):
        if cand.parent.exists():
            return cand
    return scripts_root.parent / "minecraft_data"


def list_available_versions(timeout: float = 30.0) -> list[str]:
    """Fetch the upstream list of known PC versions and return them sorted."""
    raw = _http_get(_RAW_BASE + _VERSIONS_PC_JSON, timeout=timeout)
    data = json.loads(raw)
    versions: list[str] = []
    for entry in data:
        if isinstance(entry, dict) and "minecraftVersion" in entry:
            versions.append(str(entry["minecraftVersion"]))
        elif isinstance(entry, str):
            versions.append(entry)
    return sorted(set(versions), key=lambda v: tuple(int(x) if x.isdigit() else 0
                                                      for x in v.split(".")))


def is_version_cached(version: str, cache_root: str | Path | None = None) -> bool:
    root = Path(cache_root) if cache_root else _default_cache_root()
    return (root / "data" / "pc" / version / "blocks.json").exists()


def download_version(version: str, *, cache_root: str | Path | None = None,
                     force: bool = False, timeout: float = 30.0) -> Path:
    """Download ``blocks.json`` + ``version.json`` for ``version`` into the cache.

    Returns the directory ``<cache_root>/data/pc/<version>/``. If the version
    is already cached and ``force`` is false, returns immediately without
    network access. Raises ``RuntimeError`` on network / HTTP errors.
    """
    root = Path(cache_root) if cache_root else _default_cache_root()
    version_dir = root / "data" / "pc" / version
    blocks_path = version_dir / "blocks.json"
    if blocks_path.exists() and not force:
        return version_dir
    version_dir.mkdir(parents=True, exist_ok=True)
    for fname in _VERSION_FILES:
        url = _RAW_BASE + f"data/pc/{version}/{fname}"
        try:
            payload = _http_get(url, timeout=timeout)
        except RuntimeError as e:
            # blocks.json is mandatory; version.json is nice-to-have.
            if fname == "blocks.json":
                raise
            print(f"warning: could not fetch {fname} for {version}: {e}", file=sys.stderr)
            continue
        out_path = version_dir / fname
        out_path.write_bytes(payload)
    return version_dir


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m schematica.blocks.download",
        description="Download minecraft-data block registries on demand.",
    )
    parser.add_argument("version", nargs="?", help="Minecraft PC version, e.g. 1.20.1")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if the version is already cached.")
    parser.add_argument("--list", action="store_true",
                        help="List all versions available upstream and exit.")
    parser.add_argument("--cache-root", default=None,
                        help="Override cache root (defaults to SCHEMATICA_MINECRAFT_DATA"
                             " or the skill-root minecraft_data).")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Per-request timeout in seconds.")
    args = parser.parse_args(argv)

    cache_root = Path(args.cache_root) if args.cache_root else None

    if args.list:
        try:
            versions = list_available_versions(timeout=args.timeout)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        for v in versions:
            print(v)
        return 0

    if not args.version:
        parser.error("version is required (or pass --list)")

    try:
        out = download_version(args.version, cache_root=cache_root,
                               force=args.force, timeout=args.timeout)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"downloaded {args.version} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
