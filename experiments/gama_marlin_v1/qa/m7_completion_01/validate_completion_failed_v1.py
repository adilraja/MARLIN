"""Independently bind completed M7 engineering artifacts without live calls.

This new post-M8 audit never edits old evidence. It checks retained JSON/PNG
bytes and actual command records; USD recomputation remains the separately
executed, unchanged fifteen-group verifier. Passing this audit does not grant
biological, optical, detector or human-review approval.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "experiments/gama_marlin_v1/qa"
HERE = Path(__file__).resolve().parent
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}
DECLARATION_SHA = "4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557"
PROGRESS_SHA = "a480bd2ac0624ab6cc8ff2d6873bb68c355f6a73f9adcb3ad66ec53e242635d9"
M8_SHA = "16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa"
USD_PYTHON = "/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(QA))
sys.path.insert(0, str(HERE))
import capture_gama_dataset_v2 as capture
import capture_gama_dataset_pending_v2 as pending
import build_m7_review as review_builder
import check_m7_preservation as protected
import check_m8_m7_progress_preservation as progress
import verify_m7_campaign_groups as verifier
import aggregate_capture_set as continuation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    require(not BLOCKED.intersection(path.parts) and path.suffix != ".pyc", "Generated input prohibited")
    resolved = path.resolve()
    require(not BLOCKED.intersection(resolved.parts) and resolved.suffix != ".pyc", "Generated resolved input prohibited")
    require(resolved.is_relative_to(ROOT), "Evidence must remain inside the repository")
    return resolved


def child(base, name):
    path = safe(base / name)
    require(path.is_relative_to(base), "Artifact escaped its declared evidence directory")
    return path


def digest(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Non-finite JSON number")
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


class Pins:
    def __init__(self):
        self.values = {}

    def add(self, path, expected=None, size=None):
        path = safe(path)
        require(path.is_file(), "Missing retained file: " + str(path))
        row = {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest(path)}
        require(expected is None or row["sha256"] == expected, "SHA mismatch: " + str(path))
        require(size is None or row["bytes"] == size, "Size mismatch: " + str(path))
        require(str(path) not in self.values or self.values[str(path)] == row, "Input changed during validation")
        self.values[str(path)] = row
        return path

    def load(self, path, expected=None):
        path = self.add(path, expected)
        value = json.loads(path.read_text(), object_pairs_hook=unique_object)
        finite(value)
        return value

    def row(self, row, base=ROOT):
        return self.add(base / row["path"], row["sha256"], row["bytes"])

    def tree(self, directory, expected=None):
        rows = pending.tree_pins(safe(directory))
        require(expected is None or rows == expected, "Retained source tree changed: " + str(directory))
        for row in rows:
            self.row(row)
        return rows

    def finish(self):
        before = sorted(self.values.values(), key=lambda row: row["path"])
        after = [{"path": row["path"], "bytes": (ROOT / row["path"]).stat().st_size,
                  "sha256": digest(ROOT / row["path"])} for row in before]
        require(before == after, "A retained input changed during acceptance validation")
        return before, after


def exact_rows(pins, rows, base=ROOT):
    require(isinstance(rows, list) and len({row["path"] for row in rows}) == len(rows), "Duplicate artifact inventory paths")
    for row in rows:
        pins.row(row, base)


def source_hashes(pins, hashes):
    if isinstance(hashes, list):
        exact_rows(pins, hashes)
    else:
        for path, sha in hashes.items():
            if isinstance(sha, dict):
                pins.add(Path(path) if Path(path).is_absolute() else ROOT / path, sha["sha256"], sha.get("bytes"))
            else:
                pins.add(Path(path) if Path(path).is_absolute() else ROOT / path, sha)


def command_records(value):
    if isinstance(value, dict):
        if "command" in value and "return_code" in value:
            yield value
        for key in ("execution", "executions", "commands"):
            if key in value:
                yield from command_records(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from command_records(item)


def check_command(pins, record):
    command = record.get("command")
    require(isinstance(command, list) and command and all(isinstance(v, str) for v in command), "Missing actual command vector")
    require(type(record.get("return_code")) is int and record["return_code"] == 0 and record.get("passed") is not False,
            "Command execution did not pass")
    require("-B" in command, "Retained Python command did not suppress generated bytecode")
    log = next((record[key] for key in ("log", "log_file", "actual_combined_stdout_stderr") if record.get(key)), None)
    require(log is not None and record.get("log_sha256"), "Command must retain its actual stdout/stderr log and SHA")
    path = Path(log) if Path(log).is_absolute() else ROOT / log
    pins.add(path, record["log_sha256"])
    for key in ("source_sha256", "source_pins_before", "source_pins_after"):
        if isinstance(record.get(key), (dict, list)):
            source_hashes(pins, record[key])
    if "source_pins_before" in record and "source_pins_after" in record:
        require(record["source_pins_before"] == record["source_pins_after"], "Command source pins changed")
    return command


def argument(command, key):
    require(command.count(key) == 1 and command.index(key) + 1 < len(command), "Missing unique command argument " + key)
    return safe(command[command.index(key) + 1])


def has_script(command, path):
    return any(arg.endswith(".py") and safe(arg) == path for arg in command)


def validate_attempts(pins, campaign, report, declaration):
    require(report.get("kind") == "m7_accepted_capture_set_aggregate" and report.get("operation") == "offline_readonly_source_copy",
            "Require the explicit offline accepted-source aggregate")
    require(report.get("render_calls_made") == 0 and report.get("scene_mutation_attempted") is False
            and report.get("uninterrupted_successful_capture_claimed") is False
            and report.get("source_trees_unchanged") is True, "Aggregate misstates capture/copy provenance")
    attempts = report["source_attempts"]
    require(len(attempts) == 4 and [row["passed"] for row in attempts] == list(continuation.SOURCE_STATUSES), "The two failed and two successful source statuses must be preserved")
    directories = [safe(row["directory"]) for row in attempts]
    require(directories == [QA / name for name in continuation.SOURCE_NAMES], "Unexpected approved source attempt origins")
    require(len(report["source_tree_pins_before"]) == 4, "Incomplete source tree provenance")
    attempt_reports = []
    for attempt, tree in zip(attempts, report["source_tree_pins_before"]):
        directory = safe(attempt["directory"])
        original = pins.load(directory / "results.json")
        require(capture.pin(directory / "results.json") == attempt["result"] and original["passed"] is attempt["passed"], "Original result/status changed")
        require(attempt.get("error") == original.get("error"), "Original attempt error was rewritten")
        pins.tree(directory, tree)
        attempt_reports.append(original)
    require([row["capture_counts"] for row in attempts] == [{"accepted_groups": n, "images": 10*n} for n in continuation.SOURCE_GROUP_COUNTS], "Expected 120 unchanged original and three exact ten-image continuations")
    bindings = continuation.select_sources(declaration, attempt_reports)
    for index, (directory, original) in enumerate(zip(directories, attempt_reports)):
        continuation.check_source_files(directory, original, declaration, index)
    require(report["runtime_code_before"] == report["runtime_code_after"] == pending.supplement_code_pins(), "Frozen protocol source changed")
    for row in report["runtime_code_before"]:
        pins.row(row)
    require(report.get("offline_aggregate_sources_unchanged") is True
            and report["offline_aggregate_sources_before"] == report["offline_aggregate_sources_after"] == [capture.pin(HERE / "aggregate_capture_set.py")],
            "New offline aggregate source pin changed")
    pins.row(report["offline_aggregate_sources_before"][0])
    provenance = {(row["run_id"], row["step_index"]): row for row in report["group_provenance"]}
    require(len(provenance) == len(report["group_provenance"]) == 15, "Missing/duplicate copied group provenance")
    copy_maps = {}
    for run in declaration["runs"]:
        accepted_run = next(row for row in report["runs"] if row["run_id"] == run["run_id"])
        origins = sorted({bindings[(run["run_id"], state["step_index"])] for state in run["selected_states"]})
        source_runs = [(i, next(row for row in attempt_reports[i]["runs"] if row["run_id"] == run["run_id"])) for i in origins]
        require(accepted_run["source_run_passed"] is all(row["passed"] for _, row in source_runs)
                and accepted_run["source_run_attempts"] == [{"directory": str(directories[i]), "passed": row["passed"], "cleanup_checks": row["cleanup_checks"]} for i,row in source_runs]
                and accepted_run["cleanup_checks"] == {key: all(row["cleanup_checks"].get(key) is True for _, row in source_runs) for key in source_runs[0][1]["cleanup_checks"]},
                "Original per-attempt run statuses/cleanup were rewritten")
        for state in run["selected_states"]:
            key = run["run_id"], state["step_index"]
            index = bindings[key]
            origin = directories[index]
            original_run = next(row for row in attempt_reports[index]["runs"] if row["run_id"] == run["run_id"])
            record = provenance[key]
            relative = Path("captures") / run["run_id"] / f"step_{state['step_index']:03d}"
            original_step, copied_step = origin / relative, campaign / relative
            require(safe(record["source_campaign"]) == origin and record["source_campaign_passed"] is attempt_reports[index]["passed"]
                    and record["source_attempt_index"] == index and record["source_run_passed"] is original_run["passed"]
                    and safe(record["source_group"]) == original_step / "group" and safe(record["target_group"]) == copied_step / "group"
                    and record["all_copied_files_byte_identical"] is True, "Group source-copy identity mismatch")
            original_result = pins.load(original_step / "group_result.json")
            require(original_result == pins.load(copied_step / "group_result.json")
                    == next(row for row in original_run["groups"] if row["step_index"] == state["step_index"])
                    == next(row for row in accepted_run["groups"] if row["step_index"] == state["step_index"]), "Original/copied/aggregate group records differ")
            require(record["source_group_result"] == capture.pin(original_step / "group_result.json"), "Original group-result pin changed")
            rows = record["copied_files"]
            require(len(rows) == len({row["relative_path"] for row in rows}) and rows, "Duplicate or empty group copy records")
            mappings = {}
            for row in rows:
                relative_file = Path(row["relative_path"])
                require(not relative_file.is_absolute() and ".." not in relative_file.parts
                        and row["byte_identical"] is True and row["source_sha256"] == row["target_sha256"], "Invalid byte-copy record")
                a, b = safe(row["source_path"]), safe(row["target_path"])
                require(a == original_step / relative_file and b == copied_step / relative_file, "Copy file escaped its exact source step")
                pins.add(a, row["source_sha256"], row["bytes"])
                pins.add(b, row["target_sha256"], row["bytes"])
                mappings[str(a)] = row
            expected_source = [{"path": str((original_step / row["relative_path"]).relative_to(ROOT)), "bytes": row["bytes"], "sha256": row["source_sha256"]} for row in rows]
            expected_target = [{"path": str((copied_step / row["relative_path"]).relative_to(ROOT)), "bytes": row["bytes"], "sha256": row["target_sha256"]} for row in rows]
            pins.tree(original_step, sorted(expected_source, key=lambda row: row["path"]))
            pins.tree(copied_step, sorted(expected_target, key=lambda row: row["path"]))
            require(record["source_manifest_sha256"] == record["target_manifest_sha256"], "Copied manifest differs")
            pins.add(copied_step / "group/manifest.json", record["target_manifest_sha256"])
            copy_maps[key] = mappings
    return provenance, copy_maps, attempt_reports


def validate_scene_proofs(pins, directory, campaign, declaration, report):
    summary = pins.load(directory / "results.json")
    require(summary.get("passed") is True and summary.get("expected_groups") == 15
            and safe(summary["campaign"]) == campaign and summary.get("pending_groups") == []
            and len(summary["groups"]) == 15, "Fresh copied-group verification did not complete")
    current_sources = {str(path.relative_to(ROOT)): digest(path) for path in verifier.PINNED_SOURCES}
    require(summary["source_sha256"] == current_sources, "Fresh proof helper sources differ")
    source_hashes(pins, current_sources)
    counts = Counter()
    max_projection = 0.0
    proofs, entries = {}, {}
    for row in summary["groups"]:
        key = row["run_id"], row["step_index"]
        require(key not in proofs and row.get("passed") is True, "Duplicate/failed fresh proof")
        result_path = child(directory, row["result"])
        proof = pins.load(result_path, row["result_sha256"])
        execution_path = child(directory, row["execution"])
        execution = pins.load(execution_path, row["execution_sha256"])
        group = campaign / "captures" / key[0] / f"step_{key[1]:03d}" / "group"
        require(proof.get("kind") == "m7_independent_retained_group_verification" and safe(proof["group"]) == group,
                "Fresh proof identifies another actual group")
        command = check_command(pins, execution)
        require(command == [USD_PYTHON, "-B", str(QA / "verify_m7_group.py"), "--group", str(group), "--output", str(result_path)]
                and execution.get("passed") is True and execution.get("source_and_retained_group_markers_unchanged") is True
                and execution.get("run_id") == key[0] and execution.get("step_index") == key[1]
                and execution["source_sha256"] == current_sources and execution["result_sha256"] == digest(result_path)
                and execution["capture_result_sha256"] == digest(group.parent / "group_result.json")
                and execution["capture_manifest_sha256"] == digest(group / "manifest.json"), "Actual USD invocation/result/log binding failed")
        entries[str(group)] = result_path, proof
        proofs[key] = proof
    require(set(proofs) == {(run["run_id"], state["step_index"]) for run in declaration["runs"] for state in run["selected_states"]}, "Fresh proofs differ from all15 declared groups")
    builder_pins = review_builder.InputPins()
    image_map = {row["image_id"]: row for row in report["traceable_images"]}
    original_reports = {safe(item["directory"]): pins.load(safe(item["directory"]) / "results.json") for item in report["source_attempts"]}
    for run in declaration["runs"]:
        for state in run["selected_states"]:
            key = run["run_id"], state["step_index"]
            group = campaign / "captures" / key[0] / f"step_{key[1]:03d}" / "group"
            entry = review_builder.load_group(group, declaration, builder_pins, entries, True)
            manifest, actual = entry["manifest"], entry["result"]
            counts["state_checks"] += len(manifest["state_checks"])
            counts["restoration_checks"] += len(manifest["restoration_checks"])
            counts["coexistence_checks"] += len(actual["coexistence_checks"])
            counts["settling_probes"] += sum(len(item["settling_probes"]) for item in manifest["captures"])
            rebuilt = pending.image_rows(run, state, actual["group_checks"], group, campaign)
            for rebuilt_row in rebuilt:
                image = image_map[rebuilt_row["image_id"]]
                require({k:v for k,v in image.items() if k != "copy_provenance"} == rebuilt_row, "Aggregate image record differs from its actual captured state")
                origin = image["copy_provenance"]
                origin_campaign, origin_group = safe(origin["source_campaign"]), safe(origin["source_group"])
                require(origin.get("all_output_hashes_match_source") is True and safe(origin["target_group"]) == group
                        and capture.pin(origin_campaign / "results.json") == origin["source_campaign_result"], "Image copy provenance changed")
                original_rows = pending.image_rows(run, state, actual["group_checks"], origin_group, origin_campaign)
                original_row = next(row for row in original_rows if row["image_id"] == image["image_id"])
                require(origin["source_image_record"] == original_row
                        == next(row for row in original_reports[origin_campaign]["traceable_images"] if row["image_id"] == image["image_id"])
                        and origin["source_paths"] == {field: str(origin_campaign / original_row[field]) for field in ("rgb_file", "annotation_file", "yolo_file", "group_manifest")}, "Copied image is not bound to the unchanged original record")
            for measured in proofs[key]["captures"]:
                require(measured["maximum_projection_matrix_error"] <= proofs[key]["tolerances"]["matrix_max_abs"], "Actual projection error exceeds the pinned tolerance")
                max_projection = max(max_projection, measured["maximum_projection_matrix_error"])
                counts["projections"] += 1
            for dependency in proofs[key]["dependency_checks"]:
                if dependency["status"] == "runtime_or_unresolved":
                    require(dependency["bytes_read"] is False, "Unresolved runtime bytes were inspected")
                    counts["unresolved_dependency_records"] += 1
                else:
                    require(dependency.get("content_verified") is True and dependency.get("bytes_read") is True
                            and dependency.get("expected_sha256") == dependency.get("before_sha256") == dependency.get("after_sha256"), "Local dependency proof failed")
                    pins.add(dependency["resolved_local_path"], dependency["expected_sha256"])
                    counts["local_dependency_checks"] += 1
    for row in builder_pins.finish():
        pins.add(row["path"], row["before_sha256"], row["bytes"])
    require(counts["projections"] == 150, "Require all150 actual USD projections")
    return {"groups": 15, **dict(counts), "maximum_projection_matrix_error": max_projection}


def validate_review(pins, folder, report, provenance, copy_maps):
    index = pins.load(folder / "visual_index.json")
    notes = pins.load(folder / "visual_inspection.json")
    complete = pins.load(folder / "review_complete_artifacts.json")
    require(complete.get("passed") is True, "Final review artifact inventory failed")
    exact_rows(pins, complete["files"])
    require(index.get("passed") is True and index.get("independent_scene_verifications_passed") is True
            and index.get("full_frames_uncropped") is True and index.get("all_retained_source_files_unchanged") is True
            and index.get("all_rgb_1024x768_decodable") is True and index.get("visual_inspection_completed") is False
            and index.get("biological_approval") is False and index.get("generator_sha256") == digest(QA / "build_m7_review.py")
            and len(index["images"]) == 150 and len(index["contact_sheets"]) == 15, "Final generated review scope changed")
    for flag in ("explicit_byte_copy_review_transfer_verified", "reviewed_preview_sheets_match_final_sheets", "source_rgb_annotation_yolo_hashes_verified", "source_inputs_unchanged", "engineering_review_metadata_binding_passed", "no_visibility_based_frame_dropping_or_reselection"):
        require(notes.get(flag) is True, "Final manual review lacks " + flag)
    require(notes.get("rendered_visibility") == "unknown" and notes.get("biological_approval") is False
            and notes.get("manual_observations_are_machine_visibility_labels") is False
            and notes.get("automatic_animal_visibility_threshold_used") is False
            and notes["source_attempts"] == report["source_attempts"], "Manual review altered labels or attempt status")
    generation = pins.load(folder / "generation_execution.json")
    command = check_command(pins, generation)
    require(generation.get("passed") is True and generation.get("source_inputs_unchanged") is True
            and argument(command, "--campaign") == safe(report["group_provenance"][0]["target_group"]).parents[3]
            and argument(command, "--output") == folder
            and str(QA / "build_m7_review.py") in command
            and str(HERE / "finalize_review.py") in generation["finalizer_command"], "Finalizer command binding failed")
    require(notes["visual_index_sha256"] == digest(folder / "visual_index.json"), "Manual notes identify another final index")
    views = {row["image_id"]: row for row in index["images"]}
    observations = {row["image_id"]: row for row in notes["observations"]}
    require(len(views) == len(observations) == len(notes["observations"]) == 150, "Manual review must cover150 unique actual views")
    require(set(views) == set(observations) == {row["image_id"] for row in report["traceable_images"]}, "Manual review IDs changed")
    sheets = {safe(row["file"]): row for row in index["contact_sheets"]}
    for path, row in sheets.items():
        pins.add(path, row["sha256"])
    require(len(notes["source_group_reviews"]) == 15, "Missing original source-group manual review")
    source_views = {}
    source_notes = {}
    for group in notes["source_group_reviews"]:
        key = group["run_id"], group["step_index"]
        source_group_note = pins.load(group["source_group_note"], group["source_group_note_sha256"])
        source_perview = pins.load(group["source_per_view_note"], group["source_per_view_note_sha256"])
        preview_folder = safe(group["source_group_note"]).parent
        source_index = pins.load(preview_folder / "visual_index.json")
        expected_preview = QA / ("m7_supplement_01_visual_preview" if key[0] == pending.PENDING_RUN else "m7_live_02_visual_preview") / f"{key[0]}__step_{key[1]:03d}"
        require(preview_folder == expected_preview and source_group_note["image_ids_reviewed"] == group["image_ids_reviewed"]
                == [row["image_id"] for row in source_index["images"]] == [row["image_id"] for row in source_perview["observations"]]
                and len(group["image_ids_reviewed"]) == 10 and group["engineering_observations"] == source_group_note["engineering_observations"]
                and group["copy_provenance"] == provenance[key], "Source-bound manual review/transfer changed")
        require(source_group_note["run_id"] == key[0] and source_group_note["step_index"] == key[1]
                and source_group_note["seed"] == group["seed"] and len(source_index["contact_sheets"]) == 1,
                "Original group manual notes identify another source state")
        require(source_group_note["visual_index_sha256"] == source_perview["visual_index_sha256"] == digest(preview_folder / "visual_index.json")
                and source_group_note["contact_sheet_sha256"] == source_perview["contact_sheet_sha256"] == group["reviewed_preview_sha256"], "Original inspected preview binding differs")
        pins.add(group["reviewed_preview"], group["reviewed_preview_sha256"])
        for row in source_perview["observations"]:
            require(row["image_id"] not in source_views, "Duplicate original manual observation")
            require(safe(row["contact_sheet"]) == safe(group["reviewed_preview"]) == safe(source_index["contact_sheets"][0]["file"])
                    and row["contact_sheet_sha256"] == group["reviewed_preview_sha256"] == source_index["contact_sheets"][0]["sha256"],
                    "Original per-view observation cites another inspected sheet")
            source_views[row["image_id"]] = row
            source_notes[row["image_id"]] = group
    for image in report["traceable_images"]:
        view, manual, original = views[image["image_id"]], observations[image["image_id"]], source_views[image["image_id"]]
        key = image["run_id"], image["step_index"]
        require(manual.get("physically_present") is image["target_present"] and manual.get("rendered_visibility") == "unknown"
                and manual.get("biological_approval") is False and manual.get("manual_observation_is_machine_visibility_label") is False
                and isinstance(manual.get("manual_contact_sheet_observation"), str) and manual["manual_contact_sheet_observation"].strip()
                and manual["manual_contact_sheet_observation"] == original["manual_contact_sheet_observation"], "Actual source observation was lost or converted to visibility approval")
        for field in ("run_id", "seed", "step_index", "gsd_cm_px", "variant"):
            require(manual[field] == view[field] == image[field] == original[field], "Review source identity differs")
        transfers = []
        for field, sha_key in (("rgb_file", "rgb_sha256"), ("annotation_file", "annotation_sha256"), ("yolo_file", "yolo_sha256")):
            target, origin = safe(view[field]), safe(original[field])
            require(target == safe(manual[field]) == safe(report["group_provenance"][0]["target_group"]).parents[3] / image[field]
                    and manual[sha_key] == view[sha_key] == image[sha_key] == original[sha_key], "Manual source bytes differ")
            pins.add(target, image[sha_key])
            pins.add(origin, image[sha_key])
            require(safe(manual["source_" + field]) == origin, "Manual source transfer path changed")
            transfers.append(copy_maps[key][str(origin)])
        require(manual["explicit_copy_transfer_provenance"] == transfers, "Manual file-copy transfer proof changed")
        require(safe(manual["source_review_note"]) == safe(source_notes[image["image_id"]]["source_per_view_note"])
                and manual["source_review_note_sha256"] == source_notes[image["image_id"]]["source_per_view_note_sha256"]
                and safe(manual["source_group_note"]) == safe(source_notes[image["image_id"]]["source_group_note"])
                and manual["source_group_note_sha256"] == source_notes[image["image_id"]]["source_group_note_sha256"], "Per-view source-note binding differs from group review")
        sheet = safe(manual["contact_sheet"])
        require(sheet == safe(view["contact_sheet"]) and sheet in sheets
                and manual["contact_sheet_sha256"] == sheets[sheet]["sha256"] == original["contact_sheet_sha256"]
                == manual["reviewed_preview_sha256"], "Final review sheet bytes differ from actual inspected preview")
        pins.add(manual["source_review_note"], manual["source_review_note_sha256"])
        pins.add(manual["source_group_note"], manual["source_group_note_sha256"])
    return {"sheets": 15, "actual_source_bound_observations": 150, "old_observations_preserved": 120, "supplemental_observations": 30,
            "final_sheets_byte_equal_to_inspected_original_previews": True,
            "generation_index_inspection_flag_retained_false": True}


def validate_export(pins, dataset, campaign, proof_dir, review_dir, report):
    manifest = pins.load(dataset / "manifest.json")
    require(manifest.get("kind") == "m7_engineering_dataset_export" and manifest.get("passed") is True
            and manifest.get("image_count") == 150 and manifest.get("target_present") == 75 and manifest.get("target_absent") == 75
            and manifest.get("split_image_counts") == {"train": 90, "validation": 30, "test": 30}
            and manifest.get("trajectory_families_cross_splits") is False and manifest.get("related_runs_cross_splits") is False
            and manifest.get("source_files_unchanged") is True and manifest.get("biological_approval") is False
            and manifest.get("rendered_visibility") == "unknown" and manifest.get("annotation_semantics") == "amodal_direct_evaluated_mesh_projection",
            "Export semantics/counts failed")
    for key, path in (("campaign_result", campaign / "results.json"), ("source_split_manifest", campaign / "trajectory_split_manifest.json"),
                      ("source_visual_review", review_dir / "visual_inspection.json"), ("exporter", ROOT / "tools/export_gama_dataset_v2.py")):
        require(manifest[key] == capture.pin(path), "Export source/code pin changed")
    proofs = [capture.pin(proof_dir / f"{run['run_id']}__step_{state['step_index']:03d}.json") for run in capture.validate_declaration(campaign / "declaration.json")["runs"] for state in run["selected_states"]]
    require(sorted(manifest["independent_group_verifications"], key=lambda row: row["path"]) == sorted(proofs, key=lambda row: row["path"]), "Export proof inventory changed")
    exact_rows(pins, manifest["outputs"], dataset)
    actual_tree = pins.tree(dataset)
    expected_tree = [{"path": str((dataset / row["path"]).relative_to(ROOT)), "bytes": row["bytes"], "sha256": row["sha256"]} for row in manifest["outputs"]] + [capture.pin(dataset / "manifest.json")]
    require(actual_tree == sorted(expected_tree, key=lambda row: row["path"]), "Export inventory omits/duplicates actual files")
    exported = {row["image_id"]: row for row in manifest["images"]}
    require(len(exported) == len(manifest["images"]) == 150, "Export image IDs duplicated/missing")
    for image in report["traceable_images"]:
        expected = dict(image)
        for field, folder, suffix, sha in (("rgb_file", "images", ".png", "rgb_sha256"), ("yolo_file", "labels", ".txt", "yolo_sha256"), ("annotation_file", "annotations", ".json", "annotation_sha256")):
            expected["source_" + field] = str((campaign / image[field]).relative_to(ROOT))
            expected[field] = f"{folder}/{image['split']}/{image['image_id']}{suffix}"
            pins.add(child(dataset, expected[field]), image[sha])
        require(exported[image["image_id"]] == expected, "Export row differs from source-byte provenance")
    pins.add(dataset / "visual_review.json", digest(review_dir / "visual_inspection.json"))
    expected_yaml = "# Provisional M7 engineering test set; direct amodal boxes, no visible/refraction masks.\npath: " + json.dumps(str(dataset)) + "\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n  0: harbour_porpoise\n"
    require((dataset / "data.yaml").read_text() == expected_yaml, "Dataset descriptor changed class/split/root semantics")
    return {"images": 150, "byte_identical_png_label_annotation_copies": 450, "target_present": 75, "target_absent": 75,
            "split_image_counts": manifest["split_image_counts"], "inventory_files": len(manifest["outputs"])}


def validate_history(pins, preservation_path, history_path):
    retained = pins.load(preservation_path)
    actual = protected.audit()
    require(retained.get("passed") is True and actual.get("passed") is True
            and retained["checker_sha256"] == actual["checker_sha256"] and retained["helper_sha256"] == actual["helper_sha256"]
            and retained["preservation"] == actual["preservation"]
            and retained["historical_manifest_checks"] == actual["historical_manifest_checks"]
            and retained["historical_m6_source_checks"] == actual["historical_m6_source_checks"], "New retained preservation proof no longer matches actual protected outputs")
    require({name: row["protected_files_checked"] for name,row in actual["preservation"].items()} == protected.EXPECTED_PROTECTED_COUNTS,
            "Historical protected counts changed")
    original_progress = pins.load(QA / "m7_progress_manifest.json", PROGRESS_SHA)
    exact_rows(pins, original_progress["outputs"])
    old_report = pins.load(history_path)
    current_progress = progress.audit()
    require(old_report.get("passed") is True and current_progress.get("passed") is True and old_report["outputs_checked"] == 1355
            and old_report["manifest_before"] == current_progress["manifest_before"]
            and old_report["retained_m7_status"] == current_progress["retained_m7_status"]
            and old_report["source_pins_before"] == old_report["source_pins_after"] == current_progress["source_pins_before"], "Historical incomplete120 progress proof changed")
    m8 = pins.load(QA / "milestone_8_manifest.json", M8_SHA)
    require(m8.get("status") == "complete_review_with_blocked_milestone_7" and m8.get("passed") is True
            and m8.get("milestone_7_complete") is False and m8.get("sprint_acceptance_complete") is False
            and m8.get("biological_approval") is False and len(m8["outputs"]) == 119, "Sealed M8 historical disposition changed")
    exact_rows(pins, m8["outputs"])
    for row in actual["historical_manifest_checks"]:
        pins.add(ROOT / row["path"], row["actual_sha256"], row["bytes"])
    # The fresh older checker verifies allowed source deltas separately. Pin
    # their current bytes as well, so every checked old inventory also has a
    # before/after observation in this new command's own input registry.
    for number in (2, 3, 4, 5, 6):
        document = pins.load(QA / f"milestone_{number}_manifest.json")
        for row in document["outputs"]:
            pins.add(ROOT / row["path"])
    baseline = pins.load(QA / "preserved_output_manifest.json")
    for row in baseline["files"] + [baseline["archive"]]:
        pins.add(ROOT / row["path"])
    for name in ("original", "backup"):
        pins.add(ROOT / baseline["checkpoint"][name], baseline["checkpoint"]["sha256"], baseline["checkpoint"]["bytes"])
    for row in actual["historical_m6_source_checks"]:
        pins.add(ROOT / row["retained_source"], row["original_m6_sha256"])
    return {"protected_counts": protected.EXPECTED_PROTECTED_COUNTS, "protected_inventory_count_sum": 1289,
            "original_m6_source_copies": 2, "sealed_incomplete_m7_outputs": 1355, "sealed_m8_outputs": 119,
            "historical_m7_progress_status": original_progress["status"], "historical_m8_status": m8["status"],
            "historical_records_unchanged": True, "current_original_preservation": actual}


def validate(args, pins):
    campaign, proof_dir, review_dir, dataset = map(safe, (args.campaign, args.scene_verifications, args.review, args.dataset))
    builder_pins = review_builder.InputPins()
    report = pins.load(campaign / "results.json")
    declaration, images, groups = review_builder.check_campaign(campaign, builder_pins)
    require(images == report["traceable_images"], "Strict review campaign loader returned different accepted images")
    for row in builder_pins.finish():
        pins.add(row["path"], row["before_sha256"], row["bytes"])
    require(digest(campaign / "declaration.json") == digest(capture.DECLARATION) == DECLARATION_SHA, "Original pre-capture declaration changed")
    pins.add(capture.DECLARATION, DECLARATION_SHA)
    require(Counter(row["split"] for row in report["traceable_images"]) == Counter(train=90, validation=30, test=30), "Declared90/30/30 image split failed")
    provenance, copy_maps, attempts = validate_attempts(pins, campaign, report, declaration)
    commands = []
    for path in args.execution_record:
        container = pins.load(path)
        require(container.get("passed") is not False, "Completion command wrapper failed")
        records = list(command_records(container))
        require(records, "No actual command executions in supplied record")
        commands.extend(check_command(pins, row) for row in records)
    aggregate_commands = [cmd for cmd in commands if has_script(cmd, HERE / "aggregate_capture_set.py")]
    export_commands = [cmd for cmd in commands if has_script(cmd, ROOT / "tools/export_gama_dataset_v2.py")]
    require(len(aggregate_commands) == len(export_commands) == 1, "Exactly one successful aggregate and export invocation required")
    require(argument(aggregate_commands[0], "--output") == campaign, "Aggregate invocation used another accepted-set output")
    require(argument(export_commands[0], "--campaign") == campaign and argument(export_commands[0], "--scene-verifications") == proof_dir
            and argument(export_commands[0], "--visual-review") == review_dir / "visual_inspection.json"
            and argument(export_commands[0], "--output") == dataset, "Export invocation used another accepted source")
    scene = validate_scene_proofs(pins, proof_dir, campaign, declaration, report)
    review = validate_review(pins, review_dir, report, provenance, copy_maps)
    exported = validate_export(pins, dataset, campaign, proof_dir, review_dir, report)
    history = validate_history(pins, safe(args.preservation), safe(args.history_preservation))
    return {"capture_counts": {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15},
            "source_attempts": report["source_attempts"], "fresh_independent_scene_proofs": scene, "manual_review": review,
            "dataset": exported, "historical_preservation": history,
            "aggregate_command": aggregate_commands[0], "export_command": export_commands[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("campaign", "scene-verifications", "review", "dataset", "preservation", "history-preservation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--execution-record", type=Path, action="append", required=True)
    args = parser.parse_args()
    output = safe(args.output)
    require(output.is_relative_to(HERE) and output.suffix == ".json" and not output.exists(), "Choose an exclusive new completion01 JSON result")
    require(output.parent.is_dir(), "Output parent must already exist")
    pins = Pins()
    for path in (Path(__file__).resolve(), ROOT / "tools/aggregate_gama_dataset_v2.py", ROOT / "tools/export_gama_dataset_v2.py",
                 ROOT / "tools/capture_gama_dataset_pending_v2.py", ROOT / "tools/capture_gama_dataset_v2.py",
                 QA / "build_m7_review.py", QA / "finalize_m7_review.py", QA / "check_m7_preservation.py", QA / "check_m8_m7_progress_preservation.py"):
        pins.add(path)
    for path in (HERE / "aggregate_capture_set.py", HERE / "finalize_review.py", HERE / "capture_one_pending_snapshot.py"):
        pins.add(path)
    result = {"kind": "m7_post_m8_completion_artifact_validation", "milestone": 7, "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "live_calls_made": False, "render_calls_made": 0,
              "detector_training_or_inference_run": False, "biological_approval": False, "human_approval_inferred": False,
              "uninterrupted_successful_capture_claimed": False,
              "acceptance_scope": "Retained engineering artifacts, independent scene proofs, actual-source-bound manual observations and byte-identical split export",
              "limitations": ["Static upright pose proxy; biological behavior, animation, breathing and anatomical water clearance remain unapproved.",
                              "Direct amodal mesh boxes; rendered visibility and visible/refraction masks remain unknown.",
                              "Only owned harbour porpoise class0; demonstration wildlife remains unlabelled background.",
                              "Some paired backgrounds differ in RGB shading/detail; cause unestablished, no photometric or bitwise RGB-equivalence claim.",
                              "External runtime/unresolved shader dependencies are retained explicitly and their bytes are not inspected.",
                              "No new detector result or statistical generalization claim; historical M8 review remains immutable."]}
    clock = time.monotonic()
    try:
        result.update(validate(args, pins))
        before, after = pins.finish()
        result.update(input_pins_before=before, input_pins_after=after, all_inputs_unchanged=True, passed=True)
    except Exception as error:
        result.update(error=f"{type(error).__name__}: {error}", observed_input_pins=sorted(pins.values.values(), key=lambda row: row["path"]))
    result.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), duration_seconds=time.monotonic() - clock)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "capture_counts": result.get("capture_counts"), "output": str(output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
