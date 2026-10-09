"""Seal partial M7 evidence without claiming complete-set acceptance. No live calls."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/gama_marlin_v1"
QA = BASE / "qa"
FORBIDDEN = {"_build", "extscache", "__pycache__", ".cache"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def safe(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    path.relative_to(ROOT)
    if FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated/cache path is outside progress evidence scope")
    if path.is_symlink():
        raise ValueError("Progress evidence may not be a symlink")
    return path


def digest(path):
    h = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pin(path):
    path = safe(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": digest(path)}


def read(path):
    return json.loads(safe(path).read_text())


def save(path, data):
    with safe(path).open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    started = utc()
    manifest_path = QA / "m7_progress_manifest.json"
    require(not manifest_path.exists(), "Progress manifest already exists")
    before = {}

    def remember(path, expected=None):
        item = pin(path)
        if expected is not None:
            require(item["sha256"] == expected, f"Evidence hash changed: {item['path']}")
        before[item["path"]] = item
        return item

    def checked_json(path):
        remember(path)
        return read(path)

    declaration_path = BASE / "m7_capture_declaration.json"
    declaration = checked_json(declaration_path)
    require(digest(declaration_path) == "4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557",
            "Declaration changed")
    campaign = QA / "m7_live_02"
    result = checked_json(campaign / "results.json")
    require(result["passed"] is False and result["runtime_code_unchanged"]
            and result["declaration_unchanged"], "Unexpected original campaign status")
    preflight = checked_json(QA / "m7_pending_preflight_01/results.json")
    require(preflight["passed"] and preflight["preflight_only"]
            and preflight["scene_mutation_attempted"] is False
            and preflight["source_campaign_unchanged"]
            and preflight["runtime_code_unchanged"], "Pending preflight did not pass")
    for item in preflight["runtime_code_before"]:
        remember(item["path"], item["sha256"])
    plan = checked_json(QA / "m7_pending_preflight_01/pending_plan.json")
    remember(preflight["pending_plan"]["path"], preflight["pending_plan"]["sha256"])
    for item in plan["source_tree_pins"] + plan["capture_protocol_code_pins"]:
        remember(item["path"], item["sha256"])
    require(len(plan["accepted_source_groups"]) == 12 and len(plan["pending_groups"]) == 3
            and plan["accepted_source_images"] == 120 and plan["pending_images"] == 30,
            "Pending selection changed")

    images = result["traceable_images"]
    require(len(images) == 120 and len({row["image_id"] for row in images}) == 120,
            "Wrong or duplicate partial image set")
    presence = Counter(row["variant"] for row in images)
    partitions = Counter(row["split"] for row in images)
    require(presence == {"present": 60, "absent": 60}
            and partitions == {"train": 90, "validation": 30}, "Wrong partial image partitions")
    for row in images:
        for prefix in ("rgb", "annotation", "yolo"):
            remember(campaign / row[f"{prefix}_file"], row[f"{prefix}_sha256"])
        remember(campaign / row["group_manifest"], row["group_manifest_sha256"])
        for item in row["source_files"]:
            remember(item["path"], item["sha256"])

    groups = []
    state_checks = probes = restore_checks = coexistence_checks = release_checks = 0
    max_matrix_error = 0
    proof_input_names = {"manifest": "manifest.json", "resolved_state": "resolved_state.json",
        "absent_resolved_state": "absent_resolved_state.json", "present_scene": "present_scene.usdc",
        "absent_scene": "absent_scene.usdc"}
    for run in result["runs"]:
        require(len(run["cleanup_checks"]) == 12 and all(run["cleanup_checks"].values()),
                "Run cleanup failed")
        release_checks += len(run["cleanup_checks"])
        for group in run["groups"]:
            if not group.get("passed"):
                continue
            step = campaign / "captures" / run["run_id"] / f"step_{group['step_index']:03d}"
            for item in group["retained_group"]["files"]:
                remember(step / item["path"], item["sha256"])
            manifest = checked_json(step / "group/manifest.json")
            require(manifest["passed"] and manifest["all_variant_state_checks_match"]
                    and all(manifest["restoration_checks"].values()), "Group restoration/state failed")
            state_checks += len(manifest["state_checks"])
            restore_checks += len(manifest["restoration_checks"])
            require(all(group["coexistence_checks"].values()), "Coexistence failed")
            coexistence_checks += len(group["coexistence_checks"])
            probes += sum(row["camera_and_pixel_checks"]["settling_probes"]
                          for row in group["group_checks"]["images"])
            proof_path = QA / "m7_scene_validation_02" / f"{run['run_id']}__step_{group['step_index']:03d}.json"
            proof = checked_json(proof_path)
            require(proof["kind"] == "m7_independent_retained_group_verification"
                    and proof["passed"] and all(proof["checks"].values())
                    and len(proof["captures"]) == 10, "Independent proof failed")
            require(safe(proof["group"]) == step / "group", "Independent proof bound to wrong group")
            for key, filename in proof_input_names.items():
                remember(step / "group" / filename, proof["inputs"][f"{key}_sha256"])
            remember(ROOT / "experiments/gsd_pilot_v1/environment.json",
                     proof["inputs"]["pilot_environment_sha256"])
            for capture in proof["captures"]:
                require(capture["passed"], "Independent camera/annotation check failed")
                max_matrix_error = max(max_matrix_error, capture["maximum_projection_matrix_error"])
            groups.append({"run_id": run["run_id"], "step_index": group["step_index"],
                           "split": run["split"], "manifest": pin(step / "group/manifest.json"),
                           "independent_proof": pin(proof_path)})
    require((len(groups), state_checks, probes, release_checks) == (12, 1344, 360, 60),
            "Unexpected partial capture counts")

    review = checked_json(QA / "m7_partial_review/visual_inspection.json")
    require(review["status"] == "incomplete" and review["reviewed_images"] == 120
            and review["expected_images"] == 150 and review["biological_approval"] is False,
            "Unexpected partial review scope")
    observations = {row["image_id"]: row for row in review["observations"]}
    require(len(observations) == 120 and set(observations) == {row["image_id"] for row in images},
            "Partial review image IDs differ")
    for row in images:
        observation = observations[row["image_id"]]
        require(observation["rendered_visibility"] == "unknown"
                and observation["physically_present"] == row["target_present"]
                and observation["biological_approval"] is False
                and observation["manual_observation_is_machine_visibility_label"] is False,
                "Review invented visibility or biological labels")
        for prefix in ("rgb", "annotation", "yolo"):
            require(safe(observation[f"{prefix}_file"]) == campaign / row[f"{prefix}_file"],
                    "Review source path differs")
            remember(observation[f"{prefix}_file"], row[f"{prefix}_sha256"])
        remember(observation["contact_sheet"], observation["contact_sheet_sha256"])

    preservation = checked_json(QA / "m7_partial_preservation.json")
    require(preservation["passed"] and all(v["passed"] for v in preservation["preservation"].values()),
            "Partial preservation failed")
    test_files = ["m7_01_dataset_state_execution.json", "m7_01_transaction_results.json",
                  "m7_01_dataset_routes_execution.json", "m7_03_dataset_client_results.json",
                  "m7_02_capture_preflight_execution.json", "m7_05_dataset_pending_results.json"]
    test_cases = 0
    for filename in test_files:
        record = checked_json(QA / filename)
        entries = record.get("results") or [record.get("result", record)]
        for entry in entries:
            require(entry["return_code"] == 0 and entry.get("passed", True), "Test record failed")
            test_cases += entry.get("tests", entry.get("tests_passed", 0))
            if "log" in entry:
                remember(entry["log"], entry["log_sha256"])
    require(test_cases == 121, "Relevant test count changed")

    split_manifest = {"kind": "m7_partial_trajectory_split_manifest", "status": "incomplete",
        "complete_dataset": False, "expected_images": 150, "recorded_images": 120,
        "source_campaign_passed": False, "declaration": pin(declaration_path),
        "source_campaign": pin(campaign / "results.json"), "actual_split_counts": dict(partitions),
        "policy": declaration["split_policy"], "declared_runs": declaration["runs"],
        "missing_groups": review["missing_groups"], "images": images,
        "annotation_semantics": result["annotation_semantics"], "biological_approval": False}
    families = {}
    for row in images:
        for identity in [row["encounter_group_id"], *row["related_run_ids"]]:
            require(families.setdefault(identity, row["split"]) == row["split"], "Split leakage")
    save(QA / "m7_partial_split_manifest.json", split_manifest)

    # Inventory only explicitly scoped M7 evidence; prune prohibited directories.
    paths = {safe(value["path"]) for value in before.values()}
    paths.update({Path(__file__), BASE / "M7_CAPTURE_PROGRESS.md",
                  ROOT / "integrations/gama/DATASET_CAPTURE_V2.md",
                  ROOT / "tools/export_gama_dataset_v2.py"})
    for prefix in ("capture_gama_dataset", "aggregate_gama_dataset", "test_gama_dataset", "test_gama_capture_preflight"):
        paths.update((ROOT / "tools").glob(prefix + "*.py"))
    for entry in QA.iterdir():
        if not (entry.name.startswith("m7_") or entry.name in {
            "build_m7_review.py", "build_m7_partial_review.py", "check_m7_preservation.py",
            "finalize_m7_review.py", "verify_m7_group.py", "verify_m7_campaign_groups.py"}):
            continue
        if entry == manifest_path:
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
    require(diff.returncode == 0, "git diff --check failed: " + diff.stdout + diff.stderr)
    require(all(pin(item["path"]) == item for item in before.values()), "Input changed during audit")
    refusals = [attempt for run in result["runs"] for group in run["groups"]
                for attempt in group.get("capture_attempts", []) if attempt.get("retryable_no_render_headroom")]
    summary = {"kind": "m7_partial_evidence_validation", "validation_passed": True,
        "milestone_complete": False, "complete_dataset": False, "expected_images": 150,
        "validated_images": 120, "presence_counts": dict(presence), "split_counts": dict(partitions),
        "accepted_groups": groups, "remaining_groups": review["missing_groups"],
        "state_checks": state_checks, "settling_probes": probes, "restoration_checks": restore_checks,
        "coexistence_checks": coexistence_checks, "release_cleanup_checks": release_checks,
        "independent_proof_count": len(groups), "maximum_camera_projection_matrix_error": max_matrix_error,
        "relevant_offline_test_cases_passed": test_cases, "no_render_headroom_refusals": len(refusals),
        "protected_inventory_counts": {k:v["protected_files_checked"] for k,v in preservation["preservation"].items()},
        "input_pins_before": list(before.values()), "input_pins_unchanged": True,
        "python_syntax_checked": syntax, "git_diff_check": {"return_code": diff.returncode,
        "stdout": diff.stdout, "stderr": diff.stderr}, "live_calls_made": False,
        "new_images_rendered": 0, "biological_approval": False, "milestone_8_started": False,
        "command": [sys.executable, *sys.argv], "started_at_utc": started, "finished_at_utc": utc()}
    save(QA / "m7_progress_validation.json", summary)
    log = ("Partial evidence validation passed: 120/150 images; 12/15 groups; "
           "121 relevant offline test cases passed. Milestone 7 remains incomplete; GPU headroom blocked.\n")
    with (QA / "m7_progress.log").open("x") as stream:
        stream.write(log)
    paths.update({QA / "m7_progress_validation.json", QA / "m7_progress.log"})
    inventory = [pin(path) for path in sorted(paths)]
    save(manifest_path, {"kind": "m7_progress_evidence_manifest", "milestone": 7,
        "status": "incomplete", "passed": False, "milestone_complete": False,
        "partial_evidence_validation_passed": True, "implemented": True,
        "expected_images": 150, "validated_images": 120, "remaining_images": 30,
        "pending_only_preflight_passed": True, "resource_blocked": True,
        "blocker": "GPU headroom below unchanged 768 MiB pre-render minimum",
        "last_retained_free_gpu_mib": 374, "resource_observation_utc": "2026-10-09 16:54:05 UTC",
        "source_campaign_passed": False, "final_dataset_exported": False,
        "biological_approval": False, "milestone_8_started": False,
        "recorded_at_utc": utc(), "outputs": inventory,
        "scope": "Partial M7 code, declaration, attempt evidence, tests and reviews; not final acceptance. Runtime/cache dependency bytes excluded.",
        "execution_record": "experiments/gama_marlin_v1/qa/m7_progress_execution.json"})
    print(log, end="")
    print(f"Progress manifest: {len(inventory)} output pins; sha256 {digest(manifest_path)}")


if __name__ == "__main__":
    main()
