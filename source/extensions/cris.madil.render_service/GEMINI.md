# Render Service Extension Instructions (`source/extensions/cris.madil.render_service/GEMINI.md`)

This directory contains `cris.madil.render_service`, the primary NVIDIA Omniverse Kit extension powering MARLIN's simulation engine, HTTP control plane, and rendering pipelines.

---

## 1. Extension Architecture & Key Modules

| Module | Primary Responsibility |
|---|---|
| `extension.py` | Extension lifecycle (`on_startup`, `on_shutdown`). Registers the HTTP service with `omni.services.core`. |
| `service.py` | Main HTTP routing table using FastAPI / Omniverse Services. Exposes endpoints on port 8011. |
| `scene_setup.py` | Stage orchestration (`/scene/marine/setup`): ocean mesh, lighting, camera, and initial animal prims. |
| `ocean.py` | Procedural Gerstner wave simulation, vertex displacement, ocean height queries at arbitrary `(X, Z)`. |
| `environment.py` / `gentle_environment.py` | Sun, sky atmosphere, and lighting presets (e.g., `gentle-overcast`, legacy demonstration). |
| `camera.py` / `camera_math.py` | Viewport camera manipulation, projection mathematics, and coordinate frame conversions. |
| `hidef_camera.py` | HiDef validation camera model (Prosilica GT6600C, 150 mm, 549 m altitude, 30° pitch, 7.77°/23.17° roll). |
| `sony_camera.py` | Sony ILX-LR1 camera model (85 mm, 150 m altitude, nominal nadir geometry). |
| `cetacean.py` / `cetacean_motion.py` | Spawning, transform updates, heading control, surface-following, and boundary avoidance. |
| `hidef_marine.py` / `native_tiles.py` | Guarded frozen snapshot captures, directional GSD maps, and memory-bounded tiled rendering. |
| `survey_spec.py` / `survey_gallery.py` | GSD sweep definitions (`0.5`, `1.0`, `2.0`, `3.0`, `4.0` cm/px) and survey species specifications. |

---

## 2. API Design & Modification Guidelines

1. **Preserve Working Endpoints:**
   Existing endpoints (such as `/scene/marine/setup`, `/scene/cetacean/swim/*`, `/scene/environment/*`, `/debug/scene/checkpoint/*`, `/debug/viewport/capture`) are used across automated capture scripts and research workflows. **Do not remove or alter existing request/response signatures without explicit direction.**
2. **Modular Architecture:**
   Do not bloat `service.py`. Implement business logic, mathematical algorithms, and USD prim manipulation in dedicated helper modules at package scope, importing them into `service.py` only for route definition.
3. **Pydantic Validation:**
   Define explicit Pydantic request/response models for all new endpoints to guarantee type safety and automatic Swagger documentation generation at `http://localhost:8011/docs`.
4. **No Arbitrary Remote Execution:**
   Never introduce arbitrary shell or unvalidated Python execution endpoints.

---

## 3. Viewport & Rendering Guardrails

- **Guarded Snapshot Pipeline:**
  When capturing survey imagery from a camera:
  1. Record current live stage state, active viewport camera, resolution, selection, and tracked renderer settings.
  2. Pause animal locomotion and ocean updates.
  3. Render the target frame.
  4. **Strictly restore** the live stage, viewport camera, resolution, and renderer settings.
- **GPU Memory Thresholds (RTX A2000 - 6 GB VRAM):**
  Never attempt full-frame unconstrained native rendering (6576×2192) in a single pass. Enforce memory checks before intensive capture operations (minimum 768 MiB free VRAM required). Use tiled capture (`native_tiles.py`) for native resolution.

---

## 4. Coordinate & Simulation Conventions

- **Coordinate System:** `Y` is UP.
- **Heading Angles:**
  - `0° = +Z`
  - `90° = +X`
  - `180° = -Z`
  - `270° = -X`
- **Surface Elevation:** Animals and flying targets must query `ocean.py` wave height at their current `(X, Z)` position rather than assuming a static `Y=0` water plane.

---

## 5. Development & Testing

- Always test Python syntax before running:
  ```bash
  python3 -m py_compile source/extensions/cris.madil.render_service/cris/madil/render_service/*.py
  ```
- Check service health over HTTP when Kit is active:
  ```bash
  curl -sS http://localhost:8011/openapi.json >/dev/null && echo "Render service OK"
  ```
