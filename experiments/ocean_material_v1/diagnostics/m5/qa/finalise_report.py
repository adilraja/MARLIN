"""Package the observed M5 results without rewriting historical failure evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
RUN = ROOT / 'runs/attempt03'
RECOVERY = ROOT / 'qa/driver_recovery_2026_11_03'
REPORT = REPO / 'experiments/ocean_material_v1/reports/M5_CAPTURE_AND_RESOURCES.md'


def load(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    analysis = load(RUN / 'analysis.json')
    assert analysis['above_water_m5_acceptance_passed']
    baseline = load(RUN / 'baseline/metadata.json')
    controls = baseline['effective_controls']
    runtime = load(RUN / 'runtime.json')
    recovery = load(RECOVERY / 'post_reboot_retry03/verification.json')
    final = load(ROOT / 'qa/final_live_verification.json')
    assert all(final['checks_against_pre_reboot_checkpoint'].values())
    pins = load(RECOVERY / 'post_reboot_retry03/processing_source_pins.json')
    for name, expected in pins.items():
        assert hashlib.sha256((ROOT / 'qa' / name).read_bytes()).hexdigest() == expected, name
    exr = {}
    for row in load(RUN / 'capture_records.json'):
        name = row['label']
        result = subprocess.check_output(['file', str(RUN / name / 'hdr.exr')], text=True)
        assert 'OpenEXR image data' in result and 'dataWindow: (0 0)-(511 383)' in result
        exr[name] = result.strip()
    write(ROOT / 'qa/exr_format_validation.json', exr)
    tests = []
    for command in (
        ['/usr/bin/python3', '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'qa'), '-p', 'test_*.py', '-v'],
        ['/usr/bin/python3', '-B', '-m', 'unittest', 'discover', '-s', str(REPO / 'source/extensions/cris.madil.render_service/cris/madil/render_service/tests'), '-p', 'test_renderer_snapshot.py', '-v'],
        ['/usr/bin/python3', '-B', str(ROOT / 'qa/verify_preparation.py')],
    ):
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        tests.append(dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
    write(ROOT / 'qa/final_checks.json', tests)
    sealed = ROOT / 'qa/sealed_live_logs'
    sealed.mkdir(exist_ok=False)
    for name in ('kit_process.log', 'launch_stdout.log'):
        shutil.copyfile(RECOVERY / 'post_reboot_retry03' / name, sealed / name)

    selected_keys = [key for key in controls['render_product'] if any(
        token in key for token in ('rendermode', ':pt:', ':rtpt:', ':post:aa:', ':post:dlss:', ':post:tonemap:', ':fog:'))]
    settings = dict(schema_version=1, status='validated_bounded_above_water_HDR_configuration',
        scope='engineering_v1, frozen phase-0 oblique fixture; camera starts above water',
        source_scene_sha256=load(RUN / 'snapshot.json')['source_scene_sha256'],
        saved_scene_sha256=analysis['saved_scene_sha256'], kit_build=runtime['kit_build'],
        driver=recovery['gpu_before']['driver'], gpu=recovery['gpu_before']['name'],
        renderer='PathTracing', image_width_px=512, image_height_px=384,
        camera_path=baseline['projection']['render_product']['camera'],
        camera=controls['camera'], product_controls={key: controls['render_product'][key] for key in selected_keys},
        global_settings=baseline['renderer_globals'], projection=baseline['projection'],
        capture_route='Existing omni.kit.viewport.utility native capture_viewport_to_file/buffer SDK, one MARLIN context/viewport',
        output='Native HdrColor float NPZ and EXR; fixed derived HDR display PNG',
        native_ldr_png_qualified=False,
        native_ldr_limitation='All pixels clipped white under the recorded exposure; retained as a failed useful-RGB route',
        display_conversion=load(RUN / 'baseline/display_conversion.json'),
        completed_rendered_frame_wait=64, rendered_frame_wait_timeout_seconds=30,
        per_capture_timeout_seconds=60, suite_timeout_seconds=300, pre_capture_free_mib=768,
        actual_gpu_sample_count_measured=False, camera_inside_water_qualified=False,
        comparative_mode='Real-Time Path-Tracing', comparative_mode_equivalent_to_production=False)
    write(ROOT / 'validated_capture_settings.json', settings)
    attempts = []
    for name, directory in (('01', 'post_reboot'), ('02', 'post_reboot_retry02'), ('03', 'post_reboot_retry03')):
        monitor = load(RECOVERY / directory / 'monitor_result.json')
        attempts.append(dict(attempt=name, **{k: v for k, v in monitor.items() if k != 'audit_result'},
                             result='startup_frame_timeout' if name == '01' else 'completed',
                             qualification='Native PNG clipped; mode token lookup corrected later' if name == '02' else
                                           'Qualified HDR plus fixed visible display' if name == '03' else 'No accepted capture'))
    write(ROOT / 'qa/resource_and_failure_log_final.json', dict(
        previous_failure_log='qa/resource_and_failure_log.json', driver_mismatch_resolved=True,
        host_reboot_performed_by='user', checkpointed_kit_restarts=2, attempts=attempts,
        final_gpu=final['current_gpu'], scientific_water_calibrated=False,
        permanent_memory_fix_claimed=False, native_ldr_png_qualified=False))

    comparisons = analysis['same_mode_comparisons']
    table = []
    for name, case in comparisons.items():
        frame = case['fixed_hdr_display']['comparisons']['full_rgb']
        roi = case['fixed_hdr_display']['comparisons']['fixed_central_roi']
        relative = case['native_hdr']['results']['full_rgb']['mean_absolute_difference_divided_by_reference_mean_abs'] * 100
        table.append(f"| {name} | {frame['mean_absolute_difference_8bit']:.5f} | {roi['mean_absolute_difference_8bit']:.5f} | {frame['p99_absolute_difference_8bit']:.0f} | {frame['maximum_absolute_difference_8bit']:.0f} | {relative:.3f}% | Passed |")
    timing = analysis['capture_times_seconds']
    resource = analysis['resources']
    mode = analysis['mode_comparison']
    mode_relative = mode['native_hdr']['results']['full_rgb']['mean_absolute_difference_divided_by_reference_mean_abs'] * 100
    report = f'''# M5 — Verify saved-image rendering and resource requirements

Sprint: **MARLIN — Ocean Material and Underwater Appearance**. Updated **3 November 2026**.

**The bounded above-water capture, repeatability, fresh-stage reload and resource checks passed for native HDR/EXR with a deterministic display conversion in PathTracing.** The default native LDR PNG remained fully clipped under the recorded exposure and is not qualified as useful RGB output. This supported configuration and limitation are explicit; the default PNG route was not silently certified. M4's camera-inside-water attenuation defect remains open with NVIDIA, and the sprint is not complete.

## Driver recovery and restored application

The user rebooted the computer. The running kernel changed from 7.0.0-38-generic to **7.0.0-42-generic**; the loaded NVIDIA module, installed module and `nvidia-smi` now agree on **595.99.02**. The old mismatch between loaded 595.91.07 and NVML 595.99 was resolved without replacing, purging or downgrading packages. Initial free memory before launching MARLIN was approximately 5 GiB; this is an observation, not a permanent memory fix.

MARLIN was restored from hash-verified checkpoint **checkpoint_6x3ggjpt**. The saved camera, resolution, fill mode and renderer settings matched. Two subsequent graceful, checkpointed Kit restarts loaded local audit corrections; no further host reboot occurred. After every attempt, the retained live stage and settings were restored. The recorded standard ocean/chase controllers were reconstructed with swimming stopped. Procedural phase and GPU history were reset rather than preserved.

Final live API checks confirmed the ocean and chase camera running, swimming stopped, original material selected, and camera/resolution/fill/renderer/display settings matching the pre-reboot checkpoint. The final recovery checkpoint is **{final['final_checkpoint']['checkpoint_id']}**. All **113 canonical source files** and **2,342 historical evidence entries** remained unchanged. M5 added diagnostic scripts and evidence, with no application-source edits.

## Tested configuration and actual capture route

| Item | Recorded configuration |
| --- | --- |
| Host / GPU | madil-CRIS-UL / NVIDIA RTX A2000, 6,138 MiB total |
| Kit / driver | {runtime['kit_build']} / 595.99.02 |
| Production capture mode | Exact installed token `PathTracing` |
| Fixture | Sealed M4 engineering_v1 ocean, frozen phase 0, above-water oblique camera |
| Route | Existing `omni.kit.viewport.utility` file/buffer capture SDK used by MARLIN experiments; one live context and viewport |
| Saved output | 512 × 384 square pixels; native HdrColor NPZ + EXR, native PNG retained, derived display PNG |
| Camera | `/World/MarlinOceanIntegrationDiagnostic/Camera`; 35 mm focal length; 20.48 × 15.36 mm aperture |
| Projection | Authored camera frustum and actual render product validated independently of the UI window; matching full-image aspect |
| PT budgets | Configured 512 samples/pixel, 1/iteration; total/glossy bounce limits 16/16; `pt:limits:maxVolumeBounces=2`, separate `pt:maxVolumeBounces=15` recorded |
| Denoising / temporal | PT denoising enabled; OptiX temporal mode, PT temporal accumulation and PT adaptive sampling disabled |
| Reconstruction settings | PT DLSS disabled; separate post-AA token `dlss` and post-DLSS `auto` recorded, without assuming those settings imply active reconstruction in PT |
| Exposure / colour | Camera auto-exposure disabled; exposure 0, ISO 100, time/f-stop/responsivity 1; `acesApproximation`, `sRGBLinear`, sRGB-to-gamma enabled, dithering 0 |
| Other controls | Product fog disabled; PT and RTPT firefly filters disabled; engineering medium retained |

The complete effective camera/product inventory, global settings and matrices are retained per capture. `../diagnostics/m5/validated_capture_settings.json` packages the supported configuration. Unresolved precedence between similarly named product settings is not represented as measured ray telemetry.

Each capture waited for **64 completed rendered frames**, then discarded a warmup PNG before saving. The 30-second frame wait, 60-second image coroutine, 300-second suite and 768 MiB pre-capture memory guard were retained. **Configured 512 samples/pixel is not a measured completed GPU sample count.** No hardware sample-count or absolute radiometric-calibration claim is made. Native HDR buffer and EXR were separate SDK captures of the same frozen state, rather than asserted identical stochastic samples.

## Visible output and prospective protocol amendments

`PLAN.md` preserved the M1 full-frame and fixed central ROI tolerances: MAD ≤ **1/255**, p99 ≤ **8/255**, maximum difference reported, and camera matrices within **1e-6**. ROI bounds were x=[128,384), y=[96,288). Scene/settings equality was checked separately using the existing canonical `same_settings` comparator.

The post-reboot attempt01 timed out before the first RTX-ready frame, with no image accepted. All six restoration checks passed. A recorded readiness amendment added a separate initial three-rendered-frame readiness check, bounded at 90 seconds, while leaving the actual capture limits unchanged. Attempt02 then completed five native capture/reload cases, but its native PNGs were all white. Zero differences in those clipped PNGs were explicitly treated as uninformative. Its missing mode comparison was a harness token-lookup error, not evidence that the mode was unavailable.

Before collecting **new attempt03 images**, `ATTEMPT03_DISPLAY_PROTOCOL.md` declared the additional supported display output:

```text
round(255 * clip(native_HDR_RGB / 12000, 0, 1) ** (1/2.2)), cast to uint8
```

Scale 12000 and gamma 2.2 reused the earlier M3 display convention. This conversion used no per-frame normalization, fitted scale or automatic exposure. Its processor source was pinned before the new captures. The new visible images had values 11–234 in the five PT cases, with no values clipped at 255, and passed the unchanged full-frame and ROI tolerances. Native PNGs, native HDR and failed attempts were all retained. The output pipeline changed explicitly; the clipped native PNG route was not relabelled as working.

## Repeat and actual save/reload results

Attempt03 captured a new baseline, two repeats on the same frozen stage, and two independent fresh anonymous-layer reads from the new M5 saved scene. The saved file was not replaced by a fixture rebuild. Three distinct layer identifiers, unchanged input file hash, all 46 evaluated non-render scene-prim hashes, camera matrices, effective camera/product controls and global settings verified the reloads. The maximum observed camera matrix difference was **0**.

Saved scene SHA-256: `{analysis['saved_scene_sha256']}`.

Values below are 8-bit display units, except the final HDR percentage. p99 is the full-frame value; ROI p99 was also 1 in every comparison. Maximum difference was reported, not gated; the declared 8-unit limit applies to p99.

| Comparison | Full RGB MAD | ROI MAD | p99 | Maximum | Native HDR relative MAD | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(table)}

HDR relative MAD is mean absolute native HDR difference divided by mean absolute baseline signal. It is additional diagnostic evidence, not a retrospective HDR pass threshold or per-pixel relative error. PNG equality was not substituted for the visible display measurements.

![Baseline, fresh reload and display difference](../diagnostics/m5/figures/repeat_reload.png)

## Installed renderer comparison

The registered allowed tokens were `RaytracedLighting`, `PathTracing`, **`Real-Time Path-Tracing`** and `Minimal`. The last is not a production water mode. The comparison used the exact registered real-time token; it was not renamed to Real-Time 2.0. Both saved outputs retained the same scene, matrices, exposure and global settings; the only recorded effective camera/product control change was `omni:rtx:rendermode`.

The comparison completed in **{timing['mode_comparison']:.2f} seconds**. Its native HDR relative MAD versus PT was **{mode_relative:.2f}%**. No identical-pixel gate applied across modes, and that difference does not isolate any individual lighting/volume/denoising mechanism. **PathTracing remains the qualified mode**; cross-mode equivalence and camera-inside attenuation are not claimed.

![Registered renderer comparison](../diagnostics/m5/figures/mode_comparison.png)

## Resource and failure observations

The successful attempt03 recorded **{resource['sample_count']} GPU observations** at approximately one-second intervals, spanning startup through audit completion. Peak-observed usage was **{resource['sampled_peak_used_mib']} MiB** and minimum observed free memory **{resource['sampled_minimum_free_mib']} MiB**. This is a sampled peak over that interval, not an exact allocation peak or a guarantee for other scenes. The five PT image coroutines took **{min(timing[name] for name in ('baseline','repeat_a','repeat_b','reload_a','reload_b')):.2f}–{max(timing[name] for name in ('baseline','repeat_a','repeat_b','reload_a','reload_b')):.2f} seconds** each. These timings include frame settling, capture and state recording, and exclude initial startup, stage attachment and initial renderer readiness.

| Attempt | Outcome | Peak observed used / minimum free |
| --- | --- | --- |
| Pre-reboot | NVML exit 18; existing guard refused rendering | Unavailable, not zero |
| 01 | 30.03 s initial 64-frame timeout before first RTX-ready frame; restored cleanly | 2,290 / 3,508 MiB |
| 02 | Five captures/reloads completed; native PNG clipped; comparison token lookup corrected later | 2,952 / 2,846 MiB |
| 03 | Five qualified PT captures plus one registered-mode comparison; all restoration checks passed | 3,025 / 2,774 MiB |

No capture size, camera sampling, medium or required effect was silently reduced. A 512 × 384 explicit product was used throughout. No second renderer/context was allocated, and no memory guard was bypassed. The native-LDR failure was addressed with a separately declared and tested HDR display pipeline, while preserving the original output. Existing asset-converter/libxml2 startup errors remained unrelated; asset conversion was not used.

![Sampled GPU memory](../diagnostics/m5/figures/gpu_observations.png)

## Evidence, checks and scope

- `../diagnostics/m5/runs/attempt03/analysis.json`: actual image/state comparisons, reload verification and resource summary.
- `../diagnostics/m5/runs/attempt03/`: PNG, NPZ, EXR, derived display images, effective controls, saved scene, runtime versions and restoration checks.
- `../diagnostics/m5/qa/resource_and_failure_log_final.json`: links to preserved failures, every attempt and restart accounting.
- `../diagnostics/m5/qa/final_live_verification.json`: restored live ocean/chase/material/settings and final checkpoint.
- Ten comparison/display-tool tests and five existing renderer-snapshot tests passed. Actual GPU capture/reload/restoration checks passed separately. PNG and NPZ dimensions were decoded independently; `file` independently identified all six EXRs as 512 × 384 OpenEXR outputs.
- Protected evidence/source hashes and pre-capture processor pins were verified. Sealed copies of the still-running Kit logs were retained; live log originals are excluded from immutable hashes.

**Supported:** this bounded, above-water engineering_v1 fixture in PathTracing, native HDR/EXR plus the declared fixed display conversion, within the observed host/configuration limits. **Unsupported or unqualified:** useful native LDR PNG under this exposure, camera-inside-water attenuation, general cross-mode equivalence, absolute radiometric or biological calibration, full native HiDef/Sony output and a new fresh-process reproducibility claim. M4 remains open and the overall sprint remains incomplete. The new-driver run does not retroactively requalify earlier evidence on the old driver.
'''
    REPORT.write_text(report)
    write(ROOT / 'acceptance_summary.json', dict(
        updated_utc=datetime.now(timezone.utc).isoformat(), driver_mismatch_resolved=True,
        marlin_restored=True, independent_m5_capture_checks_complete=True,
        supported_capture_configuration='PathTracing, above-water frozen engineering_v1, 512x384 native HDR/EXR plus fixed display conversion',
        native_ldr_png_qualified=False, inside_water_camera_qualified=False,
        full_sprint_complete=False, m4_complete=False, protected_source_files_unchanged=113,
        historical_evidence_entries_verified=2342, accepted_same_mode_captures=5,
        registered_mode_comparison_captures=1, measured_hardware_sample_counts=False))
    print(json.dumps(dict(report=str(REPORT), supported_configuration=settings['status'],
                         repeat_reload_checks_passed=True, native_ldr_png_qualified=False), indent=2))


if __name__ == '__main__':
    main()
