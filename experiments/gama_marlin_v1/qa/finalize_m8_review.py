"""Verify and seal the M8 review decision, keeping blocked M7 explicitly incomplete."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/gama_marlin_v1"
QA = BASE / "qa"
FORBIDDEN = {"_build", "extscache", "__pycache__", ".cache"}


def safe(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated/cache bytes are outside M8 review scope")
    resolved = path.resolve()
    if FORBIDDEN.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Resolved path enters generated/cache content")
    return path


def sha(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def pin(path):
    path = safe(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def read(path):
    return json.loads(safe(path).read_text())


def write(path, value):
    with safe(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    started = datetime.now(timezone.utc).isoformat()
    target = QA / "milestone_8_manifest.json"
    require(not target.exists(), "Existing M8 review seal cannot be overwritten")
    before = {}

    def checked(item):
        current = pin(item["path"])
        require(current["sha256"] == item["sha256"], "Evidence changed: " + current["path"])
        if "bytes" in item:
            require(current["bytes"] == item["bytes"], "Evidence size changed")
        before[current["path"]] = current
        return current

    def data(path):
        current = pin(path)
        before[current["path"]] = current
        return read(path)

    offline = data(QA / "m8_offline_01/results.json")
    cases = [row for row in offline["results"] if row["tests"] is not None]
    require(sum(row["tests"] for row in cases) == 360
            and all(row["passed"] and row["return_code"] == 0 and row["skipped"] == 0 for row in cases),
            "Current regression cases did not pass")
    failures = [row for row in offline["results"] if not row["passed"]]
    require(len(failures) == 1 and failures[0]["name"] == "pilot_sealed_package"
            and failures[0]["return_code"] == 1 and offline["passed"] is False,
            "Original historical command failure was changed")
    require(offline["additional_passed_contract_checks"] == 1 and offline["source_pins_unchanged"]
            and offline["git_diff_check"]["return_code"] == 0, "Regression metadata differs")
    categories = Counter()
    for row in cases:
        categories[row["category"]] += row["tests"]
    for row in offline["results"]:
        checked(row["stdout"])
        checked(row["stderr"])
    source_pins = data(QA / "m8_offline_01/source_pins_before.json")
    require(source_pins == data(QA / "m8_offline_01/source_pins_after.json") and len(source_pins) == 283,
            "Regression pin inventory changed")
    for item in source_pins:
        checked(item)
    disposition = data(QA / "m8_offline_01/historical_package_disposition.json")
    require(disposition["original_run_passed"] is False and disposition["no_package_outputs_written"]
            and disposition["original_evidence_preserved"] and disposition["expected_schema"] == "1.6.0"
            and disposition["actual_preserved_final_schema"] == "1.7.0", "Historical failure disposition differs")
    checked(disposition["original_run_record"])
    recipe_source = disposition["disposition_recipe_pin"]
    checked(recipe_source)
    recipe_copy = QA / "m8_historical_package_disposition_recipe.py"
    require(not recipe_copy.exists(), "Disposition recipe copy already exists")
    shutil.copyfile(safe(recipe_source["path"]), recipe_copy)
    checked({"path": str(recipe_copy), "sha256": recipe_source["sha256"]})

    audit = data(QA / "m8_pilot_audit_02.json")
    execution = data(QA / "m8_pilot_audit_02_execution.json")
    require(audit["passed"] and audit["source_and_images_unchanged_after"]
            and audit["input_images_decoded_hashed_and_pixel_padding_checked"] == 300
            and audit["retained_test_metric_summaries_exact"] == 18
            and audit["annotation_boxes_linked_geometry_coco_assignment"] == 250
            and audit["training_or_inference_performed"] is False
            and execution["passed"] and execution["return_code"] == 0
            and execution["old_outputs_written"] is False, "Read-only audit did not pass")
    checked(execution["result"])
    checked(execution["actual_combined_stdout_stderr"])
    for item in audit["source_pins"] + audit["image_pins"]:
        checked(item)
    require(len(audit["cpu_transform_checks"]) == 12, "CPU transform observation count differs")

    live = data(QA / "m8_live_demo_01/results.json")
    live_execution = data(QA / "m8_live_demo_01/command_execution.json")
    require(live["passed"] and len(live["checks"]) == 14 and all(live["checks"].values())
            and all(live["route_presence_checks"].values()) and len(live["http_requests"]) == 5
            and all(row["method"] == "GET" and row["http_status_code"] == 200 for row in live["http_requests"])
            and live["scene_mutation_attempted"] is False and live["captures_requested"] == 0
            and live_execution["return_code"] == 0, "Read-only live demonstration failed")
    for item in live["source_pins_after"]:
        checked(item)
    require(live["source_pins_before"] == live["source_pins_after"], "Live check source changed")

    historical = data(QA / "m8_preservation_final_01.json")
    historical_execution = data(QA / "m8_preservation_final_01_execution.json")
    progress = data(QA / "m8_m7_progress_preservation.json")
    require(historical["passed"] and historical_execution["passed"] and progress["passed"]
            and progress["outputs_checked"] == 1355 and progress["manifest_unchanged"]
            and progress["milestone_7_acceptance_claimed"] is False, "Preservation failed")
    checked(historical_execution["result"])
    checked(historical_execution["actual_stdout_stderr"])
    m7 = data(QA / "m7_progress_manifest.json")
    require(sha(QA / "m7_progress_manifest.json") == "a480bd2ac0624ab6cc8ff2d6873bb68c355f6a73f9adcb3ad66ec53e242635d9"
            and m7["passed"] is False and m7["status"] == "incomplete" and m7["validated_images"] == 120,
            "M7 incompleteness evidence changed")
    for item in m7["outputs"]:
        checked(item)
    require(not (QA / "milestone_7_manifest.json").exists()
            and not (QA / "m7_capture_set").exists()
            and not (BASE / "datasets/m7_engineering_v1").exists(), "Unexpected M7 completion artifact")
    human = data(QA / "m5_human_review.json")
    require(human["biological_approval"] is False
            and human["human_decision"] == "provisional; engineering use only", "Human scope changed")

    documents = [BASE / name for name in ("GAMA_MARLIN_SPRINT_REPORT.md", "M8_REPRODUCTION.md",
                                          "M8_READ_ONLY_PILOT_AUDIT.md")]
    planned = {QA / "m8_final_review_validation.json", target}
    link_count = 0
    for document in documents:
        before[str(document)] = pin(document)
        for value in re.findall(r"\]\((/[^)]+)\)", document.read_text()):
            filename = re.sub(r":\d+$", "", value)
            path = safe(filename)
            require(path.exists() or path in planned, "Document link missing: " + value)
            link_count += 1

    # Only new M8 artifacts are sealed here; M7 remains protected by its own progress inventory.
    paths = set(documents) | {Path(__file__), ROOT / "tools/verify_gama_m8_demo.py"}
    for entry in QA.iterdir():
        if not (entry.name.startswith("m8_") or entry.name in {"run_m8_offline_checks.py", "run_m8_preservation.py",
                                                                 "check_m8_m7_progress_preservation.py"}):
            continue
        if entry.is_file():
            paths.add(entry)
        elif entry.is_dir():
            for directory, names, filenames in os.walk(entry, followlinks=False):
                names[:] = [name for name in names if name not in FORBIDDEN]
                paths.update(Path(directory) / name for name in filenames if not name.endswith(".pyc"))
    syntax = []
    for path in sorted(paths):
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
            syntax.append(str(path.relative_to(ROOT)))
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, text=True, capture_output=True)
    require(diff.returncode == 0, "git diff --check failed")
    require(all(pin(item["path"]) == item for item in before.values()), "Input changed during final review")
    decision = {"milestone": 8, "review_completed": True, "sprint_acceptance_complete": False,
        "ready_for_further_bounded_engineering_tests": True,
        "ready_for_limited_behaviour_conditioned_study": False, "ready_for_larger_biological_expansion": False,
        "accepted_scope": human["accepted_use"], "biological_approval": False,
        "blocked_milestone": 7, "missing_images": 30, "missing_snapshot_groups": 3,
        "last_capture_headroom_observation": live["gpu_observation"],
        "remaining_limits": ["Static upright pose and engineering behavioral assumptions",
            "Uncalibrated refraction and wave/anatomical clearance", "Direct amodal labels and unknown rendered visibility",
            "Unlabelled background wildlife", "Paired-background shading differences of unestablished cause"],
        "report": pin(documents[0]), "human_review_source": pin(QA / "m5_human_review.json")}
    write(QA / "m8_expansion_decision.json", decision)
    validation = {"kind": "m8_final_review_validation", "milestone": 8, "passed": True,
        "acceptance_scope": "Completed regression review, read-only pilot audit, reproduction and expansion decision",
        "sprint_acceptance_complete": False, "milestone_7_complete": False, "biological_approval": False,
        "regression_unittest_cases_passed": 360, "regression_categories": dict(categories),
        "all_executed_commands_passed": False, "historical_packaging_command_failed": True,
        "retained_offline_batch_passed": False, "historical_failure_disposition": pin(QA / "m8_offline_01/historical_package_disposition.json"),
        "disposition_recipe_copy_provenance": {"original": recipe_source, "retained_copy": pin(recipe_copy)},
        "pilot_audit_passed": True, "live_demo_passed": True, "live_checks": live["checks"],
        "historical_preservation_passed": True, "m7_progress_pins_checked": 1355,
        "input_pins_before": list(before.values()), "input_pins_unchanged": True,
        "document_links_checked": link_count, "python_syntax_checked": syntax,
        "git_diff_check": {"return_code": diff.returncode, "stdout": diff.stdout, "stderr": diff.stderr},
        "finalizer_live_calls_made": False, "new_images_rendered": 0, "new_ml_training": False,
        "command": [sys.executable, *sys.argv], "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    write(QA / "m8_final_review_validation.json", validation)
    paths.update({QA / "m8_final_review_validation.json", QA / "m8_expansion_decision.json"})
    outputs = [{**pin(path), "path": str(path.relative_to(ROOT))} for path in sorted(paths)]
    write(target, {"milestone": 8, "status": "complete_review_with_blocked_milestone_7", "passed": True,
        "acceptance_scope": validation["acceptance_scope"], "sprint_acceptance_complete": False,
        "milestone_7_complete": False, "all_executed_commands_passed": False,
        "biological_approval": False, "expansion_decision": decision,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "outputs": outputs})
    print(json.dumps({"milestone_8_review_passed": True, "regression_tests": 360,
        "sprint_acceptance_complete": False, "milestone_7_complete": False,
        "outputs": len(outputs), "manifest": str(target), "manifest_sha256": sha(target)}))


if __name__ == "__main__":
    main()
