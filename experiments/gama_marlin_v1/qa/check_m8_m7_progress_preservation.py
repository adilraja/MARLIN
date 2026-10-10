"""Read-only verification of the preserved, incomplete M7 progress inventory.

This verifies existing output bytes, not M7 acceptance. It makes no live call,
capture, model execution or detector training request and leaves seals intact.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import capture_gama_dataset_v2 as capture

QA = Path(__file__).resolve().parent
MANIFEST = QA / "m7_progress_manifest.json"
EXPECTED_SHA256 = "a480bd2ac0624ab6cc8ff2d6873bb68c355f6a73f9adcb3ad66ec53e242635d9"
EXPECTED_OUTPUTS = 1355
PINNED_SOURCES = (Path(__file__).resolve(), QA / "run_m8_preservation.py", QA / "check_m7_preservation.py",
                  QA / "run_m4_checks.py", ROOT / "tools/capture_gama_dataset_v2.py",
                  ROOT / "tools/capture_gama_dataset_pending_v2.py", ROOT / "tools/aggregate_gama_dataset_v2.py",
                  ROOT / "tools/test_gama_dataset_pending.py", ROOT / "tools/verify_gama_paired_live.py")


def audit():
    before_sources = [capture.pin(path) for path in PINNED_SOURCES]
    report = {"kind": "m8_partial_m7_output_preservation", "milestone": 8,
              "scope": "All output bytes in the pinned incomplete M7 progress inventory, with pending helpers",
              "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
              "milestone_7_acceptance_claimed": False, "whole_sprint_completion_claimed": False,
              "live_calls_made": False, "tests_rerun": False, "biological_approval": False,
              "source_pins_before": before_sources, "outputs_checked": 0, "changes": []}
    try:
        manifest_before = capture.pin(MANIFEST)
        report["manifest_before"] = manifest_before
        if manifest_before["sha256"] != EXPECTED_SHA256:
            raise ValueError("M7 progress manifest differs from its exact requested historical anchor")
        document = json.loads(MANIFEST.read_text())
        rows = document["outputs"]
        if len(rows) != EXPECTED_OUTPUTS or len({row["path"] for row in rows}) != EXPECTED_OUTPUTS:
            raise ValueError("M7 progress protected inventory count or uniqueness changed")
        fields = ("status", "passed", "milestone_complete", "resource_blocked", "validated_images",
                  "expected_images", "remaining_images", "source_campaign_passed", "final_dataset_exported",
                  "biological_approval", "last_retained_free_gpu_mib", "resource_observation_utc")
        report["retained_m7_status"] = {name: document.get(name) for name in fields}
        expected_status = {"status": "incomplete", "passed": False, "milestone_complete": False,
                           "resource_blocked": True, "validated_images": 120, "expected_images": 150,
                           "remaining_images": 30, "source_campaign_passed": False,
                           "final_dataset_exported": False, "biological_approval": False}
        if any(document.get(key) != value for key, value in expected_status.items()):
            raise ValueError("Progress inventory no longer describes the declared incomplete M7 evidence")
        for row in rows:
            path = capture.live.safe_path(ROOT / row["path"])
            if not path.is_relative_to(ROOT):
                raise ValueError("Protected output resolves outside the repository")
            current = capture.pin(path) if path.is_file() else None
            report["outputs_checked"] += 1
            if current != row:
                report["changes"].append({"expected": row, "current": current})
        report["manifest_after"] = capture.pin(MANIFEST)
        report["source_pins_after"] = [capture.pin(path) for path in PINNED_SOURCES]
        report["manifest_unchanged"] = report["manifest_after"] == manifest_before
        report["sources_unchanged"] = report["source_pins_after"] == before_sources
        report["passed"] = (report["outputs_checked"] == EXPECTED_OUTPUTS and not report["changes"]
                            and report["manifest_unchanged"] and report["sources_unchanged"])
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = capture.live.safe_path(args.output)
    if not output.is_relative_to(QA) or output.exists() or output.suffix != ".json":
        raise ValueError("Use a new exclusive JSON output inside sprint QA")
    result = audit()
    capture.live.write_json(output, result)
    print(json.dumps({"passed": result["passed"], "outputs_checked": result["outputs_checked"],
                      "changes": len(result["changes"]), "output": str(output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
