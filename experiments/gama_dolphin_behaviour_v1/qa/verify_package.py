"""Verify the immutable M1 audit; named Gate A acceptance stays separate."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(records):
    for item in records:
        path = Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts) & {'_build', 'extscache', '__pycache__', '.cache'} and path.suffix != '.pyc'
        data = (REPO/path).read_bytes()
        assert len(data) == item['bytes'] and sha(data) == item['sha256'], str(path)
    return len(records)


def main():
    manifest = json.loads((BASE/'baseline_manifest.json').read_text())
    counts = {key: verify(manifest[key]) for key in ('files', 'external_inputs', 'checkpoint_artifacts')}
    # The immutable source baseline is recoverable from its exact Git commit.
    # Later authorised source work must not be misreported as altered M1 evidence.
    data = subprocess.check_output(['git', 'archive', '--format=tar', manifest['source_commit'],
                                    'source', 'tools', 'integrations/gama'], cwd=REPO)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for item in manifest['source_pins']:
            member = archive.extractfile(item['path'])
            assert member is not None and sha(member.read()) == item['sha256'], item['path']
    current_changes = [item['path'] for item in manifest['source_pins']
                       if not (REPO/item['path']).is_file()
                       or sha((REPO/item['path']).read_bytes()) != item['sha256']]
    inventory = json.loads((BASE/'qa/asset_inventory.json').read_text())
    assert all(all(r.values()) for r in inventory['identity_checks'].values())
    assert inventory['baked_clip']['joint_names_match_target']
    assert inventory['records']['live_checkpoint']['animations'] == []
    assert len(inventory['records']['live_checkpoint']['skeletons'][0]['joints']) == 20
    preservation = json.loads((BASE/'qa/final_preservation.json').read_text())
    assert preservation['passed'] and all(preservation['checks'].values())
    disposition = json.loads((BASE/'qa/historical_gama_source_pin_disposition.json').read_text())
    assert disposition['all_mismatches_proven_preexisting'] and disposition['historical_non_source_outputs_verified']
    review = json.loads((BASE/'reviews/gate_a_review.json').read_text())
    assert review['status'] in ('pending', 'accepted', 'changes_requested', 'rejected')
    if review['status'] == 'pending':
        assert review['reviewer'] is None and review['acceptance_received'] is False
    elif review['status'] == 'accepted':
        assert review['reviewer'] and review['acceptance_received'] and review.get('acceptance_record')
        assert (BASE/review['acceptance_record']).is_file()
    assert manifest['new_behaviour_or_animation_implemented'] is False
    assert manifest['gate_a_status_at_seal'] == 'pending'
    print(json.dumps(dict(verified=counts,source_files_verified_at_baseline_commit=len(manifest['source_pins']),
        current_source_changes_since_m1=current_changes,
        technical_audit_ready=True,gate_a=review['status'],
        milestone_1_accepted=review['status']=='accepted',later_milestones_started_by_m1=False,
        historical_m7_literal_source_pin_check='four preexisting version mismatches retained; non-source outputs verified'),indent=2))


if __name__ == '__main__':
    main()
