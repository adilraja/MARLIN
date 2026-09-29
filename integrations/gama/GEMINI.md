# GAMA Integration Instructions (`integrations/gama/GEMINI.md`)

This directory contains documentation, trajectory exchanges, and calibration artifacts connecting the GAMA agent-based simulation platform to MARLIN.

---

## 1. Architectural Scope & Current Sprint Boundary

- **Engineering Integration, Not Biological Truth:**
  The GAMA bridge exists to test step-synchronised agent control and trajectory exchange between an external simulation engine and Omniverse Kit.
  **GAMA animal behaviour is NOT biologically validated.**
- **Sprint Isolation Mandate:**
  Under the current **First End-to-End GSD Experiment Sprint**, GAMA development is **FROZEN**.
  The synthetic GSD sweep experiment (detection/classification performance vs GSD) must NOT depend on GAMA. Do not expand GAMA behaviours or add flocking/pod dynamics until the GSD paper pipeline is complete.

---

## 2. Bridge Extension & Tools

- **Kit Bridge Extension:**
  Located in `source/extensions/cris.madil.gama_bridge/`:
  - `actor.py`: Spawns and manages step-driven USD target prims.
  - `exchange.py`: Parses JSON/socket step trajectory payloads.
  - `counterfactual.py`: Verifies deterministic replay against reference trajectories.
- **Standalone Diagnostic Tools:**
  Located under `tools/`:
  - `tools/gama_live.py`: Step-controlled socket coordinator client.
  - `tools/gama_trajectory.py`: Offline trajectory replay runner.
  - `tools/test_gama_actor.py` & `tools/test_gama_exchange.py`: Trajectory deserialisation and transform unit tests.

---

## 3. Safe Execution Protocol

- **Dedicated Bridge Launch:**
  The standard MARLIN launch does not enable the GAMA bridge. When conducting verified trajectory tests, launch Kit with the extension explicitly enabled:
  ```bash
  cd /home/madil/kit-app-template/_build/linux-x86_64/release
  ./cris.madil.kit.sh --enable cris.madil.render_service \
    --ext-folder /home/madil/kit-app-template/source/extensions \
    --enable cris.madil.gama_bridge
  ```
- **Single Instance Warning:**
  Do NOT launch a second Kit instance if MARLIN is already running in another terminal.
- **Isolated Target:**
  When executing GAMA trajectory tests, control ONLY the designated isolated test animal (e.g. `gama_dolphin`), leaving other presentation and survey assets untouched.
