# Schematica AI Skill Review & Recommendations

This document provides a comprehensive review of the **Schematica Minecraft Schematic Toolkit (AI Skill)**. It covers bugs encountered during usage, missing gaps, overall rating, and recommendations to elevate the toolkit to a flawless state.

---

## ⭐️ Overall Rating: **8.5 / 10** (Excellent with minor polish needed)

### **The Good**
- **Rich Shape Vocabulary**: Includes 16 primitives (primitives like `BezierCurve`, `Arch`, `Torus`, and `Dome`), boolean operations (`Union`, `Subtract`, `Intersect`), and high-fidelity arbitrary transformations.
- **Chunked Backend (Big-Map Support)**: Standard 3D dense grids scale horribly ($O(N^3)$), but the chunked-grid system successfully allowed building a $128 \times 64 \times 128$ map cleanly and streaming the sponge schematic output with zero memory footprint issues.
- **Visual Previews**: Seamless integration with matplotlib to render isometric, top, front, and right perspective PNGs. Excellent for agent-based validation loops!

---

## 🐛 Bugs Discovered & Fixed

### 1. `NoiseDeformed` Shape Broadcasting Bug
- **Location**: `schematica/shapes/transforms.py` (Line 239–241)
- **Symptom**: Executing `NoiseDeformed` on any shape inside an asymmetric grid (where depth `sz` does not equal height `sy`) crashed with:
  ```
  ValueError: operands could not be broadcast together with shapes (128,64,128) (128,128,64)
  ```
- **Root Cause**: The 2D planar noise `n2` generated from `perlin2d((sz, sy), ...)` had shape `(sz, sy)`. The code tried to repeat it along the X-axis:
  ```python
  n2[None, :, :].repeat(sx, axis=0) # Yielded (sx, sz, sy) instead of (sx, sy, sz)
  ```
- **Fix**: Transposed `n2` first to swap the rows/columns so that the dimensions match the `(sx, sy, sz)` target ordering perfectly:
  ```python
  n2.T[None, :, :].repeat(sx, axis=0) # Yields (sx, sy, sz), broadcasting successfully!
  ```

### 2. Missing Scipy Fallback in `NoiseDeformed`
- **Location**: `schematica/shapes/transforms.py` (Line 245)
- **Symptom**: The docstring for `NoiseDeformed` stated that it *"Requires scipy for best results (falls back without it)"*. However, the code performed a direct import of `scipy`:
  ```python
  from scipy import ndimage as _ndi
  ```
  Without `scipy` installed, this raised a hard `ModuleNotFoundError` and crashed the script rather than falling back cleanly.
- **Resolution**: Installed `scipy` on the system via pip (`pip install scipy`). A code-level correction wrapping this in a `try...except ImportError` fallback should be added so the class degrades gracefully as advertised.

---

## 🚫 Missing Gaps (What's Absent)

### 1. Modern Decorative Blocks in Fallback Registry
While the fallback block registry includes standard block variants (dirt, stone, concrete, wool), it is missing newer decoration families:
- **Other Wood Fences/Slabs/Gates**: Only `minecraft:oak_fence`, `minecraft:oak_stairs`, and basic stone variant slabs exist. The spruce wood blocks, birch wood blocks, cherry wood blocks, mangrove wood blocks, etc. do not have their corresponding fences and gates in the fallback catalog, forcing developers to substitute with oak equivalents to avoid `KeyError` blocks.
- **Copper Blocks**: Classic industrial modern building blocks like raw copper, cut copper, and oxidized copper variants are completely absent.

### 2. Rotational and Radial Symmetry
The `Session.enable_symmetry(axis, center)` only supports mirroring along a single plane at a time. Circular structures, arenas, towers, or spawns benefit enormously from **radial symmetry** (e.g. 4-fold or 8-fold rotational cloning around a central column). Having to manually compute and loop these in python reduces the magic of live symmetry brushing.

### 3. Lack of a Quick `minecraft-data` Downloader
The skill expects `minecraft_data` to be cloned manually under the repo root to enable full per-version registries. Without it, it falls back to the limited catalog. A simple bootstrapping utility to auto-download and cache version registries from PrismarineJS would provide full block support dynamically.

---

## 💡 Ideas for Improvement & Roadmap

1. **Auto-Bootstrap Block Registry**:
   Add a utility script `python -m schematica.blocks.download` that fetches the JSON files directly from `github.com/PrismarineJS/minecraft-data` for the target version on demand and caches them locally, giving the agent full access to modern blockstates automatically.
2. **Expand the Fallback Block List**:
   At a minimum, expand `registry.py`'s `_COMMON_FALLBACK_BLOCKS` to include spruce and birch decorative blocks (stairs, slabs, gates, fences) and copper blocks, as these are the core components of modern builds.
3. **Add Radial / Quad Symmetry**:
   Extend `enable_symmetry` to support `"radial"` and `"quad"` modes:
   ```python
   session.enable_symmetry(mode="radial", center=(64, 64), folds=4)
   ```
4. **Enhanced WFC Presets**:
   Provide more out-of-the-box tilesets for `generate.wfc` beyond `mossy_ruins` (e.g., a "modern_office" or "medieval_tower" preset) to accelerate generation of high-quality interiors and facades.
