"""Independent offline failure checks for new four-attempt M7 source selection.

Fixtures copy actual retained metadata into memory. Two synthetic final-attempt
objects exercise selection only: they are never saved as capture evidence and
do not claim rendered images. No HTTP, Kit, USD rendering or source edits occur.
"""
from copy import deepcopy
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QA = HERE.parent
AGGREGATOR = HERE / "aggregate_capture_set.py"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "review_selection_tests_result.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != HERE or output.suffix != ".json":
        raise ValueError("Use a separate result inside the completion review directory")
    if output.exists():
        raise ValueError("Review results must never overwrite prior evidence")
    paths = [Path(__file__), AGGREGATOR,
             ROOT / "experiments/gama_marlin_v1/m7_capture_declaration.json",
             QA / "m7_live_02/results.json", QA / "m7_supplement_01/results.json",
             HERE / "finalize_review.py", HERE / "validate_completion.py",
             HERE / "capture_one_pending_snapshot.py", HERE / "verify_aggregate_groups.py"]
    before = {str(path): digest(path) for path in paths}
    for path in paths:
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    specification = importlib.util.spec_from_file_location("_new_aggregate_selection_review", AGGREGATOR)
    aggregate = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(aggregate)
    declaration = load(paths[2])
    original, partial = load(paths[3]), load(paths[4])
    run = declaration["runs"][-1]
    prototype_run = partial["runs"][0]
    prototype_group = prototype_run["groups"][0]
    reports = [original, partial]
    for step in (16, 32):
        state = next(row for row in run["selected_states"] if row["step_index"] == step)
        attempt = deepcopy(partial)
        attempt.update(passed=True, error=None, kind="m7_single_pending_snapshot_attempt",
                       selected_step_index=step, source_trees_unchanged=True, pending_plan_unchanged=True)
        selected_run = deepcopy(prototype_run)
        selected_run.update(passed=True, error=None)
        group = deepcopy(prototype_group)
        group.update(step_index=step, source_state=deepcopy(state))
        selected_run["groups"] = [group]
        attempt["runs"] = [selected_run]
        images = deepcopy(partial["traceable_images"])
        for image in images:
            image.update(step_index=step, simulation_time_s=state["simulation_time_s"],
                         original_gama_depth_m=state["agents"][0]["depth_m"],
                         behavioural_state=state["agents"][0]["behavioural_state"])
            image["image_id"] = f"{run['run_id']}__step_{step:03d}__{image['variant']}__gsd_{image['gsd_cm_px']:g}"
        attempt["traceable_images"] = images
        reports.append(attempt)
    cases = []
    baseline = aggregate.select_sources(declaration, reports)
    cases.append({"name": "exact_four_attempt_selection",
                  "passed": len(baseline) == 15 and baseline[(run["run_id"], 8)] == 1
                  and baseline[(run["run_id"], 16)] == 2 and baseline[(run["run_id"], 32)] == 3})

    def rejected(name, mutate):
        values = deepcopy(reports)
        mutate(values)
        try:
            aggregate.select_sources(declaration, values)
        except (ValueError, KeyError) as error:
            cases.append({"name": name, "passed": True, "rejection": str(error)})
        else:
            cases.append({"name": name, "passed": False, "error": "Invalid selection was accepted"})

    def duplicate_accepted(values):
        values[2]["runs"][0]["groups"] = [deepcopy(values[1]["runs"][0]["groups"][0])]
    rejected("accepted_original_snapshot_cannot_be_recaptured", duplicate_accepted)
    rejected("failed_attempt_status_cannot_be_rewritten", lambda v: v[1].update(passed=True))
    rejected("missing_declared_snapshot_is_rejected", lambda v: v[3]["runs"][0].update(groups=[]))
    rejected("source_state_depth_substitution_is_rejected", lambda v: v[2]["runs"][0]["groups"][0]["source_state"]["agents"][0].update(depth_m=9.0))
    rejected("cleanup_failure_is_rejected", lambda v: v[2]["runs"][0]["cleanup_checks"].update(actor_released=False))
    rejected("extra_duplicate_image_is_rejected", lambda v: v[2]["traceable_images"].append(deepcopy(v[2]["traceable_images"][0])))
    rejected("image_split_substitution_is_rejected", lambda v: v[2]["traceable_images"][0].update(split="train"))
    rejected("changed_runtime_code_flag_is_rejected", lambda v: v[3].update(runtime_code_unchanged=False))
    rejected("changed_declaration_flag_is_rejected", lambda v: v[3].update(declaration_unchanged=False))
    rejected("failed_group_cannot_be_promoted_into_source_set", lambda v: v[1]["runs"][0]["groups"][1].update(passed=True))
    after = {str(path): digest(path) for path in paths}
    result = {"kind": "m7_new_source_selection_independent_fail_injection_review",
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "passed": all(row["passed"] for row in cases) and before == after,
              "cases": cases, "cases_passed": sum(row["passed"] for row in cases),
              "source_pins_before": before, "source_pins_after": after,
              "sources_unchanged": before == after, "live_calls_made": False,
              "synthetic_fixture_metadata_used_only_in_memory": True,
              "captures_created": 0, "capture_acceptance_claimed": False,
              "biological_approval": False}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "cases_passed": result["cases_passed"],
                      "cases": len(cases), "result": str(output)}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
