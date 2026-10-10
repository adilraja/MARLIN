"""Seal only the new bounded engineering closeout and retained proof bindings.

No old main, test, live endpoint, renderer, GAMA or ML workflow is invoked.
The manifest and completed finalizer receipt are bound by a later checker.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPRINT = HERE.parents[1]
QA = HERE.parent
MANIFEST = HERE / "closeout_manifest.json"
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}
SEALS = {"milestone_7": "d2e4f7179b6c6cb1e4de8124f796fa96d56466b919a1f30abe6b39af7dbd0715",
         "milestone_8": "16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa"}
COUNTS = {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15}
SPLITS = {"train": 90, "validation": 30, "test": 30}
EXCLUDED = {MANIFEST, HERE / "closeout_command.log", HERE / "closeout_execution.json"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    require(path.is_relative_to(ROOT) and ".." not in path.parts
            and not BLOCKED.intersection(path.parts) and path.suffix != ".pyc", "Unsafe evidence path")
    parent = path
    while parent != ROOT:
        require(not parent.is_symlink(), "Evidence symlinks are prohibited")
        parent = parent.parent
    return path.resolve()


def pin(path):
    path = safe(path)
    require(path.is_file(), "Missing evidence file: " + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(path, inventory):
    row = pin(path)
    require(safe(path) not in EXCLUDED, "Manifest/active finalizer receipt cannot be inventoried")
    require(row["path"] not in inventory or inventory[row["path"]] == row, "Input changed while reading")
    inventory[row["path"]] = row
    value = json.loads(safe(path).read_text(), object_pairs_hook=unique_object,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    require(pin(path) == row, "JSON bytes changed while reading")
    return value


def bind(row, inventory):
    require(set(row) == {"path", "bytes", "sha256"} and type(row["bytes"]) is int
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Invalid evidence pin")
    actual = pin(row["path"])
    require(actual == row and safe(row["path"]) not in EXCLUDED, "Retained pin differs")
    require(row["path"] not in inventory or inventory[row["path"]] == row, "Conflicting input pin")
    inventory[row["path"]] = row
    return actual


def validate_proof(inventory):
    proof_path = HERE / "existing_evidence_validation.json"
    proof = read(proof_path, inventory)
    execution = read(HERE / "existing_evidence_execution.json", inventory)
    command = ["/usr/bin/python3", "-B", str(HERE / "verify_existing_evidence.py"), "--output", str(proof_path)]
    require(proof["kind"] == "sprint_closeout_retained_acceptance_proof" and proof["passed"] is True
            and execution["kind"] == "sprint_closeout_retained_acceptance_actual_execution"
            and execution["passed"] is True and type(execution["return_code"]) is int
            and execution["return_code"] == 0 and execution["command"] == proof["command"] == command
            and execution["cwd"] == str(ROOT), "Actual retained-proof execution binding failed")
    for key in ("live_calls_made", "regression_tests_rerun", "ml_training_or_inference_performed", "old_outputs_written"):
        require(proof[key] is False and execution[key] is False, "Proof performed an unsupported workflow")
    require(proof["captures_requested"] == proof["gama_executions"] == execution["new_renders"]
            == execution["new_gama_executions"] == 0 and proof["biological_approval"] is False
            and proof["new_closeout_documents_validated"] is False and proof["sprint_closeout_seal_issued"] is False,
            "Original proof scope was promoted")
    require(proof["helper_before"] == proof["helper_after"] == execution["source_before"] == execution["source_after"]
            and execution["runner_before"] == execution["runner_after"] and execution["source_pins_unchanged"] is True,
            "Proof program/recorder changed")
    for row in (execution["source_before"], execution["runner_before"], execution["result"], execution["log"], proof["reused_frozen_checker"]):
        bind(row, inventory)
    require(safe(execution["source_before"]["path"]) == HERE / "verify_existing_evidence.py"
            and safe(execution["runner_before"]["path"]) == HERE / "record_existing_evidence.py"
            and execution["result"] == pin(proof_path)
            and safe(execution["log"]["path"]) == HERE / "existing_evidence_command.log", "Proof cites another program/result/log")
    stdout = json.loads(safe(execution["log"]["path"]).read_text(), object_pairs_hook=unique_object)
    require(stdout["passed"] is True and stdout["m7_outputs"] == 4827 and stdout["m8_outputs"] == 119
            and stdout["retained_unittest_cases"] == 360 and stdout["inputs_verified"] == len(proof["input_pins_before"])
            and safe(stdout["result"]) == proof_path and stdout["error"] is None, "Actual proof stdout differs")
    times = [datetime.fromisoformat(value) for value in (execution["started_at_utc"], proof["started_at_utc"],
             proof["finished_at_utc"], execution["finished_at_utc"])]
    require(all(value.tzinfo is not None for value in times) and times == sorted(times)
            and math.isfinite(execution["elapsed_seconds"]) and execution["elapsed_seconds"] >= 0, "Proof execution timing differs")
    before = proof["input_pins_before"]
    require(proof["all_inputs_unchanged"] is True and before == proof["input_pins_after"]
            and len(before) == len({row["path"] for row in before}) == 4859, "First proof input inventory differs")
    require([pin(row["path"]) for row in before] == before, "A first-proof input changed before closeout")
    require(proof["m7_completion"]["unique_sealed_outputs_verified"] == 4827
            and proof["m7_completion"]["capture_counts"] == COUNTS and proof["m7_completion"]["split_image_counts"] == SPLITS
            and proof["historical_m8"]["unique_sealed_outputs_verified"] == 119
            and proof["historical_m8"]["regression_unittest_cases_verified_from_retained_commands_and_logs"] == 360
            and proof["historical_m8"]["historical_failed_package_status_preserved"] is True,
            "Retained acceptance counts or failure scope differ")
    return proof


def validate_status(inventory, proof):
    status = read(HERE / "current_status.json", inventory)
    require(status["kind"] == "gama_marlin_current_engineering_sprint_closeout"
            and status["status"] == "complete_engineering_scope" and status["sprint_acceptance_complete"] is True
            and status["milestone_7_complete"] is True and status["milestone_8_complete"] is True
            and isinstance(status["acceptance_scope"], str) and status["acceptance_scope"].strip(), "Current engineering completion status differs")
    false_flags = ("all_executed_commands_passed", "historical_records_rewritten", "biological_approval", "human_approval_inferred",
                   "ready_for_limited_behaviour_conditioned_study", "ready_for_larger_biological_expansion",
                   "detector_training_or_inference_run_for_closeout", "new_capture_or_gama_execution_for_closeout",
                   "regression_tests_reexecuted_for_closeout", "live_demo_reexecuted_for_closeout",
                   "accepted_groups_recaptured_or_substituted", "background_rgb_equivalence_claimed")
    require(all(status[key] is False for key in false_flags)
            and status["failed_attempts_and_checks_preserved"] is True
            and status["ready_for_further_bounded_engineering_tests"] is True, "Closeout granted unsupported approval or execution scope")
    require(status["capture_counts"] == COUNTS and status["split_image_counts"] == SPLITS
            and status["source_attempt_statuses"] == [False, False, True, True]
            and status["regression_unittest_cases_passed"] == 360 and status["regression_unittest_cases_skipped"] == 0
            and status["annotation_semantics"] == "amodal_direct_evaluated_mesh_projection"
            and status["rendered_visibility"] == "unknown" and status["pose_mapping"] == "static_pose_proxy_v1", "Counts or annotation scope differ")
    milestones = status["milestones"]
    require([row["number"] for row in milestones] == list(range(1, 9)), "Eight ordered milestones required")
    for milestone in milestones:
        require(all(milestone[key] is True for key in ("implemented", "executed", "passed"))
                and milestone["acceptance_scope"] and milestone["name"]
                and milestone["biological_suitability"] in {"not_approved", "provisional", "provisional_engineering_use_only"},
                "Milestone completion exceeded its bounded engineering scope")
        require(milestone["evidence"], "Milestone needs actual evidence anchors")
        for path in milestone["evidence"]:
            bind(pin(path), inventory)
    m7 = read(QA / "milestone_7_manifest.json", inventory)
    m8 = read(QA / "milestone_8_manifest.json", inventory)
    for key, document in (("milestone_7", m7), ("milestone_8", m8)):
        anchor = status["historical_anchors"][key]
        require(safe(anchor["path"]) == QA / (key + "_manifest.json") and pin(anchor["path"])["sha256"] == anchor["sha256"] == SEALS[key]
                and anchor["recorded_sprint_acceptance_complete"] is document["sprint_acceptance_complete"] is False,
                "Original milestone seal or historical status was rewritten")
    require(m8["status"] == status["historical_anchors"]["milestone_8"]["recorded_status"] == "complete_review_with_blocked_milestone_7"
            and m7["capture_counts"] == status["capture_counts"] and m7["split_image_counts"] == status["split_image_counts"], "Current status does not bind the sealed historical counts")
    for key in ("actual_gama_trajectories", "seeds", "snapshot_steps", "gsd_conditions_cm_px", "resolution_px"):
        require(status[key] == m7[key], "Declared capture contract differs: " + key)
    package = status["historical_packaging_check"]
    disposition = read(package["disposition"], inventory)
    require(package["passed"] is False and package["obsolete_expected_schema"] == disposition["expected_schema"] == "1.6.0"
            and package["preserved_final_schema"] == disposition["actual_preserved_final_schema"] == "1.7.0"
            and disposition["original_run_passed"] is False and disposition["rerun_performed"] is False, "Historical packaging failure was promoted")
    live = read(status["latest_retained_marine_demo"]["result"], inventory)
    require(live["passed"] is True and len(live["checks"]) == status["latest_retained_marine_demo"]["checks_passed"] == 14
            and all(live["checks"].values()) and len(live["route_presence_checks"]) == status["latest_retained_marine_demo"]["routes_verified"] == 4
            and all(live["route_presence_checks"].values()), "Retained marine demonstration scope differs")
    memory, gpu = status["memory"], live["gpu_observation"]
    require(memory["permanent_fix_established"] is False and memory["measurement_is_current"] is False
            and memory["controller_animation_phase_preserved"] is False
            and memory["last_recorded_free_mib"] == gpu["free_mib"] == 546
            and memory["capture_guard_minimum_free_mib"] == gpu["minimum_free_mib_before_render"] == 768
            and memory["last_recorded_at_utc"] == gpu["recorded_at_utc"], "Closeout promoted memory/phase recovery evidence")
    human_review = read(QA / "m5_human_review.json", inventory)
    require(milestones[4]["human_reviewer"] == human_review["reviewer"] == "MAR"
            and human_review["biological_approval"] is False, "Closeout inferred a new human/biological approval")
    pilot = status["pilot_audit"]
    require(pilot["passed"] is True and safe(pilot["result"]) == QA / "m8_pilot_audit_02.json"
            and safe(pilot["execution"]) == QA / "m8_pilot_audit_02_execution.json"
            and safe(pilot["report"]) == SPRINT / "M8_READ_ONLY_PILOT_AUDIT.md", "Status cites another retained Pilot audit")
    for key in ("result", "execution", "report"):
        bind(pin(pilot[key]), inventory)
    require(safe(status["latest_retained_marine_demo"]["actual_execution"]) == QA / "m7_completion_01/final_live_execution.json"
            and status["latest_retained_marine_demo"]["observation_date_utc"] == live["finished_at_utc"][:10], "Retained live observation date/receipt differs")
    bind(pin(status["latest_retained_marine_demo"]["actual_execution"]), inventory)
    require(status["supersedes"] == {"earlier_m7_capture_blocker_resolved": True, "missing_images": 0,
            "missing_snapshot_groups": 0, "historical_m8_report_is_dated_snapshot": True,
            "historical_reports_and_seals_unchanged": True}, "Current closeout altered the historical disposition")
    require(safe(status["evidence_validation"]) == HERE / "existing_evidence_validation.json"
            and safe(status["evidence_validation_execution"]) == HERE / "existing_evidence_execution.json", "Status cites another actual proof")
    bind(pin(status["specification"]), inventory)
    for path in status["current_documents"].values():
        bind(pin(path), inventory)
    return status


def validate_documents(status, inventory):
    results = []
    # These required statements bind the actual reviewed prose to its limited
    # status; the original documents and evidence remain independently pinned.
    facts = {
        "report": ("the sprint was completed for its bounded engineering scope. milestones 7 and 8 were closed.",
                   "75 target-present and 75 physically target-removed images", "90 train, 30 validation and 30 test images",
                   "360 unittest cases with zero skips", "all 4,827 m7 sealed outputs and 119 historical m8 outputs",
                   "4,859 unique input pins", "maximum projection-matrix error zero",
                   "1,680 frozen-state checks, 450 settling probes, 180 restoration checks and 135 coexistence checks",
                   "biological approval, approval for a limited research study, and approval for larger biological expansion remained false",
                   "a permanent gpu memory fix was not established", "dated observation does not describe current gpu headroom"),
        "reproduction": ("verified 150-image capture set", "90/30/30 train/validation/test split",
                         "360 passing unittest cases with zero skips", "historical batch retained passed: false",
                         "no training, inference or replacement performance result was needed for this closeout",
                         "scientific use or larger biological expansion requires its own supported review scope",
                         "offline closeout does not certify a new live session")}
    for key, name in (("report", "GAMA_MARLIN_SPRINT_CLOSEOUT.md"), ("reproduction", "SPRINT_CLOSEOUT_REPRODUCTION.md")):
        path = SPRINT / name
        require(safe(status["current_documents"][key]) == path, "Current document path differs")
        text = path.read_text()
        normalized = re.sub(r"\s+", " ", text.replace("*", "").replace("`", "")).lower()
        require(all(fact in normalized for fact in facts[key]), "Reviewed document claim or scope changed: " + name)
        if key == "report":
            require(re.findall(r"^\| ([1-8]) [—–-]", text, flags=re.MULTILINE) == [str(value) for value in range(1, 9)],
                    "Report does not retain all eight milestone outcomes")
            source = read(QA / "milestone_7_manifest.json", inventory)["fresh_independent_scene_proofs"]
            require({key: source[key] for key in ("state_checks", "settling_probes", "restoration_checks", "coexistence_checks", "projections", "maximum_projection_matrix_error")}
                    == {"state_checks": 1680, "settling_probes": 450, "restoration_checks": 180, "coexistence_checks": 135,
                        "projections": 150, "maximum_projection_matrix_error": 0}, "Document check counts differ from the sealed source")
        links = []
        for target in re.findall(r"\[[^\]]+\]\((<[^>]+>|[^)]+)\)", text):
            target = unquote(target.strip().strip("<>").split("#", 1)[0])
            require(target and not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target), "Closeout links must be real local evidence")
            target = re.sub(r":\d+$", "", target)
            linked = safe(Path(target) if Path(target).is_absolute() else path.parent / target)
            bind(pin(linked), inventory)
            links.append(str(linked.relative_to(ROOT)))
        require(links, "Closeout document has no evidence links")
        results.append({"document": pin(path), "linked_evidence": links, "reviewed_claims_match_bounded_status": True})
    return results


def main():
    require(len(sys.argv) == 1 and not MANIFEST.exists(), "Use the fixed exclusive closeout finalizer without arguments")
    inventory = {}
    bind(pin(Path(__file__)), inventory)
    bind(pin(HERE / "record_closeout.py"), inventory)
    proof = validate_proof(inventory)
    status = validate_status(inventory, proof)
    documents = validate_documents(status, inventory)
    before = sorted(inventory.values(), key=lambda row: row["path"])
    require([pin(row["path"]) for row in before] == before, "Closeout input changed during finalization")
    require([pin(row["path"]) for row in proof["input_pins_before"]] == proof["input_pins_before"], "A first-proof input changed during closeout")
    result = {"kind": "gama_marlin_engineering_sprint_closeout_manifest", "status": "complete_engineering_scope", "passed": True,
              "completed_at_utc": datetime.now(timezone.utc).isoformat(), "sprint_acceptance_complete": True,
              "acceptance_scope": status["acceptance_scope"], "milestones": status["milestones"],
              "capture_counts": COUNTS, "split_image_counts": SPLITS, "original_milestone_seal_sha256": SEALS,
              "retained_regression_unittest_cases": 360, "historical_failed_packaging_check_preserved": True,
              "existing_evidence_validation": pin(HERE / "existing_evidence_validation.json"),
              "actual_existing_evidence_execution": pin(HERE / "existing_evidence_execution.json"),
              "first_proof_input_count": len(proof["input_pins_before"]), "all_first_proof_inputs_current_and_unchanged": True,
              "current_status": pin(HERE / "current_status.json"), "document_link_checks": documents,
              "all_closeout_inputs_unchanged": True, "outputs": before, "unique_output_paths": len(before),
              "manifest_self_hash_deferred": True, "completed_finalizer_receipt_requires_later_independent_binding": True,
              "deferred_finalizer_log": str((HERE / "closeout_command.log").relative_to(ROOT)),
              "deferred_finalizer_execution": str((HERE / "closeout_execution.json").relative_to(ROOT)),
              "biological_approval": False, "human_approval_inferred": False, "all_executed_commands_passed": False,
              "new_tests_executed": False, "live_calls_made": False, "captures_requested": 0,
              "new_gama_executions": 0, "ml_training_or_inference_performed": False, "historical_records_rewritten": False}
    with MANIFEST.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "manifest": pin(MANIFEST), "outputs": len(before), "capture_counts": COUNTS,
                      "first_proof_inputs_rechecked": len(proof["input_pins_before"]), "separate_later_seal_check_required": True}, indent=2))


if __name__ == "__main__":
    main()
