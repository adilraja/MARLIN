"""Seal the reviewed technical scope once; never overwrite existing seals."""
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

from verify_package import main as verify

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'
QA = BASE / 'qa/m4'
FORBIDDEN = {'_build', 'extscache', '__pycache__', '.cache'}


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def record(path):
    relative = path.relative_to(REPO)
    assert not FORBIDDEN.intersection(relative.parts) and path.suffix != '.pyc'
    data = path.read_bytes()
    return dict(path=str(relative), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def files_under(root):
    for directory, directories, names in os.walk(root):
        directories[:] = sorted(n for n in directories if n not in FORBIDDEN)
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix != '.pyc':
                yield path


def main():
    final = BASE / 'm4_manifest.json'
    assert not final.exists(), 'Candidate already sealed; create a versioned amendment instead'
    previous = json.loads((BASE / 'm3_manifest.json').read_text())
    scope = json.loads((QA / 'source_scope.json').read_text())
    implementation = scope['modified_existing_source'] + scope['new_runtime_source'] + ['tools/test_gama_animated_v3.py']
    snapshots = {}
    for name in implementation:
        snapshot = QA / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open('xb') as stream:
            stream.write((REPO / name).read_bytes())
        snapshots[name] = str(snapshot.relative_to(REPO))

    syntax_files = sorted(set([p for p in files_under(QA) if p.suffix == '.py'] +
                              [REPO / p for p in implementation if p.endswith('.py')]))
    for path in syntax_files:
        ast.parse(path.read_text(), filename=str(path))
    write_new(QA / 'final_syntax_verification.json', dict(passed=True, files=[str(p.relative_to(REPO)) for p in syntax_files]))

    mutable = {'final_verification.json', 'candidate_draft_manifest.json'}
    files = [BASE / 'M4_STATE_TO_ANIMATION_MAP.md', BASE / 'M4_REPRODUCTION_AND_ROLLBACK.md',
             BASE / 'reviews/GATE_C_REVIEW.md']
    files += list(files_under(BASE / 'animation'))
    files += [p for p in files_under(QA) if p.suffix != '.log' and p.name not in mutable]
    source_paths = {item['path'] for item in previous['source_pins']} | set(implementation)
    assets = [REPO / item['path'] for item in json.loads((BASE / 'm2_manifest.json').read_text())['asset_dependencies']]
    assets += [REPO / 'assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json']
    checkpoints = []
    for identity in ['checkpoint_4fde7e3u', 'checkpoint_cgp8owp0', 'checkpoint_crnswl_g']:
        for name in ['scene.usdc', 'metadata.json']:
            checkpoints.append(REPO / 'artifacts/scene_checkpoints' / identity / name)
    logs = [p for p in files_under(QA) if p.suffix == '.log' and 'live_restore_gui_final' not in p.parts]
    prior = [BASE / name for name in ['baseline_manifest.json', 'm2_manifest.json', 'm3_manifest.json',
        'reviews/MAR_GATE_A_2026_11_05_acceptance_manifest.json',
        'reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json']]
    manifest = dict(schema_version=1,
        sprint='MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation',
        milestone='M4 — Map behaviour and movement to visible body animation',
        sealed_utc=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git', 'rev-parse', '4af84ab'], cwd=REPO, text=True).strip(),
        technical_status='passed_with_explicit_manoeuvre_limits', gate_b='accepted_by_MAR',
        gate_c_at_seal='pending', human_acceptance_received_at_seal=False,
        milestone_4_accepted_at_seal=False, body_animation_implemented=True,
        milestone_5_started=False, biological_approval=False, optical_approval=False,
        files=[record(p) for p in sorted(set(files))],
        source_pins=[record(REPO / p) for p in sorted(source_paths)],
        artifact_files=[record(p) for p in files_under(REPO / 'artifacts/gama_dolphin_behaviour_v1/m4')],
        asset_dependencies=[record(p) for p in assets],
        checkpoint_artifacts=[record(p) for p in checkpoints],
        prior_package_manifests=[record(p) for p in prior],
        completed_runtime_logs=[record(p) for p in logs],
        implementation_snapshots=snapshots,
        mutable_excluded=['reviews/gate_c_review.json', 'qa/m4/final_verification.json',
                          'qa/m4/candidate_draft_manifest.json', 'qa/m4/live_restore_gui_final/*.log'],
        local_artifacts_required=True, runtime_redistributed=False,
        runtime_provenance='Recorded Kit process, GPU/driver, settings and launch records; '
                           'not a bytewise identity claim for every installed SDK library.',
        limitations=['Same existing cycle for all five state labels; no bespoke steering, bank or dive pose.',
                     'Two edited 30 s review sequences at 10 fps; not the full continuous M5 sequence.',
                     'Sampled geometric guards and inspection do not certify exhaustive absence of intersections.',
                     'Underwater-camera material issue remains open in the separate ocean-material sprint.',
                     'Historical sidecars retain the pre-correction descriptive mapping label; numeric poses match final source.'])
    draft = QA / 'candidate_draft_manifest.json'
    write_new(draft, manifest)
    verify(draft)
    with final.open('xb') as stream:
        stream.write(draft.read_bytes())
    result = verify(final)
    write_new(QA / 'final_verification.json', result)
    write_new(BASE / 'reviews/gate_c_review.json', dict(status='pending', proposed_reviewer='MAR',
        reviewer=None, accepted=False, technical_status=manifest['technical_status'],
        manifest=record(final), packet=record(BASE / 'reviews/GATE_C_REVIEW.md'),
        acceptance_scope='Existing-cycle body animation with explicit limited manoeuvre-specific poses; '
                         'bounded input to M5, no biological or optical acceptance.',
        recorded_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
