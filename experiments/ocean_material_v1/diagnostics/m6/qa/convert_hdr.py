"""Convert one retained native HDR array with the predeclared M5 display map."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

M5=Path(__file__).resolve().parents[2]/'m5'
sys.path.insert(0,str(M5/'qa'))
from display_images import convert


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.conversion.json').exists():
        raise RuntimeError('Choose a new output; existing results are preserved')
    with np.load(args.input,allow_pickle=False) as archive:
        rgb=archive['rgba'][...,:3]
    result=convert(rgb)
    with args.output.open('xb') as stream:
        Image.fromarray(result).save(stream,format='PNG')
    args.output.with_suffix('.conversion.json').write_text(json.dumps(dict(
        source=str(args.input.resolve()),source_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
        formula='round(255*clip(rgb/12000,0,1)**(1/2.2)) cast to uint8',
        per_image_normalization=False,scientific_radiometry_validated=False),indent=2)+'\n')
    print(args.output)


if __name__=='__main__':
    main()
