"""Read-only preservation audit for the bounded M7 engineering test set.

Reuse the earlier milestone's SHA and row-verification helpers. The historical
manifests remain unchanged; the two explicitly declared M7 source deltas are
reported separately and their exact M6 bytes must remain in the pre-refactor
snapshot. This command runs no tests, renders and makes no Kit/HTTP call.
"""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from run_m4_checks import ROOT, QA, BRIDGE, INTENTIONAL_SOURCE_DELTAS
from run_m4_checks import checked_path, sha, verify_rows, FORBIDDEN_COMPONENTS

M7_SOURCE_DELTAS = frozenset((BRIDGE + "extension.py", BRIDGE + "paired_v2.py"))
EXPECTED_PROTECTED_COUNTS = {"pilot_baseline": 914, "baseline_archive": 1,
    "trained_checkpoint_original_and_backup": 2, "milestone_2": 17,
    "milestone_3": 27, "milestone_4": 55, "milestone_5": 175, "milestone_6": 98}


def read(path):
    return json.loads(path.read_text())


def safe_rows(rows):
    for row in rows:
        path = checked_path(row["path"]).resolve()
        if (not path.is_relative_to(ROOT) or FORBIDDEN_COMPONENTS.intersection(path.parts)
                or path.suffix == ".pyc"):
            raise ValueError("Refusing generated or external resolved path: " + row["path"])
    return rows


def verify(rows, allowed=frozenset()):
    return verify_rows(safe_rows(rows), allowed)


def record_manifest(path, expected_hash, expected_bytes=None):
    actual = sha(path)
    result = {"path": str(path.relative_to(ROOT)), "expected_sha256": expected_hash,
              "actual_sha256": actual, "bytes": path.stat().st_size,
              "passed": actual == expected_hash and (expected_bytes is None or path.stat().st_size == expected_bytes)}
    if not result["passed"]:
        raise ValueError("Historical manifest bytes changed: " + result["path"])
    return result


def audit():
    report = {"milestone": 7, "scope": "Read-only protected-output and historical-source preservation; no M8 work",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
        "tests_rerun": False, "live_calls_made": False, "biological_approval": False,
        "checker_sha256": sha(Path(__file__).resolve()), "helper_sha256": sha(QA / "run_m4_checks.py"),
        "preservation": {}, "historical_manifest_checks": [], "historical_m6_source_checks": []}
    try:
        declaration_path = QA.parent / "m7_capture_declaration.json"
        declaration = read(declaration_path)
        report["declaration"] = {"path": str(declaration_path.relative_to(ROOT)), "sha256": sha(declaration_path),
                                 "declared_at_utc": declaration["declared_at_utc"]}
        if sorted(M7_SOURCE_DELTAS) != declaration["m7_intentional_existing_source_deltas"]:
            raise ValueError("M7 source exceptions differ from the prior declaration")
        manifests = {}
        for number in (5, 6):
            path = QA / f"milestone_{number}_manifest.json"
            pin = declaration[f"sealed_m{number}_manifest"]
            if pin["path"] != str(path.relative_to(ROOT)):
                raise ValueError("Declaration points to another historical milestone manifest")
            report["historical_manifest_checks"].append(record_manifest(path, pin["sha256"], pin["bytes"]))
            manifests[number] = read(path)
            allowed = M7_SOURCE_DELTAS if number == 6 else frozenset()
            report["preservation"][f"milestone_{number}"] = verify(manifests[number]["outputs"], allowed)
        # The older hash anchors below are themselves sealed M6 outputs.
        m6_rows = {row["path"]: row for row in manifests[6]["outputs"]}
        anchor_path = QA / "m6_final_preservation.json"
        anchor_row = m6_rows[str(anchor_path.relative_to(ROOT))]
        report["historical_manifest_checks"].append(record_manifest(anchor_path, anchor_row["sha256"], anchor_row["bytes"]))
        anchor = read(anchor_path)
        old_manifest_pins = {row["milestone"]: row for row in anchor["sealed_manifests"]}
        for number in (2, 3, 4):
            path = QA / f"milestone_{number}_manifest.json"
            report["historical_manifest_checks"].append(record_manifest(path, old_manifest_pins[number]["manifest_sha256"]))
            manifests[number] = read(path)
            allowed = frozenset((BRIDGE + "extension.py",)) if number in (2, 4) else frozenset()
            report["preservation"][f"milestone_{number}"] = verify(manifests[number]["outputs"], allowed)
        baseline_path = QA / "preserved_output_manifest.json"
        report["historical_manifest_checks"].append(record_manifest(baseline_path, anchor["preserved_output_manifest_sha256"]))
        baseline = read(baseline_path)
        report["preservation"]["pilot_baseline"] = verify(baseline["files"], INTENTIONAL_SOURCE_DELTAS)
        report["preservation"]["baseline_archive"] = verify([baseline["archive"]])
        checkpoint = baseline["checkpoint"]
        report["preservation"]["trained_checkpoint_original_and_backup"] = verify([
            {"path": checkpoint[key], "bytes": checkpoint["bytes"], "sha256": checkpoint["sha256"]}
            for key in ("original", "backup")])
        for name, expected in EXPECTED_PROTECTED_COUNTS.items():
            if report["preservation"][name]["protected_files_checked"] != expected:
                raise ValueError("Protected inventory count changed: " + name)
        historical_path = QA / "m7_pre_refactor_source/manifest.json"
        historical = read(historical_path)
        report["historical_m6_source_manifest"] = {"path": str(historical_path.relative_to(ROOT)),
                                                  "sha256": sha(historical_path), "git_commit": historical["git_commit"]}
        if (historical.get("passed") is not True or historical["m6_manifest_sha256"] != declaration["sealed_m6_manifest"]["sha256"]
                or {row["canonical_source"] for row in historical["files"]} != M7_SOURCE_DELTAS
                or len(historical["files"]) != 2):
            raise ValueError("Historical M6 source snapshot lacks the exact two declared M7 deltas")
        for row in historical["files"]:
            expected = m6_rows[row["canonical_source"]]
            if row["sha256"] != expected["sha256"] or row["bytes"] != expected["bytes"]:
                raise ValueError("Historical source snapshot differs from the original M6 source pin")
            preserved = verify([{"path": row["retained_source"], "bytes": expected["bytes"], "sha256": expected["sha256"]}])
            report["historical_m6_source_checks"].append({"canonical_source": row["canonical_source"],
                "retained_source": row["retained_source"], "original_m6_sha256": expected["sha256"],
                "passed": preserved["passed"], "protected_changes": preserved["protected_changes"]})
        source_paths = sorted((ROOT / BRIDGE).glob("*.py")) + [ROOT / "tools/capture_gama_dataset_v2.py", Path(__file__).resolve()]
        report["python_syntax_checked"] = []
        for path in source_paths:
            relative = str(path.relative_to(ROOT))
            safe_rows([{"path": relative}])
            ast.parse(path.read_text(), filename=relative)
            report["python_syntax_checked"].append({"path": relative, "sha256": sha(path), "passed": True})
        diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, check=False)
        report["git_diff_check"] = {"command": ["git", "diff", "--check"], "return_code": diff.returncode,
                                     "output": diff.stdout, "passed": diff.returncode == 0}
        report["intentional_source_deltas"] = {"pilot_baseline": sorted(INTENTIONAL_SOURCE_DELTAS),
            "milestone_2": [BRIDGE + "extension.py"], "milestone_4": [BRIDGE + "extension.py"],
            "milestone_6": sorted(M7_SOURCE_DELTAS),
            "basis": "Earlier cumulative bridge deltas retained; only extension.py and paired_v2.py differed from M6 for the declared M7 work"}
        report["passed"] = (all(item["passed"] for item in report["preservation"].values())
            and all(item["passed"] for item in report["historical_manifest_checks"])
            and len(report["historical_m6_source_checks"]) == 2 and all(item["passed"] for item in report["historical_m6_source_checks"])
            and report["git_diff_check"]["passed"])
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(QA) or output.exists() or output.suffix != ".json":
        raise ValueError("Use a new exclusive JSON output inside the sprint QA directory")
    report = audit()
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(output),
        "protected_counts": {name: row["protected_files_checked"] for name, row in report["preservation"].items()},
        "historical_m6_source_checks": len(report["historical_m6_source_checks"]), "error": report.get("error")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
