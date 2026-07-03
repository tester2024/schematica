# Roadmap

## Done (phases 0-11)

- **Phase 0 — Scaffold**: pyproject, ruff/pytest/mypy config, package layout.
- **Phase 1 — Blocks + Palette**: `Block` dataclass, `BlockRegistry` with
  minecraft-data JSON loader + fallback catalog, state round-trip.
- **Phase 2 — VoxelGrid + primitives**: numpy uint16 3D array, Box, Sphere,
  Ellipsoid, Cylinder, Cone, Pyramid, Torus, Plane, Wedge, Line. Transforms
  (translate/mirror/rotate90/array). Boolean ops (union/intersect/subtract/xor).
- **Phase 3 — Polygon + mesh + heightmap**: shapely 2D polygon extrude,
  trimesh OBJ/STL voxelize, heightmap from array or image.
- **Phase 4 — Sponge export**: nbtlib v2 writer with palette + varint blockdata,
  offset, metadata. Round-trip tested.
- **Phase 5 — Preview**: matplotlib voxels -> top/front/right/iso PNGs.
- **Phase 6 — Session + history**: orchestrator with delta-based undo/redo,
  save/load JSON.
- **Phase 7 — REPL**: prompt_toolkit-style CLI with `--script` batch mode,
  command spec table, arg coercion.
- **Phase 8 — Procedural generators**: Perlin noise, terrain applicator, tree
  template.
- **Phase 9 — Advanced generators**: wave function collapse tilesets and texture
  palette tools.
- **Phase 10 — Export formats**: MCEdit `.schematic` and Litematica `.litematic`
  exporters with dense/chunked parity tests.
- **Phase 11 — Review hardening**: normalized registry names, unique fallback
  ids, expanded colored fallback blocks, MCEdit legacy metadata for common
  colored blocks, Sponge legacy palette warnings, safe large-grid previews, and
  clone commands for repeated/cardinal-symmetric builds.

## Remaining

### Polish
- `mypy --strict` clean across the package.
- Byte-equal golden `.schem` fixtures + Pillow `dhash` PNG regression.
- Hypothesis property tests for shapes and session invariants.
- Full minecraft-data submodule vendoring + `BlockRegistry.list_versions`
  in tests.
- Example gallery: `examples/castle.py`, `examples/terrain.py`,
  `examples/village.py`.
- Sponge/MCEdit/Litematica importers for round-trip editing.
- Block entities / tile entities for signs, chests, and spawners.

## Known limitations

- **amulet-core unavailable on Python 3.14**: the default backend is nbtlib.
  amulet-core is an optional extra for 3.11-3.13 only.
- **No block entities**: chests, signs, spawners are not written. Only
  blockstates and legacy block metadata are supported.
- **No biomes**: Sponge v2 has no biome array; v3 would be needed.
- **Cylinder axis**: only `axis="y"` is implemented.
- **Translated shape uses np.roll**: wraps around grid edges. For non-wrapping
  translation, clamp coords manually.
- **Preview performance**: matplotlib 3D voxels cap around 32³; larger grids use
  downsampled projected previews.
- **Large palette memory**: palette is a flat list; O(N) for N blockstates.
  Fine for typical builds (<1000 palette entries).

## Decision log

1. **nbtlib over amulet-core** (2026-07): Python 3.14 has no amulet wheels.
   nbtlib is pure Python and works on 3.11-3.14. Trade-off: hand-rolled Sponge
   NBT schema instead of amulet's multi-format engine.
2. **Delta-based history** (2026-07): full-grid snapshots would be O(N³) per
   undo step; deltas are O(changed voxels). Trade-off: redo requires keeping
   the forward delta too (done).
3. **Shape = pure geometry** (2026-07): shapes return masks, never touch
   blocks. Trade-off: cannot encode "this sphere is stone, that sphere is
   glass" in a single `Union`; must call `session.add` twice. Justified by
   boolean-op simplicity.
4. **Fallback block catalog** (2026-07): keeps the package importable without
   the minecraft-data submodule. Trade-off: common structural and colored team
   blocks are available offline, but exact per-version state coverage still
   requires minecraft-data.
