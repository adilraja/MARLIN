"""Copy the exact fifteen declared M7 groups from four immutable attempts.

The first two attempts failed after retaining twelve and one accepted groups.
The last two bounded single-state attempts must each have passed one remaining
group. Failed statuses and errors remain explicit. This command never renders,
recaptures accepted groups, changes runtime code or alters historical evidence.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "experiments/gama_marlin_v1/qa"
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))
import capture_gama_dataset_v2 as capture
import capture_gama_dataset_pending_v2 as pending
import aggregate_gama_dataset_v2 as original_aggregate

SOURCE_NAMES = ("m7_live_02", "m7_supplement_01", "m7_supplement_step_016", "m7_supplement_step_032")
SOURCE_STATUSES = (False, False, True, True)
SOURCE_GROUP_COUNTS = (12, 1, 1, 1)
MAX_RUN = pending.PENDING_RUN
live = capture.live


def require(condition, message):
    if not condition:
        raise ValueError(message)


def accepted_keys_for(index, declaration):
    if index == 0:
        return {(run["run_id"], state["step_index"]) for run in declaration["runs"] if run["run_id"] != MAX_RUN for state in run["selected_states"]}
    return {(MAX_RUN, (8, 16, 32)[index - 1])}


def select_sources(declaration, reports):
    """Pure exact selection for independent fail-injection tests.

    ``reports`` are the four source result objects in SOURCE_NAMES order.
    Return {(run_id, step_index): source_attempt_index}. Only passed completed
    groups may be selected. A failed source run can contain a passed group, but
    its attempt/run status must remain failed and its cleanup must pass.
    """
    require(len(reports) == 4, "Exactly four transparent source attempts required")
    runs = declaration["runs"]
    declared = {(run["run_id"], state["step_index"]): (run, state) for run in runs for state in run["selected_states"]}
    require(len(runs) == 5 and len(declared) == 15 and sum(len(run["selected_states"]) for run in runs) == 15,
            "Declaration must contain exactly five runs and fifteen distinct selected states")
    bindings = {}
    for index, report in enumerate(reports):
        require(report.get("passed") is SOURCE_STATUSES[index] and report.get("preflight_only") is False
                and report.get("biological_approval") is False, "Source attempt status/scope changed")
        if index:
            require(report.get("kind") == ("m7_pending_only_capture_attempt" if index == 1 else "m7_single_pending_snapshot_attempt"),
                    "Source attempt kind changed")
        if index >= 2:
            require(report.get("selected_step_index") == (16 if index == 2 else 32)
                    and report.get("source_trees_unchanged") is True and report.get("pending_plan_unchanged") is True,
                    "One-state continuation selected another snapshot or changed prior sources/plan")
        if index == 1:
            require(report.get("source_campaign_unchanged") is True and report.get("pending_plan_unchanged") is True,
                    "Failed supplement changed its original source/plan")
        if index:
            require(report.get("capture_counts") == {"target_present": 5, "target_absent": 5, "groups": 1}, "Continuation accepted-image counts changed")
        require(all(report.get(key) is True for key in ("runtime_code_unchanged", "declaration_unchanged"))
                and report.get("runtime_code_before") and report["runtime_code_before"] == report.get("runtime_code_after"),
                "Source runtime or declaration changed")
        require(index >= 2 or isinstance(report.get("error"), str) and report["error"].strip(), "Failed attempt error was omitted")
        require(index < 2 or not report.get("error"), "Passed one-state attempt retained an error")
        for phase in ("preservation_before", "preservation_after"):
            require(len(report.get(phase, [])) == 2 and all(row.get("passed") is True for row in report[phase]), "Source M5/M6 preservation failed")
        source_runs = report.get("runs", [])
        expected_runs = [row["run_id"] for row in runs] if index == 0 else [MAX_RUN]
        require([row.get("run_id") for row in source_runs] == expected_runs, "Source run identities/order changed")
        accepted, seen = set(), set()
        for source_run in source_runs:
            run = next(row for row in runs if row["run_id"] == source_run["run_id"])
            require(all(source_run.get(key) == run[key] for key in ("seed", "split", "encounter_group_id")), "Source trajectory/split/family changed")
            cleanup = source_run.get("cleanup_checks", {})
            require(cleanup and all(value is True for value in cleanup.values())
                    and not any(source_run.get(key) for key in ("cleanup_error", "cleanup_verification_error")), "Source run cleanup failed")
            expected_run_pass = not (source_run["run_id"] == MAX_RUN and index < 2)
            require(source_run.get("passed") is expected_run_pass, "Original source run status was rewritten")
            for group in source_run.get("groups", []):
                key = group.get("run_id"), group.get("step_index")
                require(key in declared and key not in seen and key[0] == source_run["run_id"], "Unknown/duplicate/misattributed source group")
                seen.add(key)
                expected_run, state = declared[key]
                require(group.get("source_state") == state and group.get("split") == expected_run["split"]
                        and group.get("encounter_group_id") == expected_run["encounter_group_id"], "Source state/split/family substitution")
                require(type(group.get("passed")) is bool, "Group acceptance must be explicit")
                if not group["passed"]:
                    require(index < 2 and not group.get("group_checks") and not group.get("retained_group"), "Failed group was presented as accepted captured evidence")
                    continue
                require(group.get("held_state") is True and group.get("retained_group") and group.get("coexistence_checks")
                        and all(value is True for value in group["coexistence_checks"].values())
                        and group.get("group_checks", {}).get("passed") is True
                        and group["group_checks"].get("capture_count") == 10, "Accepted source group did not pass state/coexistence checks")
                require(key not in bindings, "An accepted original group was duplicated or substituted")
                accepted.add(key)
                bindings[key] = index
        require(accepted == accepted_keys_for(index, declaration) and len(accepted) == SOURCE_GROUP_COUNTS[index], "Source attempt selected missing/extra/substituted accepted groups")
        images = report.get("traceable_images", [])
        expected_ids = {f"{run_id}__step_{step:03d}__{variant}__gsd_{gsd:g}" for run_id, step in accepted for variant in ("present", "absent") for gsd in capture.GSDS}
        require(len(images) == len(expected_ids) == 10 * SOURCE_GROUP_COUNTS[index]
                and {row.get("image_id") for row in images} == expected_ids, "Source image selection is missing/duplicate/extra")
        for image in images:
            run, state = declared[(image["run_id"], image["step_index"])]
            require(all(image.get(field) == run[field] for field in ("seed", "split", "encounter_group_id", "related_run_ids"))
                    and image.get("simulation_time_s") == state["simulation_time_s"]
                    and image.get("original_gama_depth_m") == state["agents"][0]["depth_m"]
                    and image.get("behavioural_state") == state["agents"][0]["behavioural_state"]
                    and image.get("target_present") is (image.get("variant") == "present")
                    and image.get("gsd_cm_px") in capture.GSDS, "Source image identity/presence/depth changed")
    require(set(bindings) == set(declared), "Accepted set lacks exact fifteen declared snapshot keys")
    require(all(reports[index].get("declaration") == reports[0].get("declaration") for index in range(4)), "Sources used differing capture declarations")
    return bindings


def check_source_files(directory, report, declaration, index):
    require(capture.pin(capture.DECLARATION) == report["declaration"]
            and live.digest(directory / "declaration.json") == report["declaration"]["sha256"], "Source declaration hash changed")
    current = {row["path"]: row for row in pending.supplement_code_pins()}
    for pin in report["runtime_code_before"]:
        path = live.safe_path(ROOT / pin["path"])
        require(capture.pin(path) == pin, "A source capture-code pin changed")
        if pin["path"] in current:
            require(pin == current[pin["path"]], "Frozen original protocol code differs")
    if index:
        sys.path.insert(0, str(HERE))
        import capture_one_pending_snapshot as single
        single.verified_source_attempt(directory, declaration, (8, 16, 32)[index - 1], SOURCE_STATUSES[index])
    if index == 1:
        require(report.get("source_campaign_unchanged") is True and report.get("pending_plan_unchanged") is True,
                "Failed supplement did not preserve the original source/plan")
        plan = pending.build_pending_plan(QA / SOURCE_NAMES[0], capture.DECLARATION)
        saved = json.loads((directory / "pending_plan.json").read_text())
        timestamp = saved.pop("saved_before_rendering_at_utc", None)
        require(isinstance(timestamp, str) and timestamp and saved == plan
                and capture.pin(directory / "pending_plan.json") == report["pending_plan"], "Failed supplement pre-render plan changed")
    if index >= 2:
        step = 16 if index == 2 else 32
        require(report.get("kind") == "m7_single_pending_snapshot_attempt" and report.get("selected_step_index") == step,
                "Require explicit one-state continuation provenance")
        plan = single.build_plan(step)
        saved = json.loads((directory / "pending_plan.json").read_text())
        timestamp = saved.pop("saved_before_acquire_and_rendering_at_utc", None)
        require(isinstance(timestamp, str) and timestamp and saved == plan
                and report["pending_plan"] == capture.pin(directory / "pending_plan.json")
                and report.get("pending_plan_unchanged") is True
                and report.get("source_trees_unchanged") is True
                and report["source_tree_pins_before"] == report["source_tree_pins_after"] == plan["source_tree_pins"]
                and report["source_attempts"] == plan["source_attempts"], "Continuation pre-render plan/source proofs changed")
        require(report["runtime_code_before"] == single.code_pins()
                and report["qa_helper_before"] == report["qa_helper_after"] == capture.pin(HERE / "capture_one_pending_snapshot.py")
                and report["frozen_capture_protocol_before"] == report["frozen_capture_protocol_after"] == pending.supplement_code_pins(),
                "Continuation helper or frozen protocol changed")
    for run in report["runs"]:
        declared_run = next(row for row in declaration["runs"] if row["run_id"] == run["run_id"])
        for group in run["groups"]:
            if not group["passed"]:
                continue
            state = next(row for row in declared_run["selected_states"] if row["step_index"] == group["step_index"])
            step = directory / "captures" / run["run_id"] / f"step_{state['step_index']:03d}"
            require(json.loads((step / "group_result.json").read_text()) == group, "Attempt's accepted group differs from its actual retained record")
            checks = capture.validate_group(step / "group", state, group["capture_response"])
            require(checks == group["group_checks"], "Repeated source group validation differs")
            rows = pending.image_rows(declared_run, state, checks, step / "group", directory)
            source_rows = [row for row in report["traceable_images"] if row["run_id"] == run["run_id"] and row["step_index"] == state["step_index"]]
            require(rows == source_rows, "Source image records differ from actual retained captures")


def build(output):
    output = live.safe_path(output)
    require(output.is_relative_to(QA) and not output.exists(), "Use a new exclusive aggregate inside sprint QA")
    directories = [QA / name for name in SOURCE_NAMES]
    require(not any(output.is_relative_to(path) or path.is_relative_to(output) for path in directories), "Aggregate must be separate from every source")
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "m7_accepted_capture_set_aggregate", "operation": "offline_readonly_source_copy", "milestone": 7,
              "passed": False, "preflight_only": False, "started_at_utc": pending.now(), "scene_mutation_attempted": False,
              "render_calls_made": 0, "uninterrupted_successful_capture_claimed": False, "biological_approval": False,
              "milestone_8_started": False, "runs": [], "traceable_images": [], "group_provenance": [],
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
              "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
              "independent_retained_usd_verification_required": True, "source_attempt_contract": list(SOURCE_NAMES),
              "continuation_note": "Two resource-limited failed attempts retained accepted groups; two subsequent isolated one-state attempts completed only missing states. Original statuses remain unchanged."}
    before_trees, seals, runtime, new_sources = None, [], None, None
    try:
        declaration = capture.validate_declaration(capture.DECLARATION)
        reports = [json.loads((path / "results.json").read_text()) for path in directories]
        bindings = select_sources(declaration, reports)
        for index, (path, original) in enumerate(zip(directories, reports)):
            check_source_files(path, original, declaration, index)
        before_trees = [pending.tree_pins(path) for path in directories]
        report["source_tree_pins_before"] = before_trees
        report["source_attempts"] = [{"directory": str(path), "result": capture.pin(path / "results.json"),
                                      "kind": original.get("kind"), "passed": original["passed"], "error": original.get("error"),
                                      "capture_counts": {"accepted_groups": SOURCE_GROUP_COUNTS[index], "images": len(original["traceable_images"])}}
                                     for index, (path, original) in enumerate(zip(directories, reports))]
        report["declaration"] = capture.pin(capture.DECLARATION)
        shutil.copyfile(capture.DECLARATION, output / "declaration.json")
        require(live.digest(output / "declaration.json") == report["declaration"]["sha256"], "Copied declaration differs")
        seals = [capture.load_seal(live.M5_MANIFEST), capture.load_seal(capture.M6_MANIFEST, capture.ALLOWED_M6_DELTAS)]
        report["preservation_before"] = [capture.verify_seal(seal) for seal in seals]
        require(all(row["passed"] for row in report["preservation_before"]), "Protected M5/M6 outputs changed")
        runtime = pending.supplement_code_pins()
        report["runtime_code_before"] = runtime
        new_sources = [capture.pin(Path(__file__).resolve())]
        report["offline_aggregate_sources_before"] = new_sources
        for run in declaration["runs"]:
            origins = sorted({bindings[(run["run_id"], state["step_index"])] for state in run["selected_states"]})
            source_runs = [(index, next(row for row in reports[index]["runs"] if row["run_id"] == run["run_id"])) for index in origins]
            combined = {key: run[key] for key in ("run_id", "seed", "split", "encounter_group_id")}
            combined.update(passed=True, groups=[], kind="accepted_source_group_set",
                            source_run_passed=all(row["passed"] for _, row in source_runs),
                            source_run_attempts=[{"directory": str(directories[index]), "passed": row["passed"],
                                                  "cleanup_checks": row["cleanup_checks"]} for index, row in source_runs],
                            cleanup_checks={key: all(row["cleanup_checks"].get(key) is True for _, row in source_runs)
                                            for key in source_runs[0][1]["cleanup_checks"]})
            report["runs"].append(combined)
            for state in run["selected_states"]:
                index = bindings[(run["run_id"], state["step_index"])]
                origin, source_report = directories[index], reports[index]
                source_run = next(row for row in source_report["runs"] if row["run_id"] == run["run_id"])
                original_result = next(row for row in source_run["groups"] if row["step_index"] == state["step_index"])
                relative = Path("captures") / run["run_id"] / f"step_{state['step_index']:03d}"
                source_step, target_step = origin / relative, output / relative
                copied = original_aggregate.copy_step(source_step, target_step)
                checks = capture.validate_group(target_step / "group", state, original_result["capture_response"])
                require(checks == original_result["group_checks"], "Byte-copied group validation differs")
                report["group_provenance"].append({"run_id": run["run_id"], "step_index": state["step_index"],
                    "source_attempt_index": index, "source_campaign": str(origin), "source_campaign_passed": source_report["passed"],
                    "source_run_passed": source_run["passed"], "source_group": str(source_step / "group"), "target_group": str(target_step / "group"),
                    "source_group_result": capture.pin(source_step / "group_result.json"),
                    "source_manifest_sha256": live.digest(source_step / "group/manifest.json"),
                    "target_manifest_sha256": live.digest(target_step / "group/manifest.json"),
                    "copied_files": copied, "all_copied_files_byte_identical": True})
                combined["groups"].append(original_result)
                rows = pending.image_rows(run, state, checks, target_step / "group", output)
                originals = pending.image_rows(run, state, checks, source_step / "group", origin)
                for row, original in zip(rows, originals):
                    row["copy_provenance"] = {"source_campaign": str(origin), "source_campaign_result": capture.pin(origin / "results.json"),
                        "source_campaign_passed": source_report["passed"], "source_attempt_index": index,
                        "source_group": str(source_step / "group"), "target_group": str(target_step / "group"),
                        "source_image_record": original,
                        "source_paths": {key: str(origin / original[key]) for key in ("rgb_file", "annotation_file", "yolo_file", "group_manifest")},
                        "all_output_hashes_match_source": True}
                    report["traceable_images"].append(row)
            live.write_json(output / "captures" / run["run_id"] / "run_result.json", combined)
        assignments = {}
        for run in declaration["runs"]:
            for related in run["related_run_ids"]:
                require(related not in assignments or assignments[related] == run["split"], "Related trajectories cross splits")
                assignments[related] = run["split"]
        images = report["traceable_images"]
        manifest = {"milestone": 7, "kind": "m7_aggregated_trajectory_split_manifest", "declaration": report["declaration"],
                    "split_policy": declaration["split_policy"],
                    "trajectory_assignments": [{key: run[key] for key in ("run_id", "related_run_ids", "encounter_group_id", "split")} for run in declaration["runs"]],
                    "related_run_split_assignments": assignments, "images": images,
                    "target_present_captures": 75, "target_absent_captures": 75, "related_trajectories_cross_splits": False,
                    "biological_approval": False, "annotation_semantics": report["annotation_semantics"], "rendered_visibility": "unknown",
                    "target_class_scope": report["annotation_scope"], "source_attempts": report["source_attempts"]}
        live.write_json(output / "trajectory_split_manifest.json", manifest)
        report["trajectory_split_manifest"] = {"path": "trajectory_split_manifest.json", "sha256": live.digest(output / "trajectory_split_manifest.json")}
        report["capture_counts"] = {"target_present": sum(row["target_present"] for row in images), "target_absent": sum(not row["target_present"] for row in images), "groups": len(bindings)}
        report["passed"] = (report["capture_counts"] == {"target_present": 75, "target_absent": 75, "groups": 15}
                            and len({row["image_id"] for row in images}) == len(images) == 150
                            and Counter(row["split"] for row in images) == Counter(train=90, validation=30, test=30))
    except BaseException as error:
        report.update(error=f"{type(error).__name__}: {error}", passed=False)
    finally:
        try:
            report["preservation_after"] = [capture.verify_seal(seal) for seal in seals]
            report["runtime_code_after"] = pending.supplement_code_pins() if runtime is not None else None
            report["runtime_code_unchanged"] = runtime is not None and report["runtime_code_after"] == runtime
            report["declaration_unchanged"] = report.get("declaration") == capture.pin(capture.DECLARATION)
            report["source_trees_unchanged"] = before_trees is not None and before_trees == [pending.tree_pins(path) for path in directories]
            report["offline_aggregate_sources_after"] = [capture.pin(Path(__file__).resolve())]
            report["offline_aggregate_sources_unchanged"] = new_sources is not None and report["offline_aggregate_sources_after"] == new_sources
            report["passed"] = (report["passed"] and report["runtime_code_unchanged"] and report["declaration_unchanged"]
                                and report["source_trees_unchanged"] and report["offline_aggregate_sources_unchanged"]
                                and all(row["passed"] for row in report["preservation_after"]))
        except BaseException as error:
            report.update(preservation_error=f"{type(error).__name__}: {error}", passed=False)
        report["finished_at_utc"] = pending.now()
        live.write_json(output / "results.json", report)
    require(report["passed"], report.get("error", report.get("preservation_error", "Aggregate did not pass")))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({"passed": result["passed"], "capture_counts": result["capture_counts"], "source_attempt_statuses": SOURCE_STATUSES, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
