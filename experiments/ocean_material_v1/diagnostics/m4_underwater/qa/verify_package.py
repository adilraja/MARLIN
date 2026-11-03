"""Verify sealed follow-up files and current source pins without rendering."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for entry in manifest['files'] + manifest['source_pins']:
        path = REPO / entry['path']
        data = path.read_bytes()
        assert len(data) == entry['bytes'], path
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], path
    assert manifest['camera_inside_attenuation_resolved'] is False
    assert manifest['full_milestone_complete'] is False
    print(json.dumps({'sealed_files_verified': len(manifest['files']),
                      'source_files_verified': len(manifest['source_pins']),
                      'status': manifest['status']}, indent=2))


if __name__ == '__main__':
    main()
