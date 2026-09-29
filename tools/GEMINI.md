# Tools Directory Instructions (`tools/GEMINI.md`)

This directory contains standalone Python utilities, Blender-based asset conversion pipelines, capture orchestration tools, and diagnostic test scripts.

---

## 1. Asset Conversion Pipeline (Blender 5.0.1)

- **Blender Conversion Mandate:**
  Do **NOT** use `omni.kit.asset_converter`. It is unusable on this host due to a native `libxml2` ABI dependency conflict.
  All glTF/GLB to USD conversions must be processed using the installed official Blender build (`/usr/bin/blender`):
  ```bash
  tools/convert_cetaceans.sh
  # Or invoke conversion script directly via Blender:
  blender --background --python tools/gltf_to_usd.py -- <input.gltf> <output.usd>
  ```
- **World-Space Dimensions vs Local Dimensions:**
  Do **NOT** assume `obj.dimensions` in Blender gives the physical size. Many glTF models contain parent `EMPTY` objects with rotation and scale hierarchies.
  `tools/gltf_to_usd.py` must compute the combined **world-space bounding box** (`matrix_world` transformed mesh vertices) to report:
  - World bounds minimum & maximum
  - World dimensions (X, Y, Z)
  - Maximum world dimension
- **Armatures & Helper Objects:**
  Some models (such as the Digital Life bottlenose dolphin) include armatures, multiple sub-meshes, or helper objects (e.g. Icospheres). Inspect their purpose before removing or baking.

---

## 2. Capture & Camera Orchestration Scripts

| Script | Purpose |
|---|---|
| `capture_hidef_marine.py` | Orchestrates HiDef oblique snapshot capture (`1644x548` preview or `--native` tiled capture). Supports `--replay <capture_id>`. |
| `capture_sony_marine.py` | Orchestrates Sony ILX-LR1 preview capture (`1188x792` at 5.3 cm/preview px). Supports `--replay <capture_id>`. |
| `capture_calibration_target.py` | Renders and measures known metric planar targets for camera geometry calibration. |
| `verify_capture_projection.py` | Validates projected pixel coordinates and ground sampling distances against theoretical geometry. |
| `analyse_tile_diagnostics.py` | Compares seam consistency and pixel overlap across native capture tiles. |

### Snapshot Replay Safety
When using `--replay <capture_id>`:
- The script loads the saved frozen stage (`scene.usdc`) even if live animals have moved.
- Replay strictly refuses execution if tracked renderer settings or texture file hashes have changed.
- Do NOT bypass memory checks or force reruns if low-memory warnings are triggered.

---

## 3. Testing & Verification

- **Standalone CPU Unit Tests:**
  ```bash
  /usr/bin/python3 -m unittest discover tools -p "test_*.py"
  ```
- **USD (`pxr`) Dependent Tests:**
  When tests require USD Python bindings (`pxr.Usd`, `pxr.UsdGeom`, `pxr.Gf`) outside the running Kit instance, execute them via Blender's embedded Python:
  ```bash
  blender --background --python-expr "import sys, unittest; sys.path.insert(0, 'tools'); unittest.main(module=None, argv=['unittest', 'discover', 'tools', '-p', 'test_*.py'])"
  ```
