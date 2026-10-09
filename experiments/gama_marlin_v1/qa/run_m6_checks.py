"""Run new paired-capture checks and preserve previous milestone evidence."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from run_m4_checks import ROOT, QA, USD_PYTHON, BRIDGE, INTENTIONAL_SOURCE_DELTAS
from run_m4_checks import checked_path, sha, verify_rows, run_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"m6_[a-z0-9_]+", args.tag):
        raise ValueError("Use a fresh m6_<suffix> tag")
    output = QA / (args.tag + "_offline_results.json")
    if output.exists() or list(QA.glob(args.tag + "_*.log")):
        raise ValueError("Existing QA evidence must be retained")
    jobs = [
        ("paired_state", USD_PYTHON, "tools/test_gama_paired_state.py", 20),
        ("paired_transaction", USD_PYTHON, "tools/test_gama_paired_transaction.py", 8),
        ("actor_v2", USD_PYTHON, "tools/test_gama_actor_v2.py", 24),
        ("legacy_actor", USD_PYTHON, "tools/test_gama_actor.py", 8),
        ("exchange_v2", sys.executable, "tools/test_gama_exchange_v2.py", 23),
        ("stage_and_routes", USD_PYTHON, "tools/test_gama_v2_stage.py", 8),
        ("legacy_exchange", sys.executable, "tools/test_gama_exchange.py", 9),
        ("legacy_live_protocol", sys.executable, "tools/test_gama_live.py", 3),
        ("porpoise_export", sys.executable, "tools/test_gama_porpoise.py", 11),
        ("capture_projection", USD_PYTHON, "tools/test_capture_projection.py", 1),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda item: run_job(item, args.tag), jobs))
    baseline = json.loads((QA / "preserved_output_manifest.json").read_text())
    preservation = {"pilot_baseline": verify_rows(baseline["files"], INTENTIONAL_SOURCE_DELTAS),
        "baseline_archive": verify_rows([baseline["archive"]])}
    checkpoint = baseline["checkpoint"]
    preservation["trained_checkpoint_original_and_backup"] = verify_rows([
        {"path": checkpoint[key], "bytes": checkpoint["bytes"], "sha256": checkpoint["sha256"]}
        for key in ("original", "backup")])
    for number in (2, 3, 4, 5):
        manifest = json.loads((QA / f"milestone_{number}_manifest.json").read_text())
        allowed = frozenset((BRIDGE + "extension.py",)) if number in (2, 4) else frozenset()
        preservation[f"milestone_{number}"] = verify_rows(manifest["outputs"], allowed)
    syntax_paths = [BRIDGE + name for name in ("extension.py", "paired_v2.py", "paired_state_v2.py")]
    syntax_paths += [item[2] for item in jobs[:2]]
    syntax_paths += ["tools/verify_gama_paired_live.py", str(Path(__file__).relative_to(ROOT))]
    syntax = []
    for relative in syntax_paths:
        path = checked_path(relative)
        ast.parse(path.read_text(), filename=relative)
        syntax.append({"path": relative, "sha256": sha(path)})
    report = {"milestone": 6, "scope": "offline tests; no Kit captures in this command",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "results": results,
        "total_tests": sum(row["tests"] or 0 for row in results), "preservation": preservation,
        "python_syntax_checked": syntax,
        "intentional_source_delta": "Only extension.py gained the bounded paired-capture endpoint; prior M4 content records remain sealed",
        "live_capture_verified": False, "biological_approval": False}
    report["passed"] = all(row["passed"] for row in results) and all(row["passed"] for row in preservation.values())
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "tests": report["total_tests"],
        "results": [{"log": row["log"], "passed": row["passed"], "tests": row["tests"]} for row in results]}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
