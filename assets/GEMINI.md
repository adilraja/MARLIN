# Assets Directory Instructions (`assets/GEMINI.md`)

This directory houses all 3D wildlife assets, textures, provenance metadata, and converted USD stages for marine animals and seabirds.

---

## 1. Directory Structure & Layout

Each animal asset must maintain a clean separation between raw source data and converted runtime assets:

```
assets/
├── cetaceans/<species_name>/
│   ├── source/
│   │   ├── scene.gltf / scene.glb
│   │   ├── scene.bin
│   │   ├── textures/
│   │   └── license.txt          # Mandatory: licence and attribution
│   └── usd/
│       ├── <species_name>.usd   # Converted USD asset ready for USD referencing
│       └── textures/
├── survey_species/<species_name>/
│   └── ...                      # Calibrated survey targets
├── avians/                      # Downloaded avian sources
└── birds/                       # Rigged/calibrated seabird assets
```

---

## 2. Provenance & Preservation Mandate

- **Preserve Source Data:** NEVER delete source glTF/GLB files, texture originals, or licensing information (`license.txt`). Attribution and source provenance must remain permanently associated with every asset.
- **Retain the Full Cetacean Library:**
  The 11 previously converted marine mammal assets must be retained regardless of current sprint priorities:
  - `bottlenose_dolphin`
  - `cuvier_whale`
  - `frasers_dolphin`
  - `humpback_whale`
  - `manatee` (preserved for broader Marine Mammal classification)
  - `model_61a_-_bottlenose_dolphin`
  - `pantropical_spotted_dolphin`
  - `pilot_whale`
  - `pygmy_sperm_whale`
  - `sperm_whale`
  - `steno_dolphin`

---

## 3. Survey Species Taxonomy & Biological States

### Target Groups & Species
- **Avian Groups (6 groups, 7 species):**
  - Storm Petrels (*European storm petrel*)
  - Shearwaters (*Manx shearwater*)
  - Terns (*Common tern*)
  - Small Gulls (*Kittiwake*)
  - Auks (*Guillemot* and *Razorbill*)
  - Gannet (*Northern gannet*)
- **Non-Avian Targets:**
  - *Harbour porpoise*
  - *Common dolphin*
  - *Risso's dolphin*
  - *Minke whale*

### Required Biological States
- **Birds:** Must support at least two distinct operational states:
  - `sitting_on_water` (conforms to wave surface elevation via `ocean.py`)
  - `in_flight` (altitude above sea must be recorded as it alters effective local GSD)
- **Cetaceans:**
  - `surface`
  - `shallow_swim`
  - `shallow_dive`

---

## 4. Calibration & Dimensional Standards

- **No Invented Measurements:**
  Never invent physical lengths, wingspans, swimming speeds, or dive limits. Ground all numbers in scientific literature.
- **Provisional Status:**
  When exact physical measurements or calibration parameters have not yet been empirically validated or referenced, explicitly record:
  ```json
  "status": "provisional"
  ```
- **Machine-Readable Calibration Record Schema:**
  Calibrated wildlife parameters must be tracked cleanly in machine-readable JSON:
  ```json
  {
    "species": "harbour_porpoise",
    "scientific_name": "Phocoena phocoena",
    "asset_path": "assets/survey_species/harbour_porpoise/usd/harbour_porpoise.usd",
    "license": "CC-BY",
    "physical": {
      "reference_length_m": 1.55,
      "reference_wingspan_m": null,
      "provenance": "Literature citation"
    },
    "asset_calibration": {
      "scale": 1.0,
      "rotation_correction_deg": [0, 0, 0],
      "forward_axis": "+Z",
      "up_axis": "+Y"
    },
    "validated_states": ["surface", "shallow_swim"]
  }
  ```
