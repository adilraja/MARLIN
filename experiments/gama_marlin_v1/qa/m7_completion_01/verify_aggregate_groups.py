"""Run the unchanged M7 retained-USD verifier on all complete aggregate groups.

This wrapper never imports Kit, sends HTTP, renders, or edits captured evidence.
Original per-group verification commands and tolerances remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUTPUT = Path(__file__).resolve().parent
QA = OUTPUT.parent
ROOT = OUTPUT.parents[3]
CAMPAIGN_VERIFIER = QA / "verify_m7_campaign_groups.py"
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}


def safe(path):
    path = Path(path)
    if BLOCKED.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated/runtime inputs are prohibited")
    resolved = path.resolve()
    if BLOCKED.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Input resolves into a prohibited generated/runtime directory")
    return resolved


def digest(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def artifact_pins(aggregate, report):
    """Check every aggregate provenance copy without opening runtime assets."""
    pins = {}
    for name in ("results.json", "declaration.json", "trajectory_split_manifest.json"):
        path = safe(aggregate / name)
        pins[str(path)] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    if pins[str(aggregate / "declaration.json")]["sha256"] != report["declaration"]["sha256"]:
        raise ValueError("Aggregate declaration hash differs")
    if pins[str(aggregate / "trajectory_split_manifest.json")]["sha256"] != report["trajectory_split_manifest"]["sha256"]:
        raise ValueError("Aggregate trajectory split manifest hash differs")
    groups = report["group_provenance"]
    if len(groups) != 15:
        raise ValueError("Require exactly fifteen provenance-bound copied groups")
    for group in groups:
        target_group = safe(group["target_group"])
        expected = aggregate / "captures" / group["run_id"] / f"step_{group['step_index']:03d}" / "group"
        if target_group != expected or group["all_copied_files_byte_identical"] is not True:
            raise ValueError("Aggregate provenance group path or copy proof differs")
        for row in group["copied_files"]:
            target, source = safe(row["target_path"]), safe(row["source_path"])
            if not target.is_relative_to(aggregate) or not source.is_relative_to(QA):
                raise ValueError("Copied provenance paths leave their scoped QA evidence")
            if row["byte_identical"] is not True or row["target_sha256"] != row["source_sha256"]:
                raise ValueError("Copied bytes lack matching source/target provenance")
            for path, key in ((target, "target_sha256"), (source, "source_sha256")):
                actual = {"bytes": path.stat().st_size, "sha256": digest(path)}
                if actual != {"bytes": row["bytes"], "sha256": row[key]}:
                    raise ValueError("Provenance file bytes differ: " + str(path))
                if str(path) in pins and pins[str(path)] != actual:
                    raise ValueError("Conflicting provenance file pin")
                pins[str(path)] = actual
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", required=True, type=Path)
    args = parser.parse_args()
    aggregate = safe(args.aggregate)
    if not aggregate.is_dir() or not aggregate.is_relative_to(QA) or aggregate.is_relative_to(OUTPUT):
        raise ValueError("Require a completed separate aggregate in this sprint QA directory")
    result_path = OUTPUT / "verification_orchestrator_result.json"
    command_path = OUTPUT / "campaign_verifier_execution.json"
    log_path = OUTPUT / "campaign_verifier.log"
    independent = QA / "m7_scene_validation_set"
    if any(path.exists() for path in (result_path, command_path, log_path, independent)):
        raise ValueError("Existing independent verification evidence cannot be overwritten")
    report = {"kind": "m7_complete_aggregate_independent_usd_verification", "passed": False,
              "started_at_utc": now(), "aggregate": str(aggregate),
              "kit_imported": False, "http_requests": 0, "renders_requested": 0,
              "captured_evidence_mutated": False, "runtime_mdl_bytes_inspected": False,
              "biological_approval": False, "rendered_visibility": "unknown",
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
              "expected_groups": 15, "expected_captures": 150}
    before = None
    try:
        accepted = json.loads((aggregate / "results.json").read_text())
        if (accepted.get("kind") != "m7_accepted_capture_set_aggregate"
                or accepted.get("passed") is not True
                or accepted.get("capture_counts") != {"target_present": 75, "target_absent": 75, "groups": 15}
                or accepted.get("runtime_code_unchanged") is not True
                or accepted.get("source_trees_unchanged") is not True
                or accepted.get("declaration_unchanged") is not True):
            raise ValueError("Require the completed preserved 75-positive/75-absent aggregate")
        specification = importlib.util.spec_from_file_location("_unchanged_m7_campaign_verifier", CAMPAIGN_VERIFIER)
        campaign = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(campaign)
        expected = [(f"m5_positive_seed_{seed}_a", step) for seed in campaign.SEEDS for step in campaign.STEPS]
        actual = [(row["run_id"], row["step_index"]) for row in accepted["group_provenance"]]
        if len(set(actual)) != 15 or set(actual) != set(expected):
            raise ValueError("Copied aggregate groups differ from the unchanged declared verifier workload")
        for run_id, step in expected:
            if not campaign.ready(aggregate / "captures" / run_id / f"step_{step:03d}"):
                raise ValueError("Aggregate group is not finally accepted: " + run_id + "/" + str(step))
        before = artifact_pins(aggregate, accepted)
        report["retained_provenance_file_pins_before"] = before
        pins = {str(path.relative_to(ROOT)): digest(path) for path in campaign.PINNED_SOURCES}
        pins[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).resolve())
        report["verifier_and_helper_source_pins_before"] = pins
        command = [sys.executable, "-B", str(CAMPAIGN_VERIFIER),
                   "--campaign", str(aggregate), "--output", str(independent),
                   "--timeout-seconds", "3600"]
        execution = {"command": command, "cwd": str(ROOT), "started_at_utc": now(),
                     "note": "Unchanged campaign verifier launches installed Blender USD Python -B per group"}
        monotonic = time.monotonic()
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with log_path.open("xb") as log:
            completed = subprocess.run(command, cwd=str(ROOT), env=environment,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=3600, check=False)
        execution.update(finished_at_utc=now(), duration_seconds=time.monotonic() - monotonic,
                         return_code=completed.returncode, log=str(log_path), log_sha256=digest(log_path))
        write(command_path, execution)
        validation = json.loads((independent / "results.json").read_text())
        if completed.returncode != 0 or validation.get("passed") is not True or len(validation["groups"]) != 15:
            raise ValueError("Unchanged campaign USD verification did not pass all fifteen groups")
        verified, unresolved = [], set()
        present = absent = 0
        for group in validation["groups"]:
            item_path = safe(independent / group["result"])
            if not item_path.is_relative_to(independent) or digest(item_path) != group["result_sha256"]:
                raise ValueError("Independent group result path/hash differs")
            item = json.loads(item_path.read_text())
            if item.get("passed") is not True or len(item["captures"]) != 10:
                raise ValueError("Independent group lacks ten verified actual captures")
            present += sum(row["target_present"] for row in item["captures"])
            absent += sum(not row["target_present"] for row in item["captures"])
            for dependency in item["dependency_checks"]:
                if dependency["status"] == "runtime_or_unresolved":
                    if dependency["bytes_read"] is not False:
                        raise ValueError("Runtime/unresolved dependency bytes were inspected")
                    unresolved.add(dependency["path"])
            verified.append(group)
        after = artifact_pins(aggregate, accepted)
        current = {str(path.relative_to(ROOT)): digest(path) for path in campaign.PINNED_SOURCES}
        current[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).resolve())
        report.update(groups=verified, capture_counts={"target_present": present, "target_absent": absent, "groups": len(verified)},
                      runtime_or_unresolved_dependencies_not_opened=sorted(unresolved),
                      retained_provenance_file_pins_after=after,
                      retained_provenance_files_unchanged=before == after,
                      verifier_and_helper_source_pins_after=current,
                      verifier_and_helper_sources_unchanged=current == pins,
                      campaign_result=str(independent / "results.json"),
                      campaign_result_sha256=digest(independent / "results.json"))
        report["passed"] = (present == absent == 75 and len(verified) == 15 and before == after and current == pins)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at_utc"] = now()
        write(result_path, report)
    print(json.dumps({"passed": report["passed"], "result": str(result_path),
                      "capture_counts": report.get("capture_counts"), "error": report.get("error")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
