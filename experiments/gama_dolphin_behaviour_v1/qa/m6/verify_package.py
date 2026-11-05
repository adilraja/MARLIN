"""Read-only M6 technical/preservation verification, with explicit review state."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def load(path):return json.loads(path.read_text())


def check(items):
    for item in items:
        path=Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=(REPO/path).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(path)
    return len(items)


def main(manifest_path=None):
    path=manifest_path or BASE/'m6_manifest.json'
    manifest=load(path)
    counts={name:check(manifest[name]) for name in ['files','source_pins','asset_dependencies',
        'checkpoint_artifacts','prior_package_manifests','media_and_state_references','external_evidence']}
    assert manifest['technical_status']=='passed' and manifest['gate_d_at_seal']=='pending'
    assert not manifest['human_acceptance_received_at_seal']
    assert not manifest['milestone_6_complete_at_seal'] and not manifest['sprint_closed_at_seal']
    assert not manifest['biological_approval'] and not manifest['research_capture_approval']
    regression=load(ROOT/'regression_summary.json')
    assert regression['passed'] and regression['effective_tests_passed']==188 and regression['effective_suites']==26
    assert regression['unresolved_skips']==0 and not regression['failed_commands']
    assert regression['raw_test_executions']==194 and regression['raw_passed_executions']==193 and regression['raw_skipped_executions']==1
    live=load(ROOT/'live_attempt01/results.json')
    assert live['passed'] and len(live['checks'])==54 and all(live['checks'].values())
    native=load(ROOT/'live_attempt01/native_regression_result.json')
    assert native['ok'] and len(native['phase_checks'])==5 and len(native['controller_checks'])==2
    assert all(v['sampler_max_error_units']<=1e-8 for v in native['phase_checks'])
    assert all(v['max_output_error_units']<=1e-8 for v in native['controller_checks'])
    stage=load(ROOT/'baseline_scene_comparison.json')
    assert stage['passed'] and stage['prims_before']==stage['prims_after']==38
    assert not stage['missing'] and not stage['extra'] and not stage['differences']
    final=load(ROOT/'final_restoration.json')
    assert final['passed'] and all(final['checks'].values())
    provenance=load(ROOT/'parameter_and_pose_provenance.json')
    assert all(v['status']=='engineering_test_assumption' for v in provenance['behaviour_parameter_evidence'].values())
    assert not provenance['biology']['expert_biological_acceptance']
    assessments=load(ROOT/'assessments_at_gate_d.json')
    assert assessments['engineering']['status']=='passed'
    assert assessments['visual']['review_status']=='pending_gate_d' and not assessments['visual']['accepted']
    assert not assessments['biological']['approved_for_biological_study'] and not assessments['research_capture']['approved']
    assert load(ROOT/'source_scope.json')['production_source_changed'] is False
    previous=subprocess.run([sys.executable,'-B',str(BASE/'qa/m5/verify_package.py')],cwd=REPO,
        capture_output=True,text=True,check=True)
    assert json.loads(previous.stdout)['passed']
    review=load(BASE/'reviews/gate_d_review.json')
    accepted=review['status']=='accepted'
    if not accepted:
        assert review['status']=='pending' and review['reviewer'] is None and not review['accepted']
    else:
        assert review['reviewer'] and review['accepted'] and review['acceptance_received']
        decision=load(BASE/review['acceptance_record'])
        assert decision['status']=='accepted' and decision['reviewer']==review['reviewer']
        assert decision['technical_manifest_sha256']==hashlib.sha256((BASE/'m6_manifest.json').read_bytes()).hexdigest()
        check(decision['bindings'])
        assert not decision['biological_approval'] and not decision['research_capture_approval']
    return dict(passed=True,verified=counts,engineering_status='passed',
        regression_tests_passed=188,unresolved_skips=0,live_assertions_passed=54,
        native_wave_phases=5,native_controller_cases=2,exact_38_prim_rollback=True,
        earlier_evidence_preserved=True,production_source_changed=False,kit_restarts=0,
        gate_d=review['status'],named_reviewer=review['reviewer'],
        final_visual_acceptance=accepted,milestone_6_complete=accepted,sprint_closed=accepted,
        biological_support='provisional',biological_approval=False,research_capture_approval=False)


if __name__=='__main__':print(json.dumps(main(),indent=2))
