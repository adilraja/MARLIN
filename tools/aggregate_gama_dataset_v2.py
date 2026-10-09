"""Assemble a complete M7 capture set from immutable accepted source groups.

This is an offline, read-only operation on the two capture attempts. It creates
byte-identical copies in a new directory, preserving both attempt statuses and
the origin/hash of every copied file. It never renders or substitutes images.
Fresh independent USD verification of the copied groups remains necessary.
"""
import argparse
import json
from pathlib import Path
import shutil

import capture_gama_dataset_pending_v2 as pending

capture, live = pending.capture, pending.live


def copy_step(source, target, copier=shutil.copyfile):
    """Exclusive byte copy with injectable copier and before/after source pins."""
    if Path(source).is_symlink() or Path(target).is_symlink():
        raise ValueError("Source/target directory symlinks are unsupported")
    source, target = map(live.safe_path, (source, target))
    if target.exists() or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("Copy requires a new separate destination; evidence is never overwritten")
    if not source.is_dir():
        raise ValueError("Copy source step does not exist")
    before = pending.tree_pins(source)
    if not before:
        raise ValueError("An empty source step is not capture evidence")
    target.mkdir(parents=True, exist_ok=False)
    rows = []
    for pin in before:
        original = capture.ROOT / pin["path"]
        relative = original.relative_to(source)
        copied = target / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        if capture.pin(original) != pin:
            raise ValueError("Source changed before its byte copy")
        copier(original, copied)
        if (capture.pin(original) != pin or copied.stat().st_size != pin["bytes"]
                or live.digest(copied) != pin["sha256"]):
            raise ValueError("Source or copied bytes changed during copy; failed evidence remains retained")
        rows.append({"source_path": str(original), "target_path": str(copied),
                     "relative_path": str(relative), "bytes": pin["bytes"],
                     "source_sha256": pin["sha256"], "target_sha256": live.digest(copied), "byte_identical": True})
    if pending.tree_pins(source) != before:
        raise ValueError("Source tree changed during byte copy")
    return rows


def validate_supplement(report, plan):
    """Require the exact saved pending workload and three accepted test groups."""
    required_true = ("passed", "runtime_code_unchanged", "declaration_unchanged", "source_campaign_unchanged", "pending_plan_unchanged")
    if (report.get("kind") != "m7_pending_only_capture_attempt" or report.get("preflight_only") is not False
            or report.get("biological_approval") is not False or any(report.get(key) is not True for key in required_true)
            or report.get("capture_counts") != {"target_present": 15, "target_absent": 15, "groups": 3}
            or report.get("declaration") != plan["declaration"]
            or report.get("runtime_code_before") != report.get("runtime_code_after")):
        raise ValueError("Require a successful unchanged pending-only supplement")
    for phase in ("preservation_before", "preservation_after"):
        rows = report.get(phase, [])
        if len(rows) != 2 or any(row.get("passed") is not True for row in rows):
            raise ValueError("Supplement M5/M6 preservation checks did not pass")
    runs = report.get("runs", [])
    if len(runs) != 1 or runs[0].get("run_id") != pending.PENDING_RUN or runs[0].get("passed") is not True:
        raise ValueError("Supplement changed the pending trajectory or run status")
    run = runs[0]
    if (run.get("seed") != 2147483647 or run.get("split") != "test"
            or run.get("encounter_group_id") != "gama_engineering_porpoise_seed_2147483647"
            or not run.get("cleanup_checks") or any(value is not True for value in run["cleanup_checks"].values())
            or run.get("error") or run.get("cleanup_error") or run.get("cleanup_verification_error")):
        raise ValueError("Supplement source identity or cleanup evidence failed")
    wanted = [(row["run_id"], row["step_index"]) for row in plan["pending_groups"]]
    groups = run.get("groups", [])
    if [(row.get("run_id"), row.get("step_index")) for row in groups] != wanted:
        raise ValueError("Missing, duplicate or substituted pending capture groups")
    for group, selected in zip(groups, plan["pending_groups"]):
        if (group.get("passed") is not True or group.get("held_state") is not True
                or group.get("source_state") != selected["source_state"] or group.get("split") != "test"
                or group.get("encounter_group_id") != run["encounter_group_id"]
                or not group.get("retained_group") or not group.get("coexistence_checks")
                or any(value is not True for value in group["coexistence_checks"].values())):
            raise ValueError("Pending group changed source, split, held state or original scene")
    images = report.get("traceable_images", [])
    if len(images) != 30 or len({row.get("image_id") for row in images}) != 30:
        raise ValueError("Pending supplement lacks exactly thirty distinct images")
    return groups


def aggregate(source, supplement, output, declaration_path=capture.DECLARATION):
    source, supplement, output, declaration_path = map(live.safe_path, (source, supplement, output, declaration_path))
    if any(output.is_relative_to(path) or path.is_relative_to(output) for path in (source, supplement)):
        raise ValueError("Aggregate must be separate from both immutable source attempts")
    if source == supplement:
        raise ValueError("Source attempt and supplement must be distinct")
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "m7_accepted_capture_set_aggregate", "operation": "offline_readonly_source_copy",
              "milestone": 7, "passed": False, "preflight_only": False, "started_at_utc": pending.now(),
              "scene_mutation_attempted": False, "render_calls_made": 0,
              "uninterrupted_successful_capture_claimed": False, "biological_approval": False,
              "milestone_8_started": False, "runs": [], "traceable_images": [], "group_provenance": [],
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
              "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
              "independent_retained_usd_verification_required": True}
    seals, code_pins, before_trees = [], None, None
    try:
        plan = pending.build_pending_plan(source, declaration_path)
        declaration = capture.validate_declaration(declaration_path)
        supplement_report = json.loads((supplement / "results.json").read_text())
        supplemental_groups = validate_supplement(supplement_report, plan)
        saved_path = supplement / "pending_plan.json"
        saved_plan = json.loads(saved_path.read_text())
        saved_at = saved_plan.pop("saved_before_rendering_at_utc", None)
        if (not isinstance(saved_at, str) or not saved_at or saved_plan != plan
                or capture.pin(saved_path) != supplement_report["pending_plan"]
                or supplement_report["runtime_code_before"] != pending.supplement_code_pins()):
            raise ValueError("Supplement did not use the saved pre-render plan and frozen helpers")
        source_report = json.loads((source / "results.json").read_text())
        report["source_attempts"] = [{"directory": str(path), "result": capture.pin(path / "results.json"),
                                     "passed": record["passed"], "error": record.get("error"),
                                     "capture_counts": {"accepted_groups": sum(group["passed"] for run in record["runs"] for group in run["groups"]),
                                                        "images": len(record["traceable_images"])}}
                                    for path, record in ((source, source_report), (supplement, supplement_report))]
        before_trees = [pending.tree_pins(path) for path in (source, supplement)]
        report["source_tree_pins_before"] = before_trees
        report["declaration"] = plan["declaration"]
        shutil.copyfile(declaration_path, output / "declaration.json")
        if live.digest(output / "declaration.json") != plan["declaration"]["sha256"]:
            raise ValueError("Aggregate declaration copy changed")
        seals = [capture.load_seal(live.M5_MANIFEST), capture.load_seal(capture.M6_MANIFEST, capture.ALLOWED_M6_DELTAS)]
        report["preservation_before"] = [capture.verify_seal(seal) for seal in seals]
        if not all(row["passed"] for row in report["preservation_before"]):
            raise ValueError("Protected M5/M6 evidence changed before aggregation")
        code_pins = pending.supplement_code_pins()
        report["runtime_code_before"] = code_pins
        bindings = {(row["run_id"], row["step_index"]): source for row in plan["accepted_source_groups"]}
        for row in supplemental_groups:
            key = (row["run_id"], row["step_index"])
            if key in bindings:
                raise ValueError("A supplement replaced an accepted original capture group")
            bindings[key] = supplement
        if len(bindings) != 15:
            raise ValueError("Aggregate requires exactly fifteen accepted declared groups")
        for run in declaration["runs"]:
            attempt = source_report if run["run_id"] != pending.PENDING_RUN else supplement_report
            source_run = next(row for row in attempt["runs"] if row["run_id"] == run["run_id"])
            aggregated_run = {key: run[key] for key in ("run_id", "seed", "split", "encounter_group_id")}
            aggregated_run.update(passed=True, groups=[], kind="accepted_source_group_set",
                                  source_run_passed=source_run["passed"], cleanup_checks=source_run["cleanup_checks"])
            report["runs"].append(aggregated_run)
            for state in run["selected_states"]:
                origin = bindings[(run["run_id"], state["step_index"])]
                relative = Path("captures") / run["run_id"] / f"step_{state['step_index']:03d}"
                original, target = origin / relative, output / relative
                original_result = json.loads((original / "group_result.json").read_text())
                declared_result = next(row for row in source_run["groups"] if row["step_index"] == state["step_index"])
                if original_result != declared_result:
                    raise ValueError("Source group result differs from its immutable capture attempt")
                source_checks = capture.validate_group(original / "group", state, original_result["capture_response"])
                if source_checks != original_result["group_checks"]:
                    raise ValueError("Source checks differ before aggregate copying")
                copied = copy_step(original, target)
                provenance = {"run_id": run["run_id"], "step_index": state["step_index"],
                              "source_campaign": str(origin), "source_campaign_passed": attempt["passed"],
                              "source_group": str(original / "group"), "target_group": str(target / "group"),
                              "source_group_result": capture.pin(original / "group_result.json"),
                              "source_manifest_sha256": live.digest(original / "group/manifest.json"),
                              "target_manifest_sha256": live.digest(target / "group/manifest.json"),
                              "copied_files": copied, "all_copied_files_byte_identical": True}
                report["group_provenance"].append(provenance)
                copied_checks = capture.validate_group(target / "group", state, original_result["capture_response"])
                if copied_checks != source_checks:
                    raise ValueError("Copied group validation differs from the immutable source")
                aggregated_run["groups"].append(original_result)
                rows = pending.image_rows(run, state, copied_checks, target / "group", output)
                original_rows = pending.image_rows(run, state, source_checks, original / "group", origin)
                source_rows = [row for row in attempt["traceable_images"] if row["run_id"] == run["run_id"] and row["step_index"] == state["step_index"]]
                if original_rows != source_rows:
                    raise ValueError("Source attempt image records do not match the copied actual group")
                for row, original_row in zip(rows, original_rows):
                    row["copy_provenance"] = {"source_campaign": str(origin), "source_campaign_result": capture.pin(origin / "results.json"),
                                              "source_group": str(original / "group"), "target_group": str(target / "group"),
                                              "source_image_record": original_row,
                                              "source_paths": {key: str(origin / original_row[key]) for key in ("rgb_file", "annotation_file", "yolo_file", "group_manifest")},
                                              "all_output_hashes_match_source": True}
                    report["traceable_images"].append(row)
            live.write_json(output / "captures" / run["run_id"] / "run_result.json", aggregated_run)
        images = report["traceable_images"]
        assignments = {}
        for run in declaration["runs"]:
            for related in run["related_run_ids"]:
                if related in assignments and assignments[related] != run["split"]:
                    raise ValueError("Related source trajectories cross declared splits")
                assignments[related] = run["split"]
        present = sum(row["target_present"] for row in images)
        manifest = {"milestone": 7, "kind": "m7_aggregated_trajectory_split_manifest", "declaration": plan["declaration"],
                    "split_policy": declaration["split_policy"],
                    "trajectory_assignments": [{key: run[key] for key in ("run_id", "related_run_ids", "encounter_group_id", "split")} for run in declaration["runs"]],
                    "related_run_split_assignments": assignments, "images": images,
                    "target_present_captures": present, "target_absent_captures": len(images) - present,
                    "related_trajectories_cross_splits": False, "biological_approval": False,
                    "annotation_semantics": report["annotation_semantics"], "rendered_visibility": "unknown",
                    "target_class_scope": report["annotation_scope"], "source_attempts": report["source_attempts"]}
        live.write_json(output / "trajectory_split_manifest.json", manifest)
        report["trajectory_split_manifest"] = {"path": "trajectory_split_manifest.json", "sha256": live.digest(output / "trajectory_split_manifest.json")}
        report["capture_counts"] = {"target_present": present, "target_absent": len(images) - present, "groups": len(bindings)}
        report["passed"] = report["capture_counts"] == {"target_present": 75, "target_absent": 75, "groups": 15} and len({row["image_id"] for row in images}) == 150
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        report["passed"] = False
    finally:
        try:
            report["preservation_after"] = [capture.verify_seal(seal) for seal in seals]
            report["runtime_code_after"] = pending.supplement_code_pins() if code_pins is not None else None
            report["runtime_code_unchanged"] = code_pins is not None and report["runtime_code_after"] == code_pins
            report["declaration_unchanged"] = report.get("declaration") == capture.pin(declaration_path)
            report["source_trees_unchanged"] = before_trees is not None and before_trees == [pending.tree_pins(path) for path in (source, supplement)]
            report["passed"] = (report["passed"] and report["runtime_code_unchanged"] and report["declaration_unchanged"]
                                and report["source_trees_unchanged"] and all(row["passed"] for row in report["preservation_after"]))
        except BaseException as error:
            report["preservation_error"] = f"{type(error).__name__}: {error}"
            report["passed"] = False
        report["finished_at_utc"] = pending.now()
        live.write_json(output / "results.json", report)
    if not report["passed"]:
        raise ValueError(report.get("error", report.get("preservation_error", "Aggregate preservation failed")))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-campaign", type=Path, default=pending.DEFAULT_SOURCE)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--declaration", type=Path, default=capture.DECLARATION)
    args = parser.parse_args()
    report = aggregate(args.source_campaign, args.supplement, args.output, args.declaration)
    print(json.dumps({"passed": report["passed"], "kind": report["kind"], "capture_counts": report["capture_counts"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
