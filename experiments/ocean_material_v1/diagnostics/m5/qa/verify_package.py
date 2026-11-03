"""Read-only verification of the sealed M5 package and its bounded qualification."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def verify(records):
    for record in records:
        path = REPO / record['path']
        if set(path.parts) & {'_build', 'extscache', '__pycache__', '.cache'} or path.suffix == '.pyc':
            raise ValueError('Generated runtime path in immutable evidence')
        data = path.read_bytes()
        assert len(data) == record['bytes'], str(path)
        assert hashlib.sha256(data).hexdigest() == record['sha256'], str(path)
    return len(records)


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    counts = {key: verify(manifest[key]) for key in ('files', 'source_pins', 'checkpoint_artifacts')}
    previous = subprocess.run(['/usr/bin/python3', '-B', str(ROOT / 'qa/verify_preparation.py')],
                              capture_output=True, text=True, check=True)
    analysis = json.loads((ROOT / 'runs/attempt03/analysis.json').read_text())
    acceptance = json.loads((ROOT / 'acceptance_summary.json').read_text())
    assert analysis['above_water_m5_acceptance_passed'] and analysis['actual_fresh_layer_reloads_verified']
    assert acceptance['independent_m5_capture_checks_complete']
    assert not acceptance['native_ldr_png_qualified'] and not acceptance['m4_complete']
    assert not acceptance['inside_water_camera_qualified'] and not acceptance['full_sprint_complete']
    print(json.dumps(dict(verified=counts,
        historical_preparation=json.loads(previous.stdout)['verified'],
        independent_m5_capture_checks_complete=True,
        native_ldr_png_qualified=False, m4_complete=False, full_sprint_complete=False), indent=2))


if __name__ == '__main__':
    main()
