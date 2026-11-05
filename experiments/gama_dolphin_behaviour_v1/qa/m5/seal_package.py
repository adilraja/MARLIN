"""Write the evidence-backed M5 report and seal the finite campaign once."""
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def load(path):return json.loads(path.read_text())


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.relative_to(REPO)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def files(root):
    for directory,directories,names in os.walk(root):
        directories[:]=sorted(d for d in directories if d not in {'_build','extscache','__pycache__','.cache'})
        for name in sorted(names):
            path=Path(directory)/name
            if path.suffix!='.pyc':yield path


def main():
    assert not (BASE/'m5_manifest.json').exists()
    plan=load(ROOT/'locked_plan_v3.json')
    state=load(ROOT/'state_comparison_final.json')
    primary=load(ROOT/'primary02/result.json')
    fresh=load(ROOT/'fresh01/result.json')
    audit=load(ROOT/'native_frozen_audit.json')
    final=load(ROOT/'final_restoration.json')
    baseline=load(ROOT/'baseline_scene_comparison.json')
    media=load(ROOT/'primary02_media_analysis.json')
    assert state['passed'] and audit['passed'] and final['passed'] and baseline['passed']
    assert primary['status']==fresh['status']=='passed'
    assert media['passed'] and load(ROOT/'fresh01_media_analysis.json')['passed']
    historical=subprocess.run([sys.executable,'-B',str(BASE/'qa/m4/verify_gate_c_acceptance.py')],
        cwd=REPO,text=True,capture_output=True,check=True)
    write(ROOT/'earlier_evidence_verification.json',json.loads(historical.stdout))
    syntax=[]
    for path in files(ROOT):
        if path.suffix=='.py':
            ast.parse(path.read_text(),filename=str(path));syntax.append(str(path.relative_to(REPO)))
    write(ROOT/'syntax_verification.json',dict(passed=True,files=syntax))
    index=[]
    for capture in primary['captures']:
        if not capture['snapshot'] or capture['label'].startswith('reorder_'):continue
        folder=Path(primary['media_directory'])/capture['label']
        record=load(folder/'state.json')
        index.append(dict(simulation_time_s=record['simulation_time_s'],state=record['frame']['agent']['behavioural_state'],
            directory=str(folder.relative_to(REPO)),state_file=pin(folder/'state.json'),scene_file=pin(folder/'scene.usdc'),
            evaluated_skin_file=pin(folder/'skin.npz'),source_prefix_last_index=record['source_prefix_last_index'],
            phase=record['pose_controls']['phase'],weight=record['pose_controls']['weight']))
    assert len(index)==23
    write(ROOT/'frozen_state_index.json',dict(schema_version=1,snapshots=index,
        controller_contract=dict(owner='Explicit-time animated v3 actor',autonomous_subscriptions=0,
            capture_owner_paused=False,capture_gate_paused=True,timeline_playing=False,
            replay='Recreate owner on baseline and deterministically deliver the retained GAMA prefix, then evaluate within the two-state bracket. Frozen USD alone is a static pose, not a serialized Python controller.',
            retained='Resolved root and joints, phase/weight, complete actual two-state buffer and accepted-prefix index, source sequence, camera/product/global controls, full frozen ocean geometry, lighting values and native schema/build provenance.')))
    gpu=[g for run in [primary,fresh] for g in run['gpu']]
    free=min(g['free_mib'] for g in gpu)
    resources=dict(resolution=[512,384],primary_wall_s=primary['wall_s'],fresh_wall_s=fresh['wall_s'],
        sampled_minimum_free_gpu_mib=free,memory_guard_mib=768,observations=len(gpu),
        driver=primary['gpu'][0]['driver'],kit_build=primary['runtime']['build'],
        checkpointed_kit_launches=6,system_reboots=0,installed_dependencies_changed=False,
        image_settle='64 completed rendered frames for snapshots; 3 for ordinary video frames; configured 512 spp, actual accumulated sample count unmeasured',
        limits='Sampled free memory is not an exact peak-allocation measurement; 512x384 and 5 fps were declared before acceptance capture, not survey-resolution qualification.')
    write(ROOT/'resource_summary.json',resources)

    text=f'''# M5 — Integrated demonstration and reproducible frozen snapshots

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Milestone: **Demonstrate the full sequence and reproducible frozen snapshots**.
Prepared 5 November 2026. **M5 technical acceptance passed. M6 and Gate D have not started.**

## Outcome and review material

The complete 74-second accepted reference sequence was replayed from actual M3
GAMA output through the unchanged, MAR-accepted M4 animation map:
steady swim → gradual turn → descent → submerged swim → ascent → steady swim.
One private experimental dolphin used the preserved Model 61A asset, rig, bake,
material and fixed calibration, with the unchanged `engineering_v1` water preset.
No production source, behaviour model, asset, accepted preset or historical seal
was changed. This was a new bounded verification campaign, not a new dataset.

- [Full 74-second video](../../artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4): 370 frames at 5 fps, normal simulation speed, no edited time windows.
- [23-state contact sheet](qa/m5/figures/frozen_state_contact_sheet.png).
- [Motion and phase plots](qa/m5/figures/motion_and_phase.png).
- [Traceable frozen-state index](qa/m5/frozen_state_index.json).
- [Numerical comparison](qa/m5/state_comparison_final.json), [native frozen-scene audit](qa/m5/native_frozen_audit.json) and [resource summary](qa/m5/resource_summary.json).

The original 297 GAMA states were retained, including seed/run/step provenance;
5 fps presentation did not create independent behavioural samples. The 23 snapshot
times were declared before acceptance capture, including states on both sides of
the 10, 22, 38, 48 and 64 second boundaries. The terminal 74-second stopped state
was separately preserved. Exact times are in `qa/m5/locked_plan.json` and its
retained, justified protocol amendments.

## Timing, seeking and frozen state

Schedule A captured the monotonic union of video and snapshot times. Schedule B
queried the same **381 timestamps** with extra 0/1/5 Kit update waits. Thirteen
additional reordered seeks passed. Seeking explicitly reset and replayed the
actual contiguous GAMA prefix through ceil(t/0.25), then evaluated within the
retained two-step bracket. This is deterministic reconstruction, not stateless
random access or resumed hidden controller history.

The primary process PID was {primary['pid']}; a fresh Kit process, PID
{fresh['pid']}, recreated six representative states in reverse order. All six
fresh-process comparisons passed. Their times were 6, 16, 30, 42, 56 and 70 s.

Every capture held resolved root, all 20 composed joint poses, phase, weight,
two-state buffer, accepted-prefix index, authored capture-camera/frustum, ocean
geometry and lighting while the renderer settled and copied HDR. Full snapshot
USD, native HDR/EXR, evaluated 21,504-vertex skin arrays and complete JSON state
were retained at the declared times. The source trajectory and prefix rule
provide the controller reconstruction path; a frozen USD is not a serialized
Python subscription or transport token.

Across the independent replay, schedule and frozen-scene checks, maximum measured
root-matrix, root-position, joint-matrix, phase and repeated/reopened skin errors
were **zero**. Criteria remained the original M4 values: root matrix 1e-8,
root position 1e-5 m, joint matrix 2e-6, phase 1e-9 cycles and skin 2e-6 m.
All **35** full frozen files (23 primary, six reordered and six fresh) reopened
and matched evaluated skin. They also matched complete ocean/lighting state in
the native Kit runtime. Pause, resume without a jump, missing-update freeze,
rejected missing-step delivery, reset hold and owned-actor removal passed in
both the primary and fresh processes.

## Capture domain and limitations

All 393 primary/reordered/fresh captures used the existing native `HdrColor`
float-buffer and EXR path. The original fixed scale-12000 gamma display and fixed
log1p display were retained. Ordinary marine HDR was much lower than the bright
emitter fixture's scale, so a separately declared, fixed Reinhard review display
was added before the successful full run:
`round(255 * (max(rgb,0)/(1+max(rgb,0)))**(1/2.2))`.
It was identical for every frame; there was no per-image normalization, light,
material or camera-exposure fitting. The video/contact sheet are derived HDR
displays, not newly qualified native LDR or radiometrically calibrated imagery.

The ocean used deterministic frozen phase zero for this campaign, matching the
accepted M4 diagnostic policy. Dynamic wave/animal coupling during full-sequence
playback was not demonstrated. Cameras remained above the wave-height bounds.
The accepted turn/descent/ascent limits remained: the existing local cycle ran
with trajectory root attitude, without bespoke bank, steering, dive-body or
breathing poses. Biological/optical/survey approval was not granted; the separate
ocean-material inside-camera attenuation case remained open.

Twelve matched HDR comparisons retained actual RGB differences separately;
state equality did not establish pixel identity. Configured 512 spp and frame
settling did not establish actual accumulated sample count. Final named visual
and biological assessments remain for M6/Gate D.

## Retained failures and audit amendments

`smoke01`, `smoke02` and partial `primary01` were preserved. Their overly broad
freeze assertions included the asynchronously updated UI viewport view matrix.
Retained operand comparisons isolated the change to that UI cache; commanded
root/joints/phase and authored capture-camera/frustum remained exact. Protocol v3
consistently distinguished these presentation fields and retained both raw UI
metadata and comparison results. No numeric tolerance or original scene data
was changed. The successful campaign used new output `primary02`.

An external generic-USD audit could not resolve four unauthored NVIDIA dome-light
schema fallbacks. Its source and diagnosis were retained. All 35 frozen files
were then reopened inside native Kit and matched the complete recorded lighting
state exactly, including those defaults. The external skin audit accepted those
specific missing schema values only with the corresponding successful native
file-hash-bound proof. This remains an explicit SDK dependency, not a claim of
identical lighting under a generic USD installation.

## Resources, restoration and next boundary

Primary wall time was {primary['wall_s']:.2f} s; fresh-process capture/check time
was {fresh['wall_s']:.2f} s, excluding launches and later offline packaging.
Minimum sampled free GPU memory was **{free} MiB**, above the unchanged 768 MiB
guard. The bounded image workload was 512×384 with 5 fps video. Six checkpointed
Kit launches covered retained smoke/capture fixes, fresh replay and the native
schema audit. No system reboot or driver/SDK installation change occurred.

The original live scene was restored exactly: **38 prims, zero missing/extra prims
and zero composed attribute/relationship differences**, without exceptions.
Camera, resolution, renderer/display settings, original water and controller
states matched pre-work. Ocean/chase/swimmer/gallery had already been stopped
and were restored stopped. The final normal-window checkpoint was
`{final['final_checkpoint']}`. No experimental actor or QA poller remained.

The M4 technical seal, MAR's Gate C decision and historical M1–M3/water M5–M6
evidence verified unchanged. Their dated pre-M5 statuses were not rewritten.
See [reproduction and rollback](M5_REPRODUCTION_AND_ROLLBACK.md) and
`m5_manifest.json`. M5 is complete for this engineering scope. The next milestone
is M6 closeout/regressions and named Gate D review; no Gate D acceptance, Git
commit, dataset generation or additional species work was performed here.
'''
    with (BASE/'M5_INTEGRATED_DEMONSTRATION.md').open('x') as stream:stream.write(text)
    reproduction=f'''# M5 reproduction and rollback

## Verify the preserved campaign

From `/home/madil/kit-app-template`:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m5/verify_package.py
```

This is read-only. It requires the retained local artifact/checkpoint store,
source assets/licences and the prior sealed sprint evidence. The native Kit,
Blender/USD and GAMA runtimes and vendor libraries were not redistributed or
claimed to be entirely byte-pinned. Actual M3 GAMA output, current source pins,
native build/driver/settings and dependency manifests provide the recorded
provenance. No newly generated GAMA trajectory was substituted.

## Media and snapshots

Full normal-speed movie:
`/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4`.

The movie contains all 370 0.2-second presentation frames from t=0 through 73.8,
played at 5 fps for 74 seconds. Terminal t=74 is preserved as a frozen snapshot.
`qa/m5/frozen_state_index.json` locates all 23 primary frozen states and binds
their scene, evaluated skin and sidecar bytes. Each capture retains native
`hdr.npz`, `hdr.exr`, effective camera/product settings, actual root/joint state
and fixed derived displays. No native PNG qualification was inferred.

The static USD includes resolved pose and scene geometry. To resume/seek the
experimental actor, restore the preserved baseline, acquire one animated v3
owner, reset its buffer and deliver the retained contiguous M3 prefix up to the
selected bracket before evaluating the desired time. Retain source sequence,
buffer samples, phase/weight and camera/ocean/lighting controls. Do not import an
old ownership token or call this stateless reconstruction. The native frozen
audit verifies the four SDK-provided lighting defaults that generic USD cannot
expand; their effective values remain in each sidecar.

## Re-execution rules

Completed output directories and immutable records deliberately refuse overwrite.
For another campaign, create a versioned protocol and new allowlisted run IDs,
save the current scene first, and retain failures and amendments. Reuse
`native_m5.py` with the accepted actor and `capture_hdr`; never run completed
`host_launch.py` identities in place or overwrite current review media.

The final finite entry point was `qa/m5/entry_audit.py`; it ended after checking
the saved files. No general HTTP code executor, external web framework, global
timeline animation controller or permanent QA poller was introduced. Canonical
runtime source was unchanged. Known Kit launcher execution was the only use of
the generated build; no generated runtime/cache files were inspected or edited.

## Rollback

The pre-work baseline was `{load(ROOT/'live_before/checkpoint.json')['checkpoint_id']}`.
Its copied USD and metadata are under `qa/m5/live_before`. Final restored state
was `{final['final_checkpoint']}`, copied under `qa/m5/live_final`. The final
normal MARLIN GUI on port 8011 retained the same stopped ocean/chase/swimmer/
gallery controllers and original water selection. The complete 38-prim scene and
settings matched exactly, so no further rollback is required.

For a later operation, checkpoint any newer user work before restoring a recorded
checkpoint through `/debug/scene/checkpoint/<id>/restore`. A frozen checkpoint
does not restore arbitrary Python controller histories. Do not start controllers
that were stopped in the pre-work record. M6 and Gate D remain separate work.
'''
    with (BASE/'M5_REPRODUCTION_AND_ROLLBACK.md').open('x') as stream:stream.write(reproduction)

    previous=load(BASE/'m4_manifest.json')
    for item in previous['source_pins']:
        assert pin(REPO/item['path'])==item
    package_files=[BASE/'M5_INTEGRATED_DEMONSTRATION.md',BASE/'M5_REPRODUCTION_AND_ROLLBACK.md']
    package_files += [p for p in files(ROOT) if p.suffix!='.log' and p.name not in {'final_verification.json','manifest_draft.json'}]
    logs=[p for p in files(ROOT) if p.suffix=='.log' and 'launch_audit' not in p.parts]
    checkpoints={load(ROOT/'live_before/checkpoint.json')['directory'],load(ROOT/'live_final/checkpoint.json')['directory']}
    for name in ['smoke03','primary02','fresh01']:
        checkpoints.add(load(ROOT/name/'result.json')['final_checkpoint']['directory'])
    checkpoints.add(audit['final_checkpoint']['directory'])
    prior=[BASE/n for n in ['baseline_manifest.json','m2_manifest.json','m3_manifest.json','m4_manifest.json',
        'reviews/MAR_GATE_A_2026_11_05_acceptance_manifest.json','reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json',
        'reviews/MAR_GATE_C_2026_11_05_acceptance_manifest.json']]
    manifest=dict(schema_version=1,sprint='MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation',
        milestone='M5 — Demonstrate the full sequence and reproducible frozen snapshots',
        sealed_utc=datetime.now(timezone.utc).isoformat(),base_commit=plan['source_commit'],technical_status='passed',
        milestone_5_complete=True,milestone_6_started=False,gate_c='accepted_by_MAR',gate_d='not_yet_requested',
        biological_approval=False,optical_approval=False,rgb_identity_inferred=False,
        production_source_changed=False,local_artifacts_required=True,runtime_redistributed=False,
        files=[pin(p) for p in sorted(set(package_files))],source_pins=previous['source_pins'],
        asset_dependencies=previous['asset_dependencies'],
        artifact_files=[pin(p) for p in files(REPO/'artifacts/gama_dolphin_behaviour_v1/m5')],
        checkpoint_artifacts=[pin(Path(d)/n) for d in sorted(checkpoints) for n in ['scene.usdc','metadata.json']],
        prior_package_manifests=[pin(p) for p in prior],completed_runtime_logs=[pin(p) for p in logs],
        mutable_excluded=['qa/m5/final_verification.json','qa/m5/manifest_draft.json','qa/m5/launch_audit/*.log'],
        limitations=['Frozen ocean phase zero; no full-sequence dynamic wave coupling demonstration.',
            'Existing-cycle manoeuvre limits retained; no biological, optical or survey approval.',
            'Fixed derived HDR displays; no native LDR or pixel-identity qualification.',
            'Four NVIDIA dome-light fallbacks require the recorded native SDK; generic USD alone cannot expand them.',
            '381 timestamps and 5 fps are bounded engineering coverage, not a survey workload.'])
    write(BASE/'m5_manifest.json',manifest)
    from verify_package import main as verify
    result=verify()
    write(ROOT/'final_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
