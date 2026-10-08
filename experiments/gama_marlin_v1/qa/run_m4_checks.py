"""Retain M4 offline checks and verify prior evidence without overwriting it."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
BRIDGE = "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/"
INTENTIONAL_SOURCE_DELTAS = frozenset((BRIDGE + "actor.py", BRIDGE + "extension.py"))
FORBIDDEN_COMPONENTS = frozenset(("_build", "extscache", "__pycache__", ".cache"))


def checked_path(relative):
    path = Path(relative)
    if (path.is_absolute() or ".." in path.parts or
            FORBIDDEN_COMPONENTS.intersection(path.parts) or path.suffix == ".pyc"):
        raise ValueError(f"Refusing a generated or non-repository path: {relative}")
    return ROOT / path


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_rows(rows, allowed=frozenset()):
    changed = []
    intentional = []
    protected = 0
    for row in rows:
        relative = row["path"]
        path = checked_path(relative)
        current = sha(path) if path.is_file() else None
        matches = (current == row["sha256"] and path.stat().st_size == row["bytes"])
        if relative in allowed:
            intentional.append({"path": relative, "changed": not matches,
                                "previous_sha256": row["sha256"], "current_sha256": current})
        else:
            protected += 1
            if not matches:
                changed.append(relative)
    return {"protected_files_checked": protected, "protected_changes": changed,
            "intentional_source_deltas": intentional, "passed": not changed}


def run_job(item, tag):
    name, python, script, expected = item
    command = [python, "-B", script, "-v"]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    log = QA / f"{tag}_{name}.log"
    with log.open("x") as output:
        output.write(result.stdout)
    match = re.search(r"Ran (\d+) tests", result.stdout)
    count = int(match[1]) if match else None
    metrics = None
    for line in result.stdout.splitlines():
        start = line.find('{"composed_transform_comparisons"')
        if start >= 0:
            metrics = json.loads(line[start:])
    return {"command": command, "return_code": result.returncode, "tests": count,
            "minimum_expected_tests": expected,
            "passed": result.returncode == 0 and count is not None and count >= expected,
            "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
            **({"composed_transform_metrics": metrics} if metrics else {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-tag", default="m4", help="Fresh prefix; existing evidence is never replaced")
    parser.add_argument("--additional-syntax", action="append", default=[], metavar="REPO_PATH")
    args = parser.parse_args()
    tag = args.evidence_tag
    if not re.fullmatch(r"m4(?:_[A-Za-z0-9_]+)?", tag):
        raise SystemExit("Evidence tag must be m4 or m4_<safe_suffix>")
    output = QA / f"{tag}_offline_results.json"
    if output.exists() or list(QA.glob(f"{tag}_*.log")):
        raise SystemExit("Evidence already exists; use a fresh --evidence-tag rather than overwrite it")
    jobs = [
        ("actor_v2", USD_PYTHON, "tools/test_gama_actor_v2.py", 24),
        ("legacy_actor", USD_PYTHON, "tools/test_gama_actor.py", 8),
        ("exchange_v2", sys.executable, "tools/test_gama_exchange_v2.py", 23),
        ("stage_and_routes", USD_PYTHON, "tools/test_gama_v2_stage.py", 8),
        ("legacy_exchange", sys.executable, "tools/test_gama_exchange.py", 9),
        ("legacy_live_protocol", sys.executable, "tools/test_gama_live.py", 3),
        ("porpoise_export", sys.executable, "tools/test_gama_porpoise.py", 11),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda job: run_job(job, tag), jobs))

    syntax_paths = [BRIDGE + name for name in (
        "actor.py", "actor_v2.py", "extension.py", "visual_v2.py", "exchange_v2.py", "stage_coordinates.py")]
    syntax_paths.extend(("tools/test_gama_actor_v2.py", "tools/build_gama_porpoise_demo.py",
                         str(Path(__file__).relative_to(ROOT))))
    live_candidates = ("tools/gama_porpoise_live.py", "tools/verify_gama_porpoise_live.py",
                       "experiments/gama_marlin_v1/qa/verify_m4_live.py")
    syntax_paths.extend(path for path in live_candidates if checked_path(path).is_file())
    syntax_paths.extend(args.additional_syntax)
    syntax = []
    for relative in dict.fromkeys(syntax_paths):
        path = checked_path(relative)
        ast.parse(path.read_text())
        syntax.append({"path": relative, "sha256": sha(path)})

    baseline = json.loads((QA / "preserved_output_manifest.json").read_text())
    protected = verify_rows(baseline["files"], INTENTIONAL_SOURCE_DELTAS)
    checkpoint = baseline["checkpoint"]
    checkpoint_copies = [{"path": checkpoint[key], "bytes": checkpoint["bytes"],
                          "sha256": checkpoint["sha256"]} for key in ("original", "backup")]
    checkpoint_verification = verify_rows(checkpoint_copies)
    archive_verification = verify_rows([baseline["archive"]])
    seals = {}
    for milestone in (2, 3):
        manifest_path = QA / f"milestone_{milestone}_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        allowed = frozenset((BRIDGE + "extension.py",)) if milestone == 2 else frozenset()
        seals[str(milestone)] = {
            "manifest": str(manifest_path.relative_to(ROOT)), "manifest_sha256": sha(manifest_path),
            **verify_rows(manifest["outputs"], allowed),
        }
    m3 = json.loads((QA / "milestone_3_manifest.json").read_text())
    retained_records = [row for row in m3["outputs"]
                        if row["path"].startswith("experiments/gama_marlin_v1/trajectories/")]
    actual_gama_records = verify_rows(retained_records)
    passed = (all(row["passed"] for row in results) and protected["passed"]
              and checkpoint_verification["passed"] and archive_verification["passed"]
              and all(row["passed"] for row in seals.values()) and actual_gama_records["passed"])
    report = {
        "passed": passed, "milestone": 4, "scope": "offline_adapter_and_preservation_checks",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "results": results, "total_tests": sum(row["tests"] or 0 for row in results),
        "python_syntax_checked": syntax, "baseline_verification": protected,
        "checkpoint_original_and_backup": checkpoint_verification,
        "baseline_archive": archive_verification, "prior_milestone_seals": seals,
        "retained_actual_gama_records": actual_gama_records,
        "live_http_verified_by_this_script": False, "biological_approval": False,
    }
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
