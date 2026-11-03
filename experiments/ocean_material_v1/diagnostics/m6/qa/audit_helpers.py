"""Reuse sealed M5 pure audit helpers without executing its startup coroutine."""
import ast
import hashlib
import json
from pathlib import Path

M5 = Path(__file__).resolve().parents[2] / 'm5'
REPO = M5.parents[3]
source = M5 / 'qa/audit_in_kit.py'
manifest = json.loads((M5 / 'manifest.json').read_text())
pin = next(item for item in manifest['files'] if item['path'] == str(source.relative_to(REPO)))
assert hashlib.sha256(source.read_bytes()).hexdigest() == pin['sha256']
names = {'plain', 'write', 'sha', 'state_record'}
nodes = [node for node in ast.parse(source.read_text()).body
         if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in nodes} == names
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), globals())
