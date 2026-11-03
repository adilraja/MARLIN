"""Freeze the tested preset, reproduction recipe and human-review candidate."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
BASE=REPO/'experiments/ocean_material_v1'
PACKAGE=BASE/'presets/engineering_v1'


def load(path):
    return json.loads(path.read_text())


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.relative_to(REPO)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    analysis=load(ROOT/'analysis.json')
    assert analysis['all_pair_invariants_passed'] and analysis['all_reload_rollback_checks_passed']
    animated=load(ROOT/'qa/live_animation/verification.json')
    assert animated['phase_advanced'] and animated['engineering_binding_retained']
    final=load(ROOT/'qa/final_live_verification.json')
    assert all(final['checks'].values())
    preparation=load(ROOT/'runs/attempt01/preparation.json')
    case=load(ROOT/'runs/attempt01/engineering_intersecting/metadata.json')
    runtime=load(ROOT/'runs/attempt01/runtime.json')
    asset=REPO/'assets/cetaceans/model_61a_-_bottlenose_dolphin'
    license_path=asset/'source/license.txt'
    shutil.copyfile(license_path,PACKAGE/'ASSET_LICENSE.txt')
    snapshots=PACKAGE/'source_snapshot'
    snapshots.mkdir(exist_ok=False)
    source_root=REPO/'source/extensions/cris.madil.render_service/cris/madil/render_service'
    source_pins=[]
    for name in ('ocean_medium.py','ocean_enclosure.py','water_material.py','ocean.py'):
        path=source_root/name
        source_pins.append(pin(path))
        shutil.copyfile(path,snapshots/name)
    parameters=REPO/'source/extensions/cris.madil.render_service/config/ocean_medium_engineering_v1.json'
    assert hashlib.sha256(parameters.read_bytes()).hexdigest()==hashlib.sha256((PACKAGE/'parameters.json').read_bytes()).hexdigest()
    dependencies=preparation['dependencies']
    local=[]
    for item in dependencies:
        if item['status']=='local_hashed':
            path=Path(item['path'])
            entry=pin(path)
            assert entry['sha256']==item['sha256']
            local.append(entry)
    local += [pin(asset/'usd/model_61a_-_bottlenose_dolphin.usd'),pin(license_path)]
    write(PACKAGE/'dependency_manifest.json',dict(water_mdl=dict(asset='OmniSurface.mdl',subidentifier='OmniSurface',
          bundled_source_copied=False,runtime_file_inspected=False,kit_build=runtime['kit_build']),
          water_texture_assets=[],local_animal_dependencies=local,canonical_source_pins=source_pins,
          parameter_source=pin(parameters),runtime_resolved_references=dependencies,
          source_asset_credit='Model 61A - Bottlenose Dolphin by DigitalLife3D, CC-BY-NC-4.0; original licence preserved'))
    selected=case['preset_configuration']
    write(PACKAGE/'geometry_requirements.json',dict(up_axis='Y',meters_per_unit=preparation['world_units_m'],
          current_existing_ocean_size_units=16000,resolution=selected['resolution'],
          top_vertices=16641,top_quad_faces=16384,closed_vertices=case['ocean_vertices'],closed_quad_faces=case['ocean_faces'],
          bottom_depth_m=selected['bottom_depth_m'],horizontal_derivative_bound=selected['horizontal_derivative_bound'],
          requirements=['Use the existing grid, wave equations, sampler and translation-only ocean transform',
                        'Consistently oriented closed side/bottom medium boundary; original top points and sampler retained',
                        'Select original before changing ocean geometry/unit convention'],configuration=selected))
    position=(np.linalg.inv(np.array(case['projection']['capture_view_matrix']))[3,:3]*preparation['world_units_m']).tolist()
    capture=dict(mode='PathTracing',size_px=[512,384],camera_path='/World/MarlinOceanM6Camera',
          actual_camera_position_m=position,camera_config=preparation['camera_config'],
          physical_near_m=.01,physical_far_m=preparation['camera_physical_far_m'],
          effective_camera_product=load(ROOT/'runs/attempt01/engineering_intersecting/effective_settings.json'),
          global_settings=case['global_settings'],projection=case['projection'],
          capture_sdk='omni.kit.viewport.utility capture_viewport_to_file/buffer',
          output='Native HdrColor NPZ and EXR; fixed HDR display PNG',
          primary_display='round(255*clip(rgb/12000,0,1)**(1/2.2)) cast to uint8',
          review_display='round(255*clip(log1p(max(rgb,0))/log1p(12000),0,1)) cast to uint8',
          per_image_normalization=False,native_ldr_png_qualified=False,
          rendered_frame_wait=64,rendered_frame_timeout_seconds=30,per_image_timeout_seconds=60,
          capture_guard_free_mib=768,renderer_startup_guard_free_mib=2048,
          actual_hardware_sample_counts_measured=False,
          tested_runtime=runtime['kit_build'],tested_driver='595.99.02',fresh_process_reload_supported=True,
          original_in_process_m6_reload_failed=True,inside_camera_qualified=False)
    write(PACKAGE/'capture_settings.json',capture)
    write(PACKAGE/'qualification.json',dict(version='engineering_v1',technical_checks='passed_for_declared_above_water_camera_HDR_configuration',
          material_source_unchanged=True,animal_mesh_scale_material_pose_orientation_unchanged=True,
          camera_stays_above_water_for_all_animal_poses=True,geometry_and_physical_settings_recoverable=True,
          fresh_process_reload_and_rollback_passed=True,animated_ocean_current_driver_capture_passed=True,
          human_acceptance='See diagnostics/m6/review_state.json; technical package does not grant human acceptance',
          m4_camera_inside_qualified=False,native_ldr_png_qualified=False,scientific_water_calibrated=False,
          wildlife_survey_validated=False,full_sprint_complete=False))
    sources=ROOT/'qa/offline_regressions.json'
    rows=load(sources)
    count=skipped=0
    for row in rows:
        if row['module']=='underwater_cue':
            row=load(ROOT/'qa/underwater_cue_corrected_invocation.json')
        assert row['returncode']==0
        text=row['stdout']+row['stderr']
        count+=int(re.search(r'Ran (\d+) tests?',text).group(1))
        skip=re.search(r'skipped=(\d+)',text)
        skipped+=int(skip.group(1)) if skip else 0
    write(ROOT/'qa/regression_summary.json',dict(discovered_tests=count,passed_tests=count-skipped,skipped_tests=skipped,
          skipped_reason='Two pure-USD calibration checks lacked pxr in the external system interpreter; actual Kit checks ran independently',
          initial_underwater_cue_import_failure_preserved=True,corrected_module_path_retry_passed=True,
          runtime_phase_cases=5,runtime_controller_cases=2,actual_live_ocean_updates=10))
    review=dict(reviewer='MAR',status='pending',acceptance_received=False,
          requested_scope='Engineering acceptance of the demonstrated material/medium configuration on the unchanged dolphin',
          not_claimed=['Real-seawater calibration','Biological validity','Wildlife-survey validation','Camera-inside attenuation support'],
          material_comparison='figures/material_comparison.png',annotation_comparison='figures/geometric_annotation_comparison.png',
          specification='Sprints/CurrentSprint/MARLIN_OCEAN_MATERIAL_SPRINT_SPECIFICATION.md:281')
    if not (ROOT/'review_state.json').exists():
        write(ROOT/'review_state.json',review)
    write(ROOT/'technical_acceptance_summary.json',dict(
          technical_checks_passed=True,paired_animal_captures=6,fresh_process_reload_captures=1,rollback_captures=1,
          animated_capture=1,canonical_source_files_unchanged=113,
          human_review_pending=True,m6_full_acceptance=False,m4_complete=False,full_sprint_complete=False,
          original_in_process_reload_qualified=False,fresh_process_reload_qualified=True,
          native_ldr_png_qualified=False,driver_mismatch_resolved=True))

    readme='''# MARLIN engineering water preset v1

This package freezes the existing `engineering_v1` parameters and exported material, with the closed-medium requirements and tested capture configuration. The parameter JSON is preserved byte for byte from canonical source; its older status text is provenance. `qualification.json` describes the newer M5/M6 checks. Human acceptance is recorded separately in `../../diagnostics/m6/review_state.json`.

**Supported:** the tested above-water camera, original and engineering water comparisons, 512 × 384 PathTracing native HDR/EXR plus a deterministic display conversion, and fresh-process reload/rollback. **Unqualified:** inside-water camera attenuation, useful native LDR PNG under this exposure, native HiDef/Sony output, and real-world optical/biological/survey validity. The initial M6 in-process stage switch exited before completing; fresh-process reload is the validated path.

## Contents and dependencies

- `parameters.json`: original measured parameter/configuration source.
- `material.usda`: exported `/World/Looks/OceanWaterEngineeringV1` with native `OmniSurface.mdl` binding; no water textures.
- `geometry_requirements.json`: unchanged top surface, closed sides/bottom, 20 m depth, Y-up and centimetre units.
- `capture_settings.json`: actual camera/product/global controls, projection, runtime and fixed display mappings.
- `demonstration_scene.usdc`: frozen engineering intersecting-animal scene used in the accepted fresh-process replay. It retains repository-local animal texture dependencies; it is not a standalone redistributable asset bundle.
- `dependency_manifest.json`, `source_snapshot/`, `ASSET_LICENSE.txt`: source pins, texture/model hashes and provenance. Native vendor runtime files are referenced by name/version and were not copied or inspected.

The demonstration uses "Model 61A - Bottlenose Dolphin" by DigitalLife3D, licensed under CC-BY-NC-4.0. The original source attribution, links and terms are retained in `ASSET_LICENSE.txt`; no source model or licence was removed.

## Apply and roll back through the existing service

Run the normal MARLIN application and checkpoint any current work first:

```sh
curl -sS -X POST http://localhost:8011/debug/scene/checkpoint
curl -sS -X POST http://localhost:8011/scene/marine/setup -H 'Content-Type: application/json' -d '{"start_swimming":false}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset -H 'Content-Type: application/json' -d '{"selection":"engineering_v1","configure_renderer":false}'
```

The last call changes binding/medium geometry only; it does not claim that an arbitrary viewport/camera has the tested capture settings. The exact capture configuration is in `capture_settings.json` and in the frozen scene. Use the original selection before changing ocean geometry or units.

```sh
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset -H 'Content-Type: application/json' -d '{"selection":"original"}'
curl -sS -X POST http://localhost:8011/scene/marine/setup -H 'Content-Type: application/json' -d '{"start_swimming":false}'
```

The second rollback command reconstructs the standard scene and controller phase; it does not restore an exact animation clock. Restore an existing checkpoint through `/debug/scene/checkpoint/<checkpoint_id>/restore` to recover its frozen visual state instead. Checkpoints do not restart procedural controllers.

## Reproduce a fresh-process capture

From the repository root, verify the sealed package first. Checkpoint and close any running Kit application before starting the replay; the launcher refuses a duplicate and requires 2,048 MiB free. Use an unused two-digit identifier, such as 02, to preserve all earlier outputs.

```sh
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/verify_package.py
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/launch_reload.py --attempt 02
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/convert_hdr.py --input experiments/ocean_material_v1/diagnostics/m6/runs/reload_process02/reload_intersecting/hdr.npz --output experiments/ocean_material_v1/diagnostics/m6/runs/reload_process02/reload_intersecting/hdr_display.png
```

This uses the saved selected scene and the same native SDK route, then tests original-material rollback. The capture code used for accepted process01 is archived beside the audit; the current wrapper adds new-output selection and graceful termination after saved results if a posted quit does not exit promptly. No material/camera/sampling retuning is required in this repository layout. On another machine, provide the listed local assets and remap repository paths; do not assume the frozen scene is self-contained.

To return to the standard live app after replay, launch the documented existing application, restore the checkpoint saved before closing it and reconstruct controllers as needed. Do not run a second renderer concurrently.
'''
    (PACKAGE/'README.md').write_text(readme)

    table=[]
    for pose,pair in analysis['pair_invariants'].items():
        record=load(ROOT/analysis['capture_directories']['original_'+pose]/'metadata.json')
        ymin=record['animal']['world_bounds_min'][1]*.01
        ymax=record['animal']['world_bounds_max'][1]*.01
        table.append(f"| {pose} | {ymin:.3f} to {ymax:.3f} m | {pair['review_log_box_mean_absolute_difference_8bit']:.2f} | Passed |")
    reload=analysis['reload_and_rollback']['reload_intersecting']['image']['comparisons']
    rollback=analysis['reload_and_rollback']['rollback_intersecting']['image']['comparisons']
    review_packet=f'''# Material demonstration review — MAR

Status: **awaiting named human review**. Technical checks have passed for the declared above-water-camera HDR configuration; M4 remains open. This packet does not reuse prior sprint approval.

Please assess whether the paired images provide an acceptable engineering demonstration of the water material and its required medium boundary on the unchanged existing dolphin. All cameras remained above water, including when the animal was submerged. The original animal mesh, scale, material, anatomical pose and orientation were preserved; only inspection Y placement varied between rows.

![Original versus engineering water](figures/material_comparison.png)

The new configuration changes water appearance, transmission/refraction, scattering and reflected/shadowed surface features. It does not improve the animal asset itself. The closed side/bottom boundary is an explicit part of the new water configuration, so the result is not an isolated one-parameter shader experiment. Images use one fixed log HDR mapping, with no per-image normalization.

![Unchanged direct geometric boxes](figures/geometric_annotation_comparison.png)

Yellow boxes are direct projections of the same 3D asset bounds within each pair. Visible/refracted contours and surface reflection/shadow features need not follow those direct boxes; the above-water engineering image has a conspicuous water feature outside the direct animal box. No existing labels were changed, no raster mask was created and no numerical visible-mask accuracy is claimed. Crop colour differences are appearance diagnostics, not mask-error or refraction-displacement measurements.

![Fresh-process persistence](figures/fresh_reload.png)

The fresh-process reload passed full-image MAD {reload['full_rgb']['mean_absolute_difference_8bit']:.4f} and p99 {reload['full_rgb']['p99_absolute_difference_8bit']:.0f}, versus limits 1 and 8 in 8-bit units. Rollback passed the same gate. The earlier in-process stage switch did not complete and remains unqualified. M6 camera far clipping was declared from geometric framing (approximately {preparation['camera_physical_far_m']:.2f} m), rather than silently inheriting the smaller fiducial camera range.

The original inside-camera defect still reproduced on driver 595.99.02 with valid above-water controls. Native LDR PNG clipping, unmeasured hardware sample counts and lack of optical/biological/field validation remain explicit limitations.

Review scope: **engineering acceptance of this demonstration**, not real-seawater or wildlife-survey validation and not closure of M4. Reviewer identifier: **MAR**. The current sprint requires this new named human review; acceptance remains unrecorded until the human responds.

Dolphin asset: DigitalLife3D, Model 61A - Bottlenose Dolphin; original CC-BY-NC-4.0 attribution/licence preserved in the preset package.
'''
    (ROOT/'REVIEW_PACKET.md').write_text(review_packet)
    closeout=f'''# MARLIN ocean material sprint — closeout candidate

Updated **3 November 2026**. Sprint: **MARLIN — Ocean Material and Underwater Appearance**.

**The sprint remains open.** M6's implementation, paired captures, fresh-process persistence, rollback and regressions have passed the declared technical checks. Named human review by **MAR** is pending. M4's inside-water-camera attenuation defect still reproduced on driver 595.99.02; the new driver resolved the NVML mismatch but did not resolve this renderer capability.

## Milestone status

| Work | Current outcome |
| --- | --- |
| M1–M3 | Earlier acceptance evidence remained sealed and unchanged |
| M4 | Above-water integration supported; inside-camera attenuation remained unqualified, including the new-driver retest |
| M5 | Bounded PathTracing HDR/EXR plus fixed-display repeat/reload checks completed; useful native LDR PNG remained unqualified |
| M6 | Versioned preset, animal comparisons, fresh-process reload, rollback and regressions ready; new named human review pending |

## New-driver reproduction

The six initial frozen standalone scenes were repeated with the same private Kit 110.2 build, source scene hashes, product controls and optical analysis. Driver was 595.99.02, kernel 7.0.0-42; the older tests used driver 595.91.07 and an earlier kernel. This is a persistence check on the current host configuration, not an isolated causal claim about one changed component.

The 1 m above-water absorption/clear RGB ratio was **[0.600536, 0.800048, 0.898451]**, consistent with [0.6,0.8,0.9] within the existing 0.03 absolute tolerance. The inside-camera 0.5 m ratio remained **[1,1,1]**, instead of [0.774597,0.894427,0.948683]. Clear, absorbing and engineering inside cases all measured centre RGB [11336,11336,11336]. Above-water positive controls passed; inside checks failed. A local [NVIDIA addendum](diagnostics/m4_driver_5959902/NVIDIA_SUPPORT_ADDENDUM.md) was prepared but not posted.

![Driver retest](diagnostics/m6/figures/driver_retest.png)

The native reproduction retained its original 64-frame/45-second frame wait and first-case/subsequent 240/90-second coroutine bounds. Only its optional direct vendor MDL hash was skipped, to honour repository restrictions on generated caches; rendering was unchanged. The owned informational IOMMU notice was dismissed without changing host settings. Six cases completed; sampled peak GPU use was 2,206 MiB, minimum free 3,592 MiB. Total process wall time 218.04 s included startup and notice acknowledgement.

## Versioned preset and unchanged animal

The package is [presets/engineering_v1](presets/engineering_v1/README.md): byte-identical parameter JSON, exported MDL material layer, closed-medium requirements, effective capture settings, saved selected scene, local dependency hashes, source snapshots and original animal attribution/licence. It uses native `OmniSurface.mdl`; the water material has no texture assets. Native vendor/cache files were not read or copied. The animal's two local texture files, original USD and licence were hashed and preserved.

The asset was the existing **Model 61A - Bottlenose Dolphin** by DigitalLife3D. Its measured render-purpose world bounds were approximately **0.827 × 0.837 × 2.586 m**, an asset measurement rather than a biological-size claim. Root scale remained [100,100,100], rotation [0,0,0] for this existing asset, and mesh/material/anatomical pose were unchanged. Only temporary Y translations changed inspection placement; live standard placement was restored afterward.

Within every old/new pair, animal transforms and identity, camera matrices, effective camera/product/global controls, lights and original top-ocean points matched. Changed scene prims were confined to the water and its engineering material. The new water required the already-tested closed side/bottom boundary: 17,154 vertices / 17,408 quads versus the original 16,641 / 16,384 top grid, a 20 m bottom depth and horizontal derivative bound {selected['horizontal_derivative_bound']:.6f}. Wave equations, shared sampler, coordinate conventions and animal controllers were not rewritten.

The camera remained above water. Geometric framing selected height **{position[1]:.3f} m**, 35 mm focal length, 20.48 × 15.36 mm aperture, 40-degree downward pitch and 512 × 384 square pixels. Near/far were 0.01 / **{preparation['camera_physical_far_m']:.3f} m**, recorded as an M6-specific camera setting. The pinhole builder's theoretical target metadata was not represented as additional physical targets or new raster-calibration evidence.

| Engineering placement | Asset world Y bounds | Fixed-log box-region MAD (8-bit) | Pair invariants |
| --- | --- | ---: | --- |
{chr(10).join(table)}

Those colour differences include changed water/background/lighting interaction; they are neither an animal-quality score nor a refraction/visible-mask error. Direct projected geometric boxes remained identical within pairs. Refracted/distorted appearance and surface reflection/shadow features can differ from those direct boxes. Existing annotation definitions and historical labels were unchanged; no new visible-mask claim was made.

![Material comparison](diagnostics/m6/figures/material_comparison.png)

## Saved-image, reload, rollback and animation evidence

M6 retained native HDR NPZ/EXR and native PNGs through the existing Kit viewport SDK. Primary quantitative images used the unchanged M5 mapping `round(255*clip(HDR/12000,0,1)**(1/2.2))`; review figures additionally used a single fixed log1p mapping. There was no per-image normalization or renderer exposure fitting. PathTracing configured 512 samples/pixel and 1/iteration, but completed hardware sample counts were not measured. Each M6 image waited 64 rendered frames within 30 s, with a 60 s image bound and 768 MiB free preflight. Initial three-frame/90 s readiness was separate.

All six paired captures completed in the first process. It exited while attaching the saved scene for in-process reload; no Python failure record or native exit code was retained, and bounded kernel/application diagnostics did not establish a cause. The sampled peak was 3,040 MiB used with at least 2,758 MiB free, which does not establish memory exhaustion. The failed switch was preserved and was not called a pass.

The milestone-permitted fresh-process alternative loaded the exact saved selected scene as its first marine stage. The animal, all evaluated non-render scene hashes, material binding, camera matrices, global settings and effective RGB/HDR controls matched. The only raw product inventory difference was the process/view `viewPickingId`; both values were retained and this picking identity alone was reported separately. Picking/object-ID or mask equality was not claimed; all other controls used the existing strict comparator. See [comparison scope](diagnostics/m6/qa/CONTROL_COMPARISON_SCOPE.md).

| Check | Full-image MAD | Full p99 | ROI MAD | ROI p99 | Maximum | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Fresh-process reload | {reload['full_rgb']['mean_absolute_difference_8bit']:.5f} | {reload['full_rgb']['p99_absolute_difference_8bit']:.0f} | {reload['fixed_central_roi']['mean_absolute_difference_8bit']:.5f} | {reload['fixed_central_roi']['p99_absolute_difference_8bit']:.0f} | {reload['full_rgb']['maximum_absolute_difference_8bit']:.0f} | Passed |
| Original-material rollback | {rollback['full_rgb']['mean_absolute_difference_8bit']:.5f} | {rollback['full_rgb']['p99_absolute_difference_8bit']:.0f} | {rollback['fixed_central_roi']['mean_absolute_difference_8bit']:.5f} | {rollback['fixed_central_roi']['p99_absolute_difference_8bit']:.0f} | {rollback['full_rgb']['maximum_absolute_difference_8bit']:.0f} | Passed |

Values are 8-bit primary-display units. The unchanged gate was MAD ≤ 1 and p99 ≤ 8 in full RGB and central ROI; maximum was reported rather than gated. PNG/HDR dimensions and all eight EXR headers were checked independently. The fresh process peaked at 2,528 MiB used / 3,270 MiB minimum free. Its saved results survived a graceful SIGTERM after posted quit did not exit promptly; the process returned 0.

The existing runtime regression passed five wave phases and two real controller trajectories, including boundary and dive/surface paths. A further current-driver live capture recorded **10 actual ocean updates**, advancing phase while retaining engineering binding and boundary updates; all cleanup checks passed. That existing M4 diagnostic kept its separate 90-second transaction bound. Seven memory observations around that live capture peaked at 3,073 MiB used / 2,725 MiB minimum free. Final normal 1280 × 720 preview observation was **{final['gpu'].strip()}**; this later single observation lies outside the smaller diagnostic capture windows. Sampled peaks are not exact allocation peaks or permanent memory fixes.

## Regressions, restoration and preservation

Existing offline checks covered camera math/evidence, projection/calibration, HiDef parameters, renderer settings/snapshots, cetacean motion, movement, baked animation, gallery helpers, ocean enclosure, water material, underwater cue and environment. **{count-skipped} tests passed and {skipped} were skipped** because pxr was unavailable in the external interpreter. Actual Kit geometry/controller/capture/reload/rollback tests ran separately. One initial underwater-cue test-discovery import failure was retained, then passed with the canonical module path; production source was not changed to fix the invocation.

MARLIN was reopened from the pre-work checkpoint and its recorded standard ocean/chase controllers reconstructed, with swimming stopped and the original material selected. Final camera, resolution, fill mode, renderer settings and display options matched the pre-work checkpoint. The final checkpoint was **{final['final_checkpoint']['checkpoint_id']}**. Phase and render history were reset across process lifecycles, not preserved. All **113 canonical source files**, the M5 package and the earlier M1–M4 evidence remained unchanged. Live process logs are excluded from immutable hashes; sealed snapshots are retained.

## Reproduction, rollback and review gate

Exact launch commands, output paths, source hashes, failures and native controls are retained under `diagnostics/m4_driver_5959902/` and `diagnostics/m6/qa/`. The [preset README](presets/engineering_v1/README.md) gives existing-service apply/rollback commands, a fresh-process capture command with an unused output identifier and the tested deterministic display converter. The copied material/source snapshots are evidence and recovery inputs, not edits to generated runtime files or an alternative service architecture.

The [review packet](diagnostics/m6/REVIEW_PACKET.md) is ready for **MAR**. The current sprint explicitly requires a named human review of this demonstrated material change; previous sprint approval is not reused. Human acceptance is still pending in `diagnostics/m6/review_state.json`. Technical readiness does not close M4, qualify native LDR output or establish real-seawater, biological or wildlife-survey validity. No dataset or ML training was started. Stop here pending human review and the unresolved NVIDIA capability.

Dolphin attribution: this work uses "Model 61A - Bottlenose Dolphin" by DigitalLife3D, CC-BY-NC-4.0; original licence and source links remain associated with the asset and preset package.
'''
    (BASE/'OCEAN_MATERIAL_SPRINT_CLOSEOUT.md').write_text(closeout)
    print(json.dumps(dict(package=str(PACKAGE),closeout=str(BASE/'OCEAN_MATERIAL_SPRINT_CLOSEOUT.md'),
          technical_checks_passed=True,human_review='pending',m4_complete=False,tests_passed=count-skipped,tests_skipped=skipped),indent=2))


if __name__=='__main__':
    main()
