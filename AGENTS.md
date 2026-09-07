# MARLIN Development Instructions

## Project

MARLIN is an NVIDIA Omniverse Kit application for marine-scene
simulation and rendering.

Main application:
- source/apps/cris.madil.kit

Main custom extension:
- source/extensions/cris.madil.render_service

Main service implementation:
- source/extensions/cris.madil.render_service/cris/madil/render_service/service.py

## Architecture

Omniverse Kit is the rendering/simulation engine.

External software communicates with MARLIN through HTTP endpoints
implemented using NVIDIA Kit Services.

Do not replace this architecture with an unrelated web framework or
standalone renderer.

## Important directories

Edit source files under:
- source/apps/
- source/extensions/

Marine assets are under:
- assets/

Do NOT directly edit generated files under:
- _build/
- extscache/

The built extension under _build may be a symlink to source. Always
make source/ the canonical location for edits.

## Running MARLIN

From:

    ~/kit-app-template/_build/linux-x86_64/release

Launch with:

    ./cris.madil.kit.sh --enable cris.madil.render_service

HTTP API:
- http://localhost:8011
- http://localhost:8011/docs
- http://localhost:8011/openapi.json

## Current marine scene

The project currently supports:
- animated Gerstner-style procedural ocean
- ocean material
- procedural sky and sunlight
- referenced bottlenose dolphin USD asset
- cetacean spawning and transform control
- smooth swimming
- live heading and speed changes
- boundary avoidance
- ocean-surface following
- marine scene one-command setup
- work in progress: depth/dive/surface behaviour

Important endpoint:
- POST /scene/marine/setup

## Dolphin asset

USD:
assets/cetaceans/bottlenose_dolphin/usd/bottlenose_dolphin.usd

The imported dolphin currently requires approximately:
- scale: 100
- orientation correction: X rotation 180 degrees

## Ocean coordinate system

Y is vertical.

Ocean is normally:
- size: 5000
- centred at X=0, Z=0
- approximate domain: -2500 to +2500

Cetacean heading convention:
- 0 degrees = +Z
- 90 degrees = +X
- 180 degrees = -Z
- 270 degrees = -X

## Development rules

1. Preserve existing working endpoints unless intentionally refactoring.
2. Prefer extending existing NVIDIA/Omniverse APIs rather than creating
   unnecessary parallel systems.
3. Do not modify _build artifacts directly.
4. Run Python syntax checks after changing service.py.
5. Avoid restarting Kit unless required because the current USD scene is
   in memory.
6. After restart, POST /scene/marine/setup can reconstruct the marine scene.
7. Treat asset conversion as preprocessing. The dolphin was converted
   externally with Blender; do not depend on omni.kit.asset_converter
   because its native dependency currently has a libxml2 ABI problem on
   this machine.

   ## Generated files

Do not inspect, search, edit, or modify files under:

- _build/
- __pycache__/
- .cache/

Ignore *.pyc files.

The canonical MARLIN source is under:

- source/apps/
- source/extensions/

Marine assets are under:

- assets/