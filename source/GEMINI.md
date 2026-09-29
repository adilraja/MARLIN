# Source Directory Instructions (`source/GEMINI.md`)

This directory contains the canonical source code for all MARLIN Omniverse Kit applications and custom extensions.

---

## 1. Directory Structure

```
source/
├── apps/
│   ├── cris.madil.kit              # Primary Kit application configuration
│   ├── cris.madil_nvcf.kit         # NVIDIA Cloud Functions (NVCF) headless configuration
│   └── cris.madil_streaming.kit    # WebRTC/streaming Kit configuration
└── extensions/
    ├── cris.madil.render_service/  # Core simulation, rendering, and HTTP service extension
    └── cris.madil.gama_bridge/     # Multi-agent GAMA simulation bridge extension
```

---

## 2. Canonical Source Mandate

- **Source of Truth:** All edits to application configurations (`.kit`), Python code, and extension manifests (`config.extension.toml`) MUST be made here under `source/`.
- **Never Touch `_build/`:** The files under `_build/linux-x86_64/release/` are generated build artifacts or symlinks. Modifying them directly will cause edits to be overwritten or lead to desynchronised state.
- **Python Syntax Checks:** Run `python3 -m py_compile <path_to_file>` after making code edits to ensure syntax correctness before runtime invocation.

---

## 3. Subsystem Pointers

- **Render Service & Simulation:** See [`source/extensions/cris.madil.render_service/GEMINI.md`](extensions/cris.madil.render_service/GEMINI.md) for details on:
  - HTTP service router (`service.py`)
  - Ocean simulation and surface following (`ocean.py`)
  - Camera geometry & projection (`camera.py`, `hidef_camera.py`, `sony_camera.py`)
  - Wildlife spawning & swimming kinematics (`cetacean.py`, `cetacean_motion.py`)
  - Viewport snapshot & restoration guardrails
- **GAMA Integration Bridge:** See [`integrations/gama/GEMINI.md`](../integrations/gama/GEMINI.md) for bridge extension details (`cris.madil.gama_bridge`).
