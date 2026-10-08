"""Capture M2 offline test evidence without rewriting any Pilot output."""
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
USD_PYTHON = "/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(item):
    name, python, script = item
    command = [python, "-B", script, "-v"]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    log = QA / ("m2_" + name + ".log")
    with log.open("x") as out:
        out.write(result.stdout)
    match = re.search(r"Ran (\d+) tests", result.stdout)
    return {"command": command, "return_code": result.returncode,
            "tests": int(match[1]) if match else None,
            "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)}


def main():
    output = QA / "m2_offline_results.json"
    if output.exists() or list(QA.glob("m2_*.log")):
        raise SystemExit("M2 evidence already exists; preserve it rather than overwrite")
    jobs = [("exchange_v2", sys.executable, "tools/test_gama_exchange_v2.py"),
            ("stage_and_routes", USD_PYTHON, "tools/test_gama_v2_stage.py"),
            ("legacy_exchange", sys.executable, "tools/test_gama_exchange.py"),
            ("legacy_live_protocol", sys.executable, "tools/test_gama_live.py"),
            ("legacy_actor", USD_PYTHON, "tools/test_gama_actor.py")]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, jobs))
    source = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
    syntax = []
    for name in ("exchange_v2.py", "stage_coordinates.py", "extension.py"):
        path = source / name
        ast.parse(path.read_text())
        syntax.append(str(path.relative_to(ROOT)))
    baseline = json.loads((QA / "preserved_output_manifest.json").read_text())
    allowed = "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/extension.py"
    protected = [row for row in baseline["files"] if row["path"] != allowed]
    changed = [row["path"] for row in protected if sha(ROOT / row["path"]) != row["sha256"]]
    checkpoint = baseline["checkpoint"]
    checkpoint_valid = all(sha(ROOT / checkpoint[key]) == checkpoint["sha256"] for key in ("original", "backup"))
    passed = (all(row["return_code"] == 0 and row["tests"] for row in results)
              and not changed and checkpoint_valid)
    report = {"passed": passed, "results": results,
              "total_tests": sum(row["tests"] or 0 for row in results),
              "python_syntax_checked": syntax,
              "protected_baseline_files_checked": len(protected),
              "protected_baseline_changes": changed,
              "checkpoint_original_and_backup_hashes_match": checkpoint_valid,
              "live_http_verified": False,
              "biological_approval": False}
    with output.open("x") as out:
        out.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
