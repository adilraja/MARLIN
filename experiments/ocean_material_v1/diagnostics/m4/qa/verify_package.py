"""Read-only verification of M4 evidence, final source pins and prior milestones."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def verify(records, base):
    for record in records:
        path = base / record['path']
        data = path.read_bytes()
        assert len(data) == record['bytes'], f'Length changed: {path}'
        assert hashlib.sha256(data).hexdigest() == record['sha256'], f'Hash changed: {path}'
    return len(records)


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    evidence = verify(manifest['files'], REPO)
    sources = verify(manifest['source_pins'], REPO)
    base = REPO / 'experiments/ocean_material_v1'
    historical = {}
    for name, path, prefix in (
        ('m1', base / 'manifest.json', base),
        ('m2', base / 'diagnostics/m2/manifest.json', REPO),
        ('m3', base / 'diagnostics/m3/manifest.json', REPO),
    ):
        records = json.loads(path.read_text())['files']
        historical[name] = verify(records, prefix)
    assert manifest['full_milestone_complete'] is False
    assert manifest['camera_inside_qualified'] is False
    print(json.dumps({'evidence_files_verified': evidence,
                      'final_source_files_verified': sources,
                      'historical_files_verified': historical,
                      'status': manifest['status']}, indent=2))


if __name__ == '__main__':
    main()
