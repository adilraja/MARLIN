"""Seal the technically verified, still-pending Gate D candidate once."""
from datetime import datetime,timezone
import ast
import hashlib
import json
import os
from pathlib import Path

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
    final=BASE/'m6_manifest.json'
    assert not final.exists()
    syntax=[]
    for path in files(ROOT):
        if path.suffix=='.py':ast.parse(path.read_text(),filename=str(path));syntax.append(str(path.relative_to(REPO)))
    write(ROOT/'syntax_verification.json',dict(passed=True,files=syntax))
    previous=load(BASE/'m5_manifest.json')
    for record in previous['source_pins']:assert pin(REPO/record['path'])==record
    source_pins=previous['source_pins']
    docs=[BASE/'M6_SPRINT_CLOSEOUT.md',BASE/'REPRODUCTION_AND_ROLLBACK.md',BASE/'reviews/GATE_D_REVIEW.md']
    package_files=docs+[p for p in files(ROOT) if p.suffix!='.log' and p.name not in ['final_verification.json','manifest_draft.json']]
    prior=[BASE/n for n in ['baseline_manifest.json','m2_manifest.json','m3_manifest.json','m4_manifest.json','m5_manifest.json',
        'reviews/MAR_GATE_A_2026_11_05_acceptance_manifest.json','reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json',
        'reviews/MAR_GATE_C_2026_11_05_acceptance_manifest.json']]
    media=[REPO/'artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4',
        REPO/'artifacts/gama_dolphin_behaviour_v1/m4/dry02/review_30s.mp4',
        BASE/'qa/m5/figures/frozen_state_contact_sheet.png',BASE/'qa/m5/figures/motion_and_phase.png',
        BASE/'qa/m5/frozen_state_index.json',BASE/'qa/m5/state_comparison_final.json',
        BASE/'qa/m5/native_frozen_audit.json',BASE/'qa/m5/rgb_comparison.json',
        BASE/'trajectories/m3_ref_a01/trajectory.json',BASE/'qa/m3/campaign_analysis.json']
    assets=[REPO/record['path'] for record in load(BASE/'qa/asset_provenance.json')['files']]
    checkpoints=[]
    for folder in ['live_before','live_final']:
        cp=load(ROOT/folder/'checkpoint.json')
        checkpoints += [Path(cp['directory'])/name for name in ['scene.usdc','metadata.json']]
    regression=load(ROOT/'live_attempt01/native_regression_call.json')
    manifest=dict(schema_version=1,sprint='MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation',
        milestone='M6 — Review, preserve and close out',evidence_version='bottlenose_engineering_demo_v1',
        sealed_utc=datetime.now(timezone.utc).isoformat(),base_commit='3c6e2630ea3cc091b2de9604c5a6c9972bc14232',
        technical_status='passed',gate_d_at_seal='pending',human_acceptance_received_at_seal=False,
        milestone_6_complete_at_seal=False,sprint_closed_at_seal=False,
        biological_support='provisional',biological_approval=False,research_capture_approval=False,
        production_source_changed=False,kit_restarts=0,local_artifacts_required=True,runtime_redistributed=False,
        files=[pin(p) for p in sorted(set(package_files))],source_pins=source_pins,
        asset_dependencies=[pin(p) for p in sorted(set(assets))],
        checkpoint_artifacts=[pin(p) for p in checkpoints],prior_package_manifests=[pin(p) for p in prior],
        media_and_state_references=[pin(p) for p in media],
        external_evidence=[pin(Path(regression['directory'])/'result.json')],
        mutable_excluded=['reviews/gate_d_review.json','qa/m6/final_verification.json','qa/m6/manifest_draft.json',
            'qa/m5/launch_audit/*.log'],
        limitations=['Named final visual review pending; Codex supplied no human or biological acceptance.',
            'Existing-cycle manoeuvre limits, frozen-ocean 5 fps/512x384 video and separate optics limitations retained.',
            'Model/controller assumptions are not empirical biological validation.',
            'Later dataset/ML/species/research use requires a separate explicit decision.'])
    write(ROOT/'manifest_draft.json',manifest)
    review=dict(gate='D',evidence_version=manifest['evidence_version'],status='pending',
        proposed_reviewer='MAR',reviewer=None,accepted=False,acceptance_received=False,
        technical_status='passed',technical_manifest='m6_manifest.json',packet='reviews/GATE_D_REVIEW.md',
        biological_approval=False,research_capture_approval=False,milestone_6_complete=False,sprint_closed=False,
        requested_scope='Exact bounded engineering/visual demonstration; biological support remains provisional and research capture unapproved',
        recorded_utc=datetime.now(timezone.utc).isoformat())
    write(BASE/'reviews/gate_d_review.json',review)
    from verify_package import main as verify
    verify(ROOT/'manifest_draft.json')
    with final.open('xb') as stream:stream.write((ROOT/'manifest_draft.json').read_bytes())
    result=verify()
    write(ROOT/'final_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
