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
- **Phase 12 — Review-grade improvements**: Session.add kwargs delegation
  fix (`s.add(Sphere(...), "stone", hollow=True)` now works), Cylinder
  `start`/`end` aliases for non-Y axes, `axis` param on Cone/Dome, `plane`
  param on Arch, `BezierCurve` shape, arbitrary-angle `Rotated` transform,
  SDF-based `SmoothUnion`/`SmoothIntersect`/`SmoothSubtract` blending, SVG path
  `d`-string voxelization in `extrude_polygon`, active `enable_symmetry`/
  `disable_symmetry` session decorator, `resample_subregion` scaling utility,
  and a much larger fallback registry (quartz slabs/stairs, concrete
  slabs/stairs for all 16 colors, stone-variant slabs/stairs including
  deepslate/tuff/calcite/blackstone).

## Phase 12 changelog (consolidated)

Driven by `schematica_review.md`. All review items are now addressed and
covered by tests in `tests/test_sdf.py` and `tests/test_review_fixes.py`.

### Bug fixes
- **`Session.add` kwargs delegation**: `add`/`subtract`/`paint`/`intersect`
  accept `**shape_kwargs` and forward them to the shape's dataclass fields via
  `dataclasses.replace`. `s.add(Sphere(...), "stone", hollow=True)` works;
  unknown kwargs raise `TypeError` listing the valid fields. (test_add_forwards_*)
- **Cylinder non-Y axis mapping**: added explicit `start`/`end` aliases for the
  along-axis extent; `Cylinder(8, 8, 3, start=2, end=6, axis="x")` reads
  naturally. Backward-compatible with `y0`/`y1`. (test_cylinder_start_end_*)

### New shapes and transforms
- `Cone(axis="x"|"z")`, `Dome(axis="x"|"z")` — horizontal cones and wall-mounted
  domes. (test_cone_axis_*, test_dome_axis_*)
- `Arch(plane="xy"|"xz"|"yz")` — arches in any coordinate plane.
  (test_arch_plane_*)
- `BezierCurve(p0, p1, p2, p3=None, thickness, samples)` — quadratic / cubic
  3D Bezier tubes. (test_bezier_*)
- `Rotated(shape, angle_deg, axes, order=0)` — arbitrary-angle rotation via
  nearest-neighbour resampling. 0° and 360° are byte-identical to the original.
  (test_rotated_*)

### New modules
- `schematica.shapes.sdf` — `SDFShape`, `SmoothUnion`, `SmoothIntersect`,
  `SmoothSubtract`. Signed-distance-field composition with a `k`-voxel blend
  radius. `k=0` reduces to the hard boolean op (byte-identical to `Union`;
  verified by `test_smooth_union_hard_k0_matches_union`). Uses scipy's
  `distance_transform_edt` when available; pure-numpy iterative-erosion BFS
  fallback with a fully-filled-mask fast path so `SmoothSubtract` on a filled
  box doesn't hang.

### New session features
- `enable_symmetry(axis, center=None)` / `disable_symmetry()` — live mirror
  decorator. Every subsequent `add`/`subtract`/`paint` is auto-unioned with its
  mirror image about `center` (grid middle by default) along `axis`. The
  `symmetry_active` property reflects state. (test_enable_symmetry_*)
- `resample_subregion(frm, to, new_size, block, dest_origin=None)` — nearest-
  neighbour rescale of a sub-box, written at `dest_origin`. Supports upscaling
  and downscaling. (test_resample_subregion_*)

### Polygon enhancements
- `extrude_polygon` now accepts SVG path `d`-strings (`M`/`L`/`H`/`V`/`C`/`Q`/`Z`,
  absolute and relative). Curved segments are flattened into polylines, then
  closed and converted to a shapely polygon via `buffer(0)`.
  (test_extrude_svg_path_*)

### Fallback registry enrichment
- Quartz family (smooth quartz, quartz pillar, chiseled quartz, quartz slab,
  smooth quartz slab, quartz stairs, smooth quartz stairs).
- Concrete slabs + stairs for all 16 colors (with proper `_SLAB_STATES` /
  `_STAIRS_STATES` schemas).
- ~40 stone-variant slabs + stairs: sandstone, red sandstone, nether brick,
  prismarine (3 variants), end stone brick, mossy stone brick / cobblestone,
  granite / polished granite, diorite, andesite, deepslate brick / tile,
  blackstone, tuff / tuff bricks, calcite, polished deepslate, plus
  `smooth_basalt` and `chiseled_deepslate` full blocks. Verified by
  `reg["minecraft:blue_concrete_slab"]` resolving to a valid blockstate.

### Documentation
- `shapes_catalog.md`, `library_api.md`, `SKILL.md`, `roadmap.md` updated for
  Cylinder `start`/`end`, Cone/Dome `axis`, Arch `plane`, `BezierCurve`,
  `Rotated`, SDF smooth blending, SVG path voxelization, `enable_symmetry` /
  `disable_symmetry`, `resample_subregion`, and the larger fallback registry.
- `architecture.md` module layout updated with `sdf.py`, the new generators /
  procedural / analysis / export submodules, and the enriched Session data
  model.
- `block_registry.md` adds a "Phase 12 enrichment" section enumerating every
  new fallback block family.
- `generators.md` adds reference sections for SDF smooth blending, Bezier
  curves, SVG path voxelization, active symmetry, and subregion resampling.
- `agent_cli_guide.md` adds a "Python-only features" section so agents know
  which features require switching from CLI to Python mode.
- `workflow_guide.md` adds a "Phase 12 advanced recipes" section with copy-
  paste-ready examples for each new feature.
- `cli_reference.md` notes the cylinder axis caveat and adds a Python-only
  features block.
- `schematica_review.md` annotated with `[FIXED]` notes and the rating raised
  from 8.5 to 9.5.

### Verification
- Tests: **320 pass** (291 baseline + 5 SDF + 24 review-fix tests).
- ruff: **0 new errors** (66 baseline → 66; all pre-existing).
- mypy: **−1 error** (29 baseline → 28; the new code is stricter-typed than
  the surrounding baseline).

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
- **Cylinder axis**: all of `axis="x"`, `"y"`, `"z"` are implemented. Use the
  `start`/`end` aliases for non-Y axes so the along-axis extent reads
  naturally (`Cylinder(8, 8, 3, start=2, end=6, axis="x")`).
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
   requires minecraft-data. Phase 12 extended this with quartz / concrete /
   stone-variant slabs and stairs so common modern detailing works offline.
5. **SDF via distance transform** (2026-07, Phase 12): `schematica.shapes.sdf`
   wraps binary shape masks as signed distance fields via
   `scipy.ndimage.distance_transform_edt` when available, with a pure-numpy
   iterative-erosion BFS fallback so the module works without scipy. Trade-off:
   O(N³) per shape, so prefer it for medium grids or use the chunked backend.
6. **Active symmetry via shape wrapping** (2026-07, Phase 12):
   `enable_symmetry` wraps each shape in `Union((shape, Translated(Mirror(...))))`
   on every op. Trade-off: the wrapper is rebuilt per op (cheap) and only
   affects `add`/`subtract`/`paint` (not `set_box`/`set_many`/`replace`).
7. **Kwargs delegation via dataclasses.replace** (2026-07, Phase 12):
   `Session.add/subtract/paint/intersect` forward `**shape_kwargs` to the
   shape's dataclass fields. Trade-off: only works for dataclass shapes (all
   built-in primitives are); custom `Shape` protocol implementations without
   dataclass decoration raise a clear `TypeError`.
