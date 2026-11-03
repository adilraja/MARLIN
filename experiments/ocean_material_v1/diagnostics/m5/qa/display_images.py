"""Fixed, predeclared display conversion of retained native M5 float HDR outputs."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/attempt03'


def convert(rgb):
    if rgb.shape != (384, 512, 3) or not np.isfinite(rgb).all():
        raise ValueError('Invalid HDR image dimensions or nonfinite data')
    return np.rint(255 * np.clip(rgb.astype(np.float64) / 12000, 0, 1) ** (1 / 2.2)).astype(np.uint8)


def main():
    records = json.loads((RUN / 'capture_records.json').read_text())
    for record in records:
        directory = RUN / record['label']
        source = directory / 'hdr.npz'
        target = directory / 'hdr_display.png'
        if target.exists():
            raise RuntimeError('Preserve existing derived display images')
        with np.load(source) as data:
            rgb = data['rgba'][..., :3]
        result = convert(rgb)
        Image.fromarray(result).save(target)
        metadata = dict(source='hdr.npz', source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            output=target.name, output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            domain='Derived RGB display of native HdrColor; native HDR and clipped native PNG retained',
            formula='round(255 * clip(rgb/12000,0,1)**(1/2.2)) cast to uint8',
            scale=12000, gamma=2.2, auto_normalization=False,
            nonconstant=bool(np.ptp(result.astype(float), axis=(0, 1)).max() > 5),
            minimum=int(result.min()), maximum=int(result.max()),
            fraction_of_rgb_values_at_255=float(np.mean(result == 255)))
        (directory / 'display_conversion.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print(record['label'], metadata['minimum'], metadata['maximum'], metadata['fraction_of_rgb_values_at_255'])


if __name__ == '__main__':
    main()
