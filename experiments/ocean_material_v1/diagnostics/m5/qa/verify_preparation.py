"""Verify the saved preparation without reading generated runtime directories."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def main():
    counts = {}
    for name in ('historical_pins', 'source_before'):
        records = json.loads((ROOT / 'qa' / (name + '.json')).read_text())
        for record in records:
            path = REPO / record['path']
            if set(path.parts) & {'_build', 'extscache', '.cache', '__pycache__'} or path.suffix == '.pyc':
                raise ValueError('Forbidden runtime path in pin list')
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], str(path)
        counts[name] = len(records)
    checkpoint = json.loads((ROOT / 'qa/pre_checkpoint.json').read_text())
    assert hashlib.sha256((Path(checkpoint['directory']) / 'scene.usdc').read_bytes()).hexdigest() == checkpoint['scene_sha256']
    attempt = json.loads((ROOT / 'qa/guarded_capture_attempt01.json').read_text())
    assert attempt['response']['ok'] is False
    assert attempt['response']['render_attempted'] is False
    reference = json.loads((ROOT / 'prior_capture_settings.json').read_text())
    assert reference['status'] == 'historical_M4_reference_only_not_a_new_M5_validation'
    source = REPO / reference['source_directory'] / 'scene.usdc'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == reference['source_scene_sha256']
    result = dict(verified=counts, checkpoint_hash_verified=True, guard_refused_render=True,
                  historical_settings_source_verified=True, full_milestone_complete=False)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
