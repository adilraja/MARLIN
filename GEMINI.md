# MARLIN Project Instructions (GEMINI.md)

MARLIN (**M**arine **A**nimal **R**endering, **L**ocomotion, **I**nteraction and **N**avigation) is an NVIDIA Omniverse Kit simulation platform and experimental instrument for synthetic marine environments, wildlife locomotion, and digital aerial wildlife survey experimentation.

---

## 1. System Architecture & Fundamental Rules

- **Core Engine:** NVIDIA Omniverse Kit. Main application: `source/apps/cris.madil.kit`.
- **Primary Extension:** `source/extensions/cris.madil.render_service` (HTTP API served via NVIDIA Kit Services).
- **Service Endpoint:** `http://localhost:8011` (Swagger UI: `http://localhost:8011/docs`, OpenAPI: `http://localhost:8011/openapi.json`).
- **Canonical Source Tree:** All edits MUST be made under `source/` or `tools/`.
  - **STRICT RULE:** NEVER directly edit, search, or inspect generated files under `_build/`, `extscache/`, `__pycache__/`, or `.cache/`. `_build/` contains generated/symlinked runtime outputs.
- **Single Kit Instance Mandate:** Omniverse Kit maintains the active USD stage in GPU/CPU memory. **NEVER** launch a second Kit instance while one is running. Always verify or query the existing instance over HTTP before touching runtime state.
- **Coordinate System Conventions:**
  - Vertical axis: `Y` is UP.
  - Heading convention: `0° = +Z`, `90° = +X`, `180° = -Z`, `270° = -X`.
  - Ocean domain: Approximately 5000 × 5000 scene units, centred at `X=0, Z=0`.
- **Source Control Safety:** NEVER stage or commit git changes unless explicitly requested by the user.

---

## 2. Current Research Priority: First End-to-End GSD Experiment Sprint

The project has transitioned from simulator development to scientific experimentation: **quantifying Ground Sampling Distance (GSD) requirements for automated wildlife detection and classification in digital aerial surveys.**

### Key Experimental Parameters
- **GSD Sweep Levels:** `0.5 cm/px`, `1.0 cm/px`, `2.0 cm/px`, `3.0 cm/px`, `4.0 cm/px`. GSD is the primary independent variable.
- **Controlled Fixed Environment:** Calm sea, overcast/diffuse lighting, no sun glint, zero precipitation, frozen renderer settings (e.g. `gsd_baseline_v1` preset). **Do not introduce weather/domain randomisation into GSD experiments.**
- **Initial Target Animals:** Exactly TWO validated species (ONE bird, ONE cetacean) for the pilot sprint.
- **Paired Renders:** For every unique scene seed (25–50 seeds), render the identical biological scene across all 5 GSD levels.
- **Ground-Truth Annotations:** Direct projection from synthetic scene data (species, 2D bounding box, centroid, world position, heading, depth/altitude, local GSD, pixels on target).
- **Leakage Prevention:** Train/validation/test splits MUST be split by **scene seed**, never by individual rendered images.
- **Preservation of Existing Assets:** The existing converted cetacean library must remain intact. Do not discard assets.

---

## 3. Essential Commands & Workflows

### Starting MARLIN
```bash
# Terminal 1: Launch Kit with Render Service
cd /home/madil/kit-app-template/_build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service

# Terminal 2: Verify service readiness
curl --fail -sS http://localhost:8011/openapi.json >/dev/null && echo "MARLIN API ready"
```

### Visual Checkpoints & Scene Setup
```bash
# Save a visual checkpoint (scene, camera, tracked settings)
curl --fail-with-body -sS -X POST http://localhost:8011/debug/scene/checkpoint

# Restore visual checkpoint in a fresh Kit session
curl --fail-with-body -sS -X POST http://localhost:8011/debug/scene/checkpoint/<checkpoint_id>/restore

# Standard single-dolphin demonstration scene
curl --fail-with-body -sS -X POST http://localhost:8011/scene/marine/setup -H 'Content-Type: application/json' -d '{"underwater_cue":false}'

# Apply gentle overcast environment preset
curl --fail-with-body -sS -X POST http://localhost:8011/scene/environment/gentle-overcast
```

### Viewport Capture & Camera Pipelines
```bash
# Quick viewport capture (saved to /tmp/marlin_viewport.png)
curl --fail-with-body -sS -X POST http://localhost:8011/debug/viewport/capture

# HiDef oblique marine snapshot (preview 1644x548)
python3 tools/capture_hidef_marine.py

# Replay an existing HiDef snapshot
python3 tools/capture_hidef_marine.py --replay <capture_id>

# Sony ILX-LR1 nadir preview capture (1188x792)
python3 tools/capture_sony_marine.py
```

---

## 4. Subdirectory Instructions Index

Specialized guidance for each core subsystem is maintained in dedicated `GEMINI.md` files:

1. **`source/GEMINI.md` & `source/extensions/cris.madil.render_service/GEMINI.md`**
   - Omniverse Kit application definitions (`source/apps/`).
   - Extension architecture, HTTP endpoint routes, ocean simulation, motion kinematics, camera geometry, viewport snapshot & restoration rules.
2. **`tools/GEMINI.md`**
   - Blender 5.0.1 asset conversion pipeline (`gltf_to_usd.py`, `convert_cetaceans.sh`).
   - World-space bounding box calculations, snapshot capture runners, and test execution conventions.
3. **`assets/GEMINI.md`**
   - 3D asset directory structure (`source/` glTF vs `usd/`), provenance and licensing requirements.
   - Survey wildlife taxonomy, flight vs on-water states, and machine-readable calibration records.
4. **`integrations/gama/GEMINI.md`**
   - GAMA agent-based simulation bridge, trajectory replay, counterfactual verification, and sprint isolation rules.

---

## 5. Development & Engineering Standards

- **Small Incremental Changes:** Reuse existing spawning, camera, and service mechanisms. Do not perform large unsolicited refactors of `service.py`.
- **Python Syntax Verification:** Always run syntax validation (`python3 -m py_compile <file>`) after modifying Python sources.
- **Scientific Safeguards:** Never invent biological parameters (dimensions, speeds, diving limits). Mark unverified measurements explicitly as `"provisional"`.
- **Memory Guardrails:** The host GPU is an NVIDIA RTX A2000 (6 GB VRAM). Never lower memory safety thresholds or attempt unconstrained full-frame RTX allocations.
