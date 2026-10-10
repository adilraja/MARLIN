"""Write a new M7 engineering report/seal only from current passed proofs.

This is an offline finalization command. It revalidates the accepted retained
artifact set, checks final read-only live evidence and restart/capture records,
and writes two exclusive new files. It never controls Kit, captures images,
trains a detector, rewrites historical reports or grants biological approval.
The finalizer's own stdout/execution must be bound by a later seal-check record
to avoid a self-hash cycle. Actively appended source Kit logs are excluded;
only verified fixed-prefix snapshots are inventoried as immutable log evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SPRINT = ROOT / "experiments/gama_marlin_v1"
QA = SPRINT / "qa"
HERE = Path(__file__).resolve().parent
REPORT = SPRINT / "M7_COMPLETION_REPORT.md"
MANIFEST = QA / "milestone_7_manifest.json"
CAPTURE_CLIENT_SHA = "b634b127dc7f607deb63a749d3cc64727d6b88efcf120f25e83941e968415fd3"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import validate_completion as validation
import aggregate_capture_set as aggregate
import snapshot_runtime_logs as snapshot_logs

require, safe, digest = validation.require, validation.safe, validation.digest
DEMO_CHECKS = frozenset(("eleven_original_swimmers_running", "all_original_swimmers_advanced",
    "controller_configuration_preserved", "no_deformation_errors", "ocean_advanced", "ocean_configuration_preserved",
    "renderer_settings_preserved", "stable_scene_attributes_preserved", "original_camera_preserved", "layers_unchanged",
    "no_owned_actor_before", "no_private_root_before", "no_owned_actor_after", "no_private_root_after"))
ROUTES = frozenset(("/scene/marine/setup", "/scene/cetaceans/gallery", "/integration/gama/v2/actor/paired-capture",
                    "/integration/gama/v2/actor/dataset-capture"))


def now():
    return datetime.now(timezone.utc).isoformat()


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Evidence timestamp lacks a timezone")
    return parsed.astimezone(timezone.utc)


def tree(pins, directory, excluded=()):
    """Inventory scoped immutable files, skipping declared streams before I/O."""
    directory, excluded = safe(directory), {safe(path) for path in excluded}
    require(directory.is_dir(), "Required final evidence directory missing: " + str(directory))
    count = 0
    for parent, directories, files in os.walk(directory, followlinks=False):
        require(not validation.BLOCKED.intersection(directories), "Generated evidence directory prohibited")
        for name in directories + files:
            require(not (Path(parent) / name).is_symlink(), "Evidence directory symlinks prohibited")
        for name in sorted(files):
            path = safe(Path(parent) / name)
            if path in excluded:
                continue
            pins.add(path)
            count += 1
    return count


def command_args(command, acceptance):
    """Recover the actual validator input paths from its retained command."""
    require(validation.has_script(command, HERE / "validate_completion.py"), "Execution is not the actual acceptance validator")
    require(validation.argument(command, "--output") == acceptance, "Acceptance execution points to another result")
    arguments = {}
    for key in ("campaign", "scene-verifications", "review", "dataset", "preservation", "history-preservation"):
        arguments[key.replace("-", "_")] = validation.argument(command, "--" + key)
    execution_records = []
    for index, item in enumerate(command):
        if item == "--execution-record":
            require(index + 1 < len(command), "Acceptance command has incomplete execution argument")
            execution_records.append(safe(command[index + 1]))
    require(execution_records, "Actual acceptance execution records were omitted")
    return argparse.Namespace(**arguments, execution_record=execution_records)


def checked_execution(pins, record):
    command = validation.check_command(pins, record)
    if "source_sha256_before" in record:
        require(len(command) > 2 and command[1] == "-B" and command[2].endswith(".py")
                and record["source_sha256_before"] == record["source_sha256_after"] == digest(safe(command[2])),
                "Actual command program SHA changed before/after execution")
        pins.add(safe(command[2]), record["source_sha256_before"])
    if "runner_sha256_before" in record:
        runner = record.get("runner_command", [])
        require(len(runner) > 2 and runner[1] == "-B" and runner[2].endswith(".py")
                and record["runner_sha256_before"] == record["runner_sha256_after"] == digest(safe(runner[2])),
                "Actual command recorder SHA changed before/after execution")
        pins.add(safe(runner[2]), record["runner_sha256_before"])
    return command


def current_acceptance(pins, path, execution_records):
    proof = pins.load(path)
    require(proof.get("kind") == "m7_post_m8_completion_artifact_validation" and proof.get("passed") is True
            and proof.get("all_inputs_unchanged") is True and proof.get("biological_approval") is False
            and proof.get("human_approval_inferred") is False and proof.get("uninterrupted_successful_capture_claimed") is False
            and proof.get("detector_training_or_inference_run") is False
            and proof.get("capture_counts") == {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15},
            "Require an actual passed current engineering acceptance result")
    require(proof["input_pins_before"] == proof["input_pins_after"], "Acceptance input pins changed")
    validation.exact_rows(pins, proof["input_pins_before"])
    all_commands, execution_paths = [], []
    for supplied in execution_records:
        record = pins.load(supplied)
        require(record.get("passed") is not False, "Final successful command wrapper failed")
        commands = list(validation.command_records(record))
        require(commands, "Final execution wrapper has no actual command")
        for command_record in commands:
            all_commands.append(checked_execution(pins, command_record))
        execution_paths.append(str(safe(supplied).relative_to(ROOT)))
    commands = [command for command in all_commands if validation.has_script(command, HERE / "validate_completion.py")]
    require(len(commands) == 1, "Exactly one successful actual acceptance invocation required")
    args = command_args(commands[0], path)
    current = validation.validate(args, pins)
    for path in args.execution_record:
        for record in validation.command_records(pins.load(path)):
            checked_execution(pins, record)
    for key in ("capture_counts", "source_attempts", "fresh_independent_scene_proofs", "manual_review", "dataset", "aggregate_command", "export_command"):
        require(proof[key] == current[key], "Current acceptance differs in " + key)
    for key in ("protected_counts", "protected_inventory_count_sum", "original_m6_source_copies", "sealed_incomplete_m7_outputs", "sealed_m8_outputs", "historical_m7_progress_status", "historical_m8_status", "historical_records_unchanged"):
        require(proof["historical_preservation"][key] == current["historical_preservation"][key], "Current historical preservation differs")
    return proof, args, all_commands, execution_paths


def final_live(pins, path, commands, capture_finished):
    report = pins.load(path)
    require(report.get("kind") == "m8_read_only_live_demo_check" and report.get("passed") is True
            and set(report.get("checks", {})) == DEMO_CHECKS and all(value is True for value in report["checks"].values())
            and set(report.get("route_presence_checks", {})) == ROUTES and all(value is True for value in report["route_presence_checks"].values())
            and report.get("source_pins_unchanged") is True and report["source_pins_before"] == report["source_pins_after"]
            and report.get("scene_mutation_attempted") is False and report.get("captures_requested") == 0
            and report.get("kit_restart_requested") is False and report.get("biological_approval") is False,
            "Final read-only marine check did not pass all fourteen checks and routes")
    require(utc(report["started_at_utc"]) >= capture_finished, "Final live check predates the final accepted capture")
    for source in report["source_pins_before"]:
        pins.add(ROOT / source["path"], source["sha256"])
    require(len(report["http_requests"]) == 5 and all(row["method"] == "GET" and row["http_status_code"] == 200 for row in report["http_requests"]),
            "Final live proof was not the bounded successful read-only request set")
    actual_commands = [command for command in commands if validation.has_script(command, ROOT / "tools/verify_gama_m8_demo.py")]
    require(len(actual_commands) == 1 and validation.argument(actual_commands[0], "--output") == path.parent,
            "Final live check lacks its actual successful command/log execution")
    tree(pins, path.parent)
    return {"result": validation.capture.pin(path), "actual_command": actual_commands[0], "checks": report["checks"],
            "route_presence_checks": report["route_presence_checks"], "gpu_observation": report.get("gpu_observation"),
            "read_only_check_not_capture_headroom_approval": True}


def capture_commands(pins):
    records = []
    cases = (("supplement_01", 1, 8), ("step_016", 0, 16), ("step_032", 0, 32))
    for stem, expected_code, step in cases:
        execution = pins.load(HERE / (stem + "_execution.json"))
        command = execution["command"]
        require(type(execution.get("return_code")) is int and execution["return_code"] == expected_code and "-B" in command,
                "Capture command status differs from its actual source attempt")
        script = ROOT / "tools/capture_gama_dataset_pending_v2.py" if stem == "supplement_01" else HERE / "capture_one_pending_snapshot.py"
        require(validation.has_script(command, script), "Capture command identifies another client")
        if stem == "supplement_01":
            require(validation.argument(command, "--output") == QA / "m7_supplement_01", "Failed supplement command used another output")
        else:
            require(command.count("--step") == 1 and command[command.index("--step") + 1] == str(step), "Single-state capture command changed its selected state")
        log_path = pins.add(HERE / (stem + "_command.log"))
        require(log_path.stat().st_size > 0, "Capture command stdout/stderr log is missing")
        records.append({"execution": validation.capture.pin(HERE / (stem + "_execution.json")),
                        "command": command, "return_code": expected_code, "log": validation.capture.pin(log_path),
                        "failed_overall_status_preserved": expected_code != 0})
    return records


def restart_proofs(pins, snapshot_dir):
    summary = pins.load(snapshot_dir / "manifest.json")
    require(summary.get("kind") == "m7_fixed_prefix_runtime_log_snapshots" and summary.get("passed") is True
            and summary.get("source_streams_can_append_after_snapshot") is True
            and summary["helper_sha256_before"] == summary["helper_sha256_after"] == digest(HERE / "snapshot_runtime_logs.py")
            and len(summary["snapshots"]) == 3, "Require three actual fixed-prefix runtime log snapshots")
    exclusions, records = [], []
    for index, snapshot in enumerate(summary["snapshots"], 1):
        directory = QA / f"kit_restart_{index:02d}"
        source = safe(ROOT / snapshot["source_log"])
        require(source == directory / "kit_process.log" and snapshot["copy_exact_initial_prefix"] is True
                and snapshot["original_source_log_sealed_as_immutable"] is False and snapshot["source_stream_may_append"] is True
                and snapshot["initial_source_size_bytes"] == snapshot["initial_bytes_read"] == snapshot["source_prefix_bytes_rechecked"] == snapshot["copy_bytes"]
                and snapshot["source_initial_prefix_sha256"] == snapshot["source_rechecked_prefix_sha256"] == snapshot["copy_sha256"],
                "Runtime log snapshot changed its fixed-prefix semantics")
        pins.add(ROOT / snapshot["copy"], snapshot["copy_sha256"], snapshot["copy_bytes"])
        require(snapshot_logs.prefix_sha(source, snapshot["initial_bytes_read"]) == snapshot["copy_sha256"], "Retained source log prefix differs from its immutable snapshot")
        phases = []
        for phase in ("stop_launch", "restore"):
            path = directory / (phase + "_result.json")
            result = pins.load(path)
            require(result.get("passed") is True and result.get("desktop_restarted") is False
                    and result.get("gpu_guard_changed") is False and result.get("capture_requested") is False
                    and result.get("controller_animation_phase_preserved") is False, "Restart proof changed its authorization/scope/phase limitation")
            if phase == "restore":
                require(result.get("checks") and all(value is True for value in result["checks"].values())
                        and result["actor_after"]["owned"] is False and result["actor_after"]["actor_count"] == 0,
                        "Restart recovery did not restore the recorded demo and release ownership")
            execution = pins.load(directory / (phase + "_execution.json"))
            require(execution.get("return_code") == 0 and "-B" in execution["command"], "Actual restart command did not pass")
            expected_helper = directory / "restart_kit.py" if index == 1 else HERE / "repeat_kit_restart.py"
            require(validation.has_script(execution["command"], expected_helper)
                    and phase.replace("_", "-") in execution["command"]
                    and (index == 1 or validation.argument(execution["command"], "--output") == directory),
                    "Restart execution command identifies another helper/phase/output")
            if index >= 2:
                require(result["source_helper_sha256_before"] == result["source_helper_sha256_after"] == digest(expected_helper)
                        and result["base_helper_unchanged"] is True
                        and result["base_restart_helper"]["sha256"] == digest(QA / "kit_restart_01/restart_kit.py"), "Restart source helper proof changed")
            pins.add(directory / (phase + "_command.log"))
            phases.append({"result": validation.capture.pin(path), "execution": validation.capture.pin(directory / (phase + "_execution.json")),
                           "actual_command": execution["command"], "source_status": result["passed"]})
        tree(pins, directory, (source,))
        exclusions.append({"path": str(source.relative_to(ROOT)), "reason": "Original runtime stream may append; only the fixed initial prefix is sealed.",
                           "snapshot": snapshot})
        records.append({"directory": str(directory.relative_to(ROOT)), "phases": phases, "animation_phase_preserved": False})
    tree(pins, snapshot_dir)
    return records, exclusions


def report_text(proof, args, old_attempt, live, restart, inventory_count):
    scenes, preservation = proof["fresh_independent_scene_proofs"], proof["historical_preservation"]
    gpu = live.get("gpu_observation") or {}
    free = gpu.get("free_mib", "unavailable")
    timestamp = now()
    return f"""# Milestone 7 engineering completion

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**.

Milestone: **Produce a small GAMA-driven capture and annotation test set**.

Recorded at UTC `{timestamp}`. The declared bounded engineering test set was
completed, independently verified, reviewed and exported. All 150 declared
images were retained: 75 physically target-present and 75 explicit
target-removed images in 15 snapshot groups and 75 camera-condition pairs.
This report recorded the later M7 completion; it did not alter the earlier
incomplete-M7 progress record or the sealed M8 review.

## Actual sources and split

The set used five already executed fresh-process M5 GAMA trajectories, with
seeds **1, 42, 184729, 20261008 and 2147483647**. M7 reused and reparsed their
retained actual GAMA outputs; no new GAMA simulation or synthetic replacement
trajectory was created. Steps 8, 16 and 32 supplied simulation times 4, 8 and
16 seconds: shallow swimming at 0.5 m, descent at 1.9 m and ascent at 1.6 m.
The pre-inspection declaration remained SHA256
`{validation.DECLARATION_SHA}`.

Every snapshot used the same five nominal GSD conditions, **0.5, 1, 2, 3 and
4 cm/px**, and a 1024 × 768 ideal nadir perspective camera. Only camera height
varied within each frozen snapshot/pair; actual matrices, optics, exposure and
projection checks were retained. Physical target absence was produced by
removing only `/MarlinGamaPorpoise` from a private frozen counterpart. The
positive and absent scenes retained their common background identities and
source context; an absent target was neither hidden nor merely submerged.

The exported split contained **90 train, 30 validation and 30 test images**.
Seeds 1/42/184729 stayed in train, 20261008 in validation and 2147483647 in test.
Whole trajectories/encounter families, selected snapshots, all GSDs,
present/removed counterparts and related repeat identifiers remained in one
partition. This grouping did not establish ecological independence or
statistical generalization.

## Transparent capture history

| Attempt | Original overall status retained | Accepted contribution |
| --- | --- | --- |
| `qa/m7_live_02` | failed | 12 groups / 120 images |
| `qa/m7_supplement_01` | failed | max-seed step 8 / 10 images |
| `qa/m7_supplement_step_016` | passed | max-seed step 16 / 10 images |
| `qa/m7_supplement_step_032` | passed | max-seed step 32 / 10 images |

The earlier `qa/m7_live_01` attempt also remained failed. It retained
{old_attempt['images']} images in {old_attempt['groups']} passed groups, and
those images were **excluded** from the accepted set. Thus the selected four
origins preserved statuses `[false, false, true, true]`; the wider history also
included that earlier failed attempt. No failed campaign or failed source run
was relabelled as successful. The accepted set was an explicit byte-identical
offline aggregation, not one uninterrupted successful capture campaign.

The original 120 images and the first supplement's accepted step-8 images were
not recaptured. After another exhausted pre-render GPU refusal, authorized
Kit-only restarts enabled the two remaining snapshots to run as separate
single-state attempts. The unchanged guard required 768 MiB free before
rendering. A restart provided memory for bounded capture work; **a permanent
GPU memory fix was not established**. The controller/ocean phases restarted,
and an uninterrupted animation phase was not preserved. Each later snapshot
was independently frozen and verified; cross-snapshot background animation
continuity was not claimed. Desktop applications were not restarted by these
Kit-only procedures. Final read-only demo evidence observed `{free}` MiB free;
that observation did not authorize further rendering or prove sufficient
headroom for another capture.

## Verification, actual inspection and export

All 15 copied groups received fresh executions of the unchanged retained-USD
verifier, rather than relabelled old source proofs. Actual saved positive and
negative scenes, exact owned-root removal, zero time samples, background and
state identities, GAMA pose/depth, camera conditions and direct mesh
annotations were checked. All **{scenes['projections']}** projections passed;
the maximum retained projection-matrix error was
`{scenes['maximum_projection_matrix_error']}`. Actual records contained
**{scenes['state_checks']} frozen-state checks**, **{scenes['settling_probes']}
settling probes**, **{scenes['restoration_checks']} restoration checks** and
**{scenes['coexistence_checks']} coexistence checks**. Local dependency hashes
were rechecked; unresolved runtime shader dependencies remained explicit and
their generated/cache bytes were not opened.

All 150 contact-sheet views received source-bound Codex engineering
presentation observations: the original 120 notes remained unchanged, and the
new 30 were inspected after capture. Final sheets had exactly the same PNG
bytes as the inspected source previews; observations were transferred through
explicit original/copy hashes. Generating sheets alone was not treated as
inspection, and no visibility threshold was used to select, discard or
replace frames. Ambiguous physically present positives remained present and
labelled by their direct amodal geometry.

The export copied 150 PNGs, 150 YOLO labels and 150 annotation JSONs unchanged
and retained 453 dataset artifacts plus its separately pinned manifest.
Class **0, harbour_porpoise**, labelled only the bridge-owned target. Removed
counterparts had no target box and empty target labels; other demonstration
wildlife remained unlabelled background. The dataset descriptor recorded the
declared partitions and was not a training command. No detector training,
inference, replacement performance result or generalization study was run.

Retained review/export/acceptance evidence:

- [Accepted aggregate results]({args.campaign / 'results.json'})
- [Fresh fifteen-group retained-scene proofs]({args.scene_verifications / 'results.json'})
- [All fifteen final contact sheets]({args.review / 'index.md'})
- [All 150 source-bound observations]({args.review / 'visual_inspection.json'})
- [Dataset export manifest]({args.dataset / 'manifest.json'})
- [New acceptance result]({proof['_acceptance_path']})
- [Final read-only marine check]({ROOT / live['result']['path']})

## Preservation and retained limits

Current preservation passed Pilot914, archive1, checkpoints2, M2 17, M3 27,
M4 55, M5 175 and M6 98 protected inventory entries, plus the two exact archived
M6 source copies. The inventory count-sum was 1289; these inventories can
overlap. All 1355 historically sealed incomplete-M7 output entries and all
119 sealed M8 output entries remained unchanged, including the historical
manifest bytes and disposition. The new completion seal inventoried
{inventory_count} unique current artifact paths. Original Kit logs could
continue appending; only verified fixed initial-prefix snapshots were sealed,
with subsequent appended bytes explicitly outside those snapshots.

The earlier M8 status `{preservation['historical_m8_status']}` remained the
historical disposition at its recorded time. Its reports and expansion
decision were not rewritten or silently promoted by this later M7 completion.

The animal still used a static upright mesh proxy and provisional engineering
behavior assumptions. Biological pose, dive pitch, body/rig animation,
breathing, anatomical water clearance and biological suitability were not
approved. Boxes remained direct **amodal evaluated-mesh projections**, not
exact visible or refracted outlines; machine rendered visibility remained
**unknown**. Underwater refraction and water optics remained uncalibrated.
Some paired background animals differed in RGB shading/detail; their cause
was unestablished. Matching physical identities did not certify pixel-identical
or photometrically equivalent backgrounds. Coarse GSD and overlay borders
limited anatomical inspection, and unlabelled background wildlife remained
outside the owned-target class scope.

Completion applied to this bounded engineering capture/review/export
milestone. Biological approval and inferred human M7 acceptance remained
false; no automatic approval for broader biological expansion or a scientific
behavior-conditioned study was created.
"""


def finalize(args):
    acceptance, live_path, active_log, snapshots = map(safe, (args.acceptance, args.final_live_check, args.active_log, args.runtime_log_snapshots))
    require(not REPORT.exists() and not MANIFEST.exists(), "New completion report and milestone7 seal must both be absent")
    require(acceptance.is_relative_to(HERE) and active_log.parent == HERE and active_log.suffix == ".log", "Use scoped new completion acceptance/active-log paths")
    pins = validation.Pins()
    pins.add(Path(__file__).resolve())
    proof, inputs, commands, executions = current_acceptance(pins, acceptance, args.execution_record)
    source_reports = [pins.load(safe(item["directory"]) / "results.json") for item in proof["source_attempts"]]
    require([row["passed"] for row in source_reports] == list(aggregate.SOURCE_STATUSES), "Selected source attempt statuses changed")
    last_capture = max(utc(row["finished_at_utc"]) for row in source_reports)
    live = final_live(pins, live_path, commands, last_capture)
    capture_records = capture_commands(pins)
    capture_client = pins.add(HERE / "capture_one_pending_snapshot.py", CAPTURE_CLIENT_SHA, 25514)
    for report in source_reports[2:]:
        require(len(report["runtime_code_before"]) == 32 and report["runtime_code_before"] == report["runtime_code_after"]
                and report["qa_helper_before"] == report["qa_helper_after"] == validation.capture.pin(capture_client), "Frozen32 capture pins or B634 client changed")
        validation.exact_rows(pins, report["runtime_code_before"])
    excluded_attempt_path = QA / "m7_live_01"
    excluded_attempt = pins.load(excluded_attempt_path / "results.json")
    excluded_groups = sum(group.get("passed") is True for run in excluded_attempt["runs"] for group in run["groups"])
    require(excluded_attempt.get("passed") is False and len(excluded_attempt["traceable_images"]) == 20 and excluded_groups == 2,
            "Earlier excluded failed attempt's original20-image history changed")
    tree(pins, excluded_attempt_path)
    old_attempt = {"directory": str(excluded_attempt_path.relative_to(ROOT)), "passed": False,
                   "result": validation.capture.pin(excluded_attempt_path / "results.json"), "images": 20, "groups": 2,
                   "selected_for_accepted_set": False, "error": excluded_attempt.get("error")}
    restart, stream_exclusions = restart_proofs(pins, snapshots)
    for source in proof["source_attempts"]:
        tree(pins, source["directory"])
    for directory in (inputs.campaign, inputs.scene_verifications, QA / "m7_live_02_visual_preview",
                      QA / "m7_supplement_01_visual_preview", inputs.review, inputs.dataset):
        tree(pins, directory)
    require(proof["dataset"]["inventory_files"] == 453, "Dataset artifact count is not the complete453 export")
    tree(pins, HERE, (active_log,))
    # Verify all current evidence before any completion artifact is written.
    before, _ = pins.finish()
    proof["_acceptance_path"] = str(acceptance)
    text = report_text(proof, inputs, old_attempt, live, restart, len(before) + 1)
    with REPORT.open("x") as stream:
        stream.write(text)
    pins.add(REPORT)
    rows, after = pins.finish()
    manifest = {"kind": "m7_engineering_completion_manifest", "milestone": 7, "status": "complete", "passed": True,
                "completed_at_utc": now(), "milestone_complete": True,
                "acceptance_scope": "Bounded engineering GAMA-driven capture/annotation test set, fresh retained-scene proof, actual source-bound presentation review and split export",
                "capture_counts": proof["capture_counts"], "actual_gama_trajectories": 5,
                "seeds": [1, 42, 184729, 20261008, 2147483647], "snapshot_steps": [8, 16, 32],
                "gsd_conditions_cm_px": [.5, 1, 2, 3, 4], "resolution_px": [1024, 768],
                "split_image_counts": {"train": 90, "validation": 30, "test": 30}, "source_attempts": proof["source_attempts"],
                "excluded_earlier_failed_attempt": old_attempt, "source_attempt_statuses": [False, False, True, True],
                "uninterrupted_successful_capture_claimed": False, "all_executed_commands_passed": False,
                "failed_attempts_preserved": True, "accepted_groups_recaptured_or_substituted": False,
                "frozen_single_state_client": validation.capture.pin(capture_client), "capture_protocol_pins_per_isolated_attempt": 32,
                "acceptance_result": validation.capture.pin(acceptance), "successful_acceptance_and_live_execution_records": executions,
                "capture_execution_records": capture_records, "final_live_check": live, "restart_proofs": restart,
                "restart_proved_permanent_gpu_memory_fix": False, "controller_animation_phase_preserved": False,
                "mutable_runtime_stream_exclusions": stream_exclusions,
                "runtime_fixed_prefix_snapshot_manifest": validation.capture.pin(snapshots / "manifest.json"),
                "fresh_independent_scene_proofs": proof["fresh_independent_scene_proofs"], "manual_review": proof["manual_review"],
                "dataset": proof["dataset"], "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
                "target_class_scope": "Class0 owned harbour porpoise only; demonstration wildlife unlabelled background",
                "pose_mapping": "static_pose_proxy_v1", "background_rgb_equivalence_claimed": False,
                "biological_approval": False, "human_approval_inferred": False, "detector_training_or_inference_run": False,
                "automatic_biological_expansion_approval": False, "sprint_acceptance_complete": False,
                "historical_preservation": {key:value for key,value in proof["historical_preservation"].items() if key != "current_original_preservation"},
                "historical_m8_status_retained": "complete_review_with_blocked_milestone_7",
                "report": validation.capture.pin(REPORT), "outputs": rows, "unique_output_paths": len(rows),
                "all_input_pins_current_and_unchanged": rows == after,
                "deferred_finalizer_stdout_log": str(active_log.relative_to(ROOT)),
                "seal_self_hash_deferred": True,
                "later_seal_check_required": "A separate retained command/log/execution record must verify every output and pin this manifest's own SHA256 plus this finalizer's completed stdout/execution.",
                "limitations": proof["limitations"]}
    require(len({row["path"] for row in rows}) == len(rows) and str(MANIFEST.relative_to(ROOT)) not in {row["path"] for row in rows}, "Seal inventory has duplicate paths or self-hash cycle")
    with MANIFEST.open("x") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    # This post-write check confirms content at finalization, but its output
    # cannot be included inside the already-created seal without a cycle.
    for row in manifest["outputs"]:
        require(validation.capture.pin(ROOT / row["path"]) == row, "Sealed artifact changed after manifest writing")
    return {"passed": True, "report": validation.capture.pin(REPORT), "manifest": validation.capture.pin(MANIFEST),
            "unique_output_paths": len(rows), "capture_counts": proof["capture_counts"],
            "separate_later_seal_check_still_required": True, "biological_approval": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance", required=True, type=Path)
    parser.add_argument("--final-live-check", required=True, type=Path)
    parser.add_argument("--runtime-log-snapshots", required=True, type=Path)
    parser.add_argument("--execution-record", required=True, action="append", type=Path)
    parser.add_argument("--active-log", required=True, type=Path,
                        help="This invocation's stdout log; deferred for the separate later seal-check record")
    args = parser.parse_args()
    result = finalize(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
