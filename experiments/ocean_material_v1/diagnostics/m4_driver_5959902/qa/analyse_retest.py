"""Reuse the prior independent optical analysis with output-path serialization only."""
import ast
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'m4_standalone'


def main():
    source=OLD/'analyse_comparison.py'
    text=source.read_text().replace('str(directory.relative_to(ROOT))','str(directory)')
    nodes=[node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef) and node.name in ('analyse','exr_dimensions')]
    namespace=dict(ROOT=OLD,Path=Path,hashlib=hashlib,json=json,struct=struct,np=np,Image=Image)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
    result=namespace['analyse'](ROOT/'run_01')
    result['analysis_provenance']=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        only_change='Serialize output directory as absolute path, enabling analysis outside the historical root; optical math unchanged')
    path=ROOT/'analysis.json'
    if path.exists():
        assert json.loads(path.read_text())==result,'Retained analysis changed'
    else:
        path.write_text(json.dumps(result,indent=2)+'\n')
    assert result['valid_capture_run'] and result['above_water_target_positive_control_passed']
    print(json.dumps(dict(valid_capture_run=True,above_water_control_passed=True,
        inside_optical_checks_passed=result['initial_inside_optical_checks_passed']),indent=2))


if __name__=='__main__':
    main()
