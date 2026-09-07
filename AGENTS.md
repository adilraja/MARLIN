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

# MARLIN — Codex Working Manual for Adding More Cetaceans

## 1. Project identity

MARLIN stands for:

**Marine Animal Rendering, Locomotion, Interaction and Navigation**

MARLIN is an NVIDIA Omniverse Kit application for interactive marine
simulation.

The current research direction includes:

- realistic marine environments
- procedural/dynamic oceans
- cetacean rendering
- cetacean locomotion
- diving and surfacing
- ocean-animal interaction
- multiple cetacean species
- pod/group behaviour
- synthetic marine imagery
- future aerial-survey and computer-vision experiments


## 2. Repository

Repository root:

    /home/madil/kit-app-template

Main Kit app:

    source/apps/cris.madil.kit

Main MARLIN extension:

    source/extensions/cris.madil.render_service

Primary service implementation:

    source/extensions/cris.madil.render_service/
        cris/madil/render_service/service.py

HTTP service:

    http://localhost:8011

Swagger:

    http://localhost:8011/docs


## 3. Generated directories

Do NOT inspect, search, edit or modify these unless explicitly asked:

    _build/
    __pycache__/
    .cache/
    *.pyc

_build contains the generated Kit runtime and is large.

Canonical source code is under:

    source/

Do not edit generated copies inside _build.


## 4. Important existing functionality

Do not break existing working functionality.

MARLIN currently has:

- procedural animated ocean
- Gerstner-style wave simulation
- shared ocean surface sampling
- ocean/environment creation
- cetacean USD spawning
- cetacean transform control
- swimming
- heading control
- speed control
- boundary avoidance
- ocean-relative vertical following
- diving/surfacing work
- /scene/marine/setup

The existing ocean state is also used by cetacean behaviour.

Do not replace the ocean model merely for visual reasons without preserving
the simulation API used by marine animals.


## 5. Coordinate conventions

Current MARLIN convention:

    Y = vertical

Swimming heading:

    0 degrees   = +Z
    90 degrees  = +X
    180 degrees = -Z
    270 degrees = -X

Current ocean is approximately:

    5000 x 5000 scene units

Do not silently change coordinate conventions.


## 6. Asset conversion

Do NOT use:

    omni.kit.asset_converter

It is currently unusable on this host because of a native libxml2 ABI
dependency problem.

Use the installed official Blender build for source-model conversion.

Current reusable tools:

    tools/gltf_to_usd.py
    tools/convert_cetaceans.sh

Asset pipeline:

    glTF / GLB
        -> Blender
        -> USD
        -> MARLIN calibration


## 7. Cetacean asset layout

Marine assets are stored under:

    assets/cetaceans/

Each species should follow approximately:

    assets/cetaceans/<species>/
        source/
            scene.gltf
            scene.bin
            textures/
            license.txt

        usd/
            <species>.usd
            textures/

Never delete the original source model or licence information.

Licence/provenance must remain associated with each asset.


## 8. Converted marine models

The following models have already been successfully converted to USD:

    bottlenose_dolphin
    cuvier_whale
    frasers_dolphin
    humpback_whale
    manatee
    model_61a_-_bottlenose_dolphin
    pantropical_spotted_dolphin
    pilot_whale
    pygmy_sperm_whale
    sperm_whale
    steno_dolphin

Note:

The manatee is a marine mammal but is not a cetacean.

Do not delete it; MARLIN may later support MarineMammal as a broader
category.


## 9. Important asset issue

Do NOT assume that Blender `obj.dimensions` alone gives the final physical
size of every imported model.

Some glTF assets contain parent EMPTY objects with scale and rotation
transforms.

Therefore local mesh dimensions may differ from effective world-space
dimensions.

The Digital Life bottlenose also contains:

- an armature
- multiple meshes
- an Icosphere/helper object

Do not automatically delete these components.

Inspect their purpose first.


# CURRENT DEVELOPMENT MILESTONE

## 10. Task A — Improve asset measurement

Modify:

    tools/gltf_to_usd.py

so it calculates a combined WORLD-SPACE bounding box for the complete
imported model after all parent transforms have been applied.

Report:

    world bounds minimum
    world bounds maximum
    world dimensions X/Y/Z
    maximum world dimension

The calculation should consider all relevant mesh vertices transformed by
each object's matrix_world.

Do not modify geometry merely to calculate these measurements.


## 11. Task B — Build a cetacean calibration gallery

Add a temporary MARLIN endpoint:

    POST /scene/cetaceans/gallery

Its purpose is asset inspection and calibration.

It should spawn all converted marine models at separated positions above
the ocean so that they can be visually inspected.

Use the existing cetacean/reference spawning mechanisms where possible.

Do NOT duplicate the entire spawning implementation.


Target stage hierarchy should resemble:

    /World/Cetaceans
        Bottlenose_Carimam
        Cuvier_Whale
        Frasers_Dolphin
        Humpback_Whale
        Manatee
        Bottlenose_DigitalLife
        Spotted_Dolphin
        Pilot_Whale
        Pygmy_Sperm_Whale
        Sperm_Whale
        Steno_Dolphin


The gallery is for determining:

- orientation
- forward/nose direction
- upright versus upside-down orientation
- texture correctness
- world-space dimensions
- relative scale
- unwanted/helper geometry
- suitable rotation correction
- suitable scale correction


## 12. Gallery safety requirements

The gallery must NOT:

- replace the current ocean
- modify ocean animation code
- modify existing dolphin behaviour
- modify boundary avoidance
- modify dive logic
- redesign /scene/marine/setup
- introduce a new coordinate system
- refactor unrelated code

Keep this change small and isolated.


## 13. Gallery API response

Return useful calibration information for every spawned model.

Prefer a structure similar to:

    {
      "ok": true,
      "animals": [
        {
          "name": "Humpback_Whale",
          "species": "humpback_whale",
          "prim_path": "/World/Cetaceans/Humpback_Whale",
          "asset_path": "...",
          "position": [...],
          "rotation": [...],
          "scale": ...
        }
      ]
    }

Do not yet invent biological parameters.


## 14. Do NOT create final species scale values yet

The models have not all been visually calibrated.

Do not assume:

    scale = 1

or:

    scale = 100

for every species.

The final values must come from:

1. world-space measurements
2. visual inspection
3. known real-world animal dimensions
4. MARLIN's eventual world-unit convention


## 15. Next architecture AFTER calibration

Do not implement this until the gallery/calibration milestone works.

The next step will be a species registry, for example:

    assets/cetaceans/species_registry.json

Conceptually:

    {
      "humpback_whale": {
        "common_name": "Humpback whale",
        "scientific_name": "Megaptera novaeangliae",
        "asset": "...",
        "rotation_correction": [...],
        "scale_correction": ...,
        "forward_axis": "+Z"
      }
    }

Only populate calibration fields after they have actually been measured.


## 16. Biological behaviour comes later

Eventually species profiles may include:

- body dimensions
- cruising speed
- maximum speed
- turn rate
- normal dive depth
- maximum dive depth
- dive duration
- ascent/descent rate
- surfacing duration
- social/group behaviour

Do NOT invent these numbers.

They must later be grounded in scientific literature.


## 17. Multi-animal simulation comes after the registry

The current swimming architecture historically used a single swimmer state.

The future architecture should support something conceptually like:

    cetacean_swim_states = {
        "Dolphin_001": {...},
        "Humpback_001": {...},
        "PilotWhale_001": {...}
    }

with one efficient Kit update mechanism advancing all active animals.

Do NOT perform this refactor during the gallery task unless explicitly
requested.


## 18. Future pod behaviour

After independent multi-animal swimming works, MARLIN should support pod
spawning and behaviour.

Potential later API:

    POST /scene/cetaceans/pod

Future group behaviour may include:

- cohesion
- separation
- alignment
- leader/centroid following
- individual variation
- different depth profiles
- different response delays

This is NOT part of the current gallery task.


## 19. Coding principles

When changing MARLIN:

1. Prefer small incremental changes.
2. Reuse existing functions.
3. Do not duplicate working logic.
4. Do not rewrite service.py unnecessarily.
5. Preserve existing endpoints unless explicitly asked otherwise.
6. Add validation and useful error responses.
7. Keep helper functions at module scope where appropriate.
8. Avoid generated directories.
9. Keep HTTP APIs suitable for external systems.
10. Do not add arbitrary remote command execution.


## 20. Immediate definition of done

The current milestone is complete when:

1. Blender conversion tooling reports reliable world-space dimensions.
2. `/scene/cetaceans/gallery` exists.
3. All available converted models can be loaded into one MARLIN scene.
4. Every animal appears at a distinct inspection position.
5. Existing ocean and dolphin functionality still work.
6. No final biological parameters have been invented.
7. No final species calibration is assumed without inspection.

Stop after this milestone and report the results before implementing the
species registry or multi-animal behavioural controller.
