"""Read-only M5 verification; requires the explicitly retained local artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
BASE=ROOT.parents[1]


def load(path):return json.loads(path.read_text())


def records(items):
    for item in items:
        path=Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=(REPO/path).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(path)
    return len(items)


def main():
    manifest=load(BASE/'m5_manifest.json')
    counts={key:records(manifest[key]) for key in ['files','source_pins','artifact_files','asset_dependencies',
        'checkpoint_artifacts','prior_package_manifests','completed_runtime_logs']}
    assert manifest['technical_status']=='passed' and manifest['milestone_5_complete']
    assert not manifest['milestone_6_started'] and manifest['gate_d']=='not_yet_requested'
    assert not manifest['biological_approval'] and not manifest['optical_approval']
    plan=load(ROOT/'locked_plan_v3.json')
    assert len(plan['snapshot_times_s'])==23
    for name in ['reference','m4_manifest','gate_c_acceptance','acceptance']:
        records([plan[name]])
    state=load(ROOT/'state_comparison_final.json')
    assert state['passed'] and state['fresh_process_is_distinct'] and state['fresh_process_comparisons']==6
    assert state['schedule_comparisons']==381 and state['reordered_seek_comparisons']==13
    assert len(state['frozen_snapshots'])==35 and all(s['passed'] and s['environment_reopened_exactly'] for s in state['frozen_snapshots'])
    for run_id in ['primary02','fresh01']:
        run=load(ROOT/run_id/'result.json')
        assert run['status']=='passed' and all(run['checks'].values()) and all(run['restoration'].values())
        assert all(c['passed'] for c in run['comparisons'])
        assert load(ROOT/(run_id+'_media_analysis.json'))['passed']
    media=load(ROOT/'primary02_media_analysis.json')
    assert media['captures']==387 and media['ffprobe']['nb_frames']=='370'
    assert media['ffprobe']['duration']=='74.000000' and media['ffprobe']['avg_frame_rate']=='5/1'
    assert load(ROOT/'fresh01_media_analysis.json')['captures']==6
    assert len(load(ROOT/'rgb_comparison.json')['comparisons'])==12
    assert load(ROOT/'final_restoration.json')['passed']
    assert load(ROOT/'baseline_scene_comparison.json')['passed']
    audit=load(ROOT/'native_frozen_audit.json')
    assert audit['passed'] and len(audit['snapshots'])==35
    # The M4 package and named Gate C record remain exactly as reviewed.
    historical=subprocess.run([sys.executable,'-B',str(BASE/'qa/m4/verify_gate_c_acceptance.py')],
        cwd=REPO,capture_output=True,text=True,check=True)
    assert json.loads(historical.stdout)['passed']
    return dict(passed=True,verified=counts,milestone_5_complete=True,
        full_sequence_s=74,video_frames=370,video_fps=5,frozen_primary_states=23,
        schedule_comparisons=381,reordered_seek_comparisons=13,fresh_process_comparisons=6,
        reopened_skin_snapshots=35,earlier_evidence_preserved=True,original_scene_restored=True,
        rgb_identity_inferred=False,biological_approval=False,optical_approval=False,
        gate_d='not_yet_requested',milestone_6_started=False)


if __name__=='__main__':print(json.dumps(main(),indent=2))
