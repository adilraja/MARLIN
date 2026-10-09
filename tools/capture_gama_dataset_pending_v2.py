"""Capture only the three missing declared M7 test snapshots.

The failed source campaign remains immutable. A pending plan is saved before
any new rendering; accepted source groups are never replayed for new images.
This imports the frozen original client's validation and bounded retry helpers.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
from urllib.parse import urlparse
import urllib.request

import capture_gama_dataset_v2 as capture

live = capture.live
ROOT, BASE = capture.ROOT, capture.BASE
DEFAULT_SOURCE = capture.SPRINT / "qa/m7_live_02"
PENDING_RUN = "m5_positive_seed_2147483647_a"


def now():
    return datetime.now(timezone.utc).isoformat()


def tree_pins(directory):
    """Pin every regular evidence file without entering generated directories."""
    directory = live.safe_path(directory)
    rows = []
    for parent, directories, names in os.walk(directory, followlinks=False):
        if live.FORBIDDEN_PARTS.intersection(directories):
            raise ValueError("Evidence contains a prohibited generated directory")
        for name in directories + names:
            path = Path(parent) / name
            if path.is_symlink() or path.suffix == ".pyc":
                raise ValueError("Evidence symlinks and generated files are unsupported")
        rows.extend(capture.pin(Path(parent) / name) for name in sorted(names))
    return sorted(rows, key=lambda row: row["path"])


def select_pending(declaration, report):
    """Validate partial selection; return exactly the three untouched test keys."""
    if (report.get("passed") is not False or report.get("preflight_only") is not False
            or report.get("biological_approval") is not False
            or report.get("runtime_code_unchanged") is not True
            or report.get("declaration_unchanged") is not True
            or report.get("runtime_code_before") != report.get("runtime_code_after")):
        raise ValueError("Require an honest failed capture attempt with unchanged source/code")
    for phase in ("preservation_before", "preservation_after"):
        checks = report.get(phase)
        if not isinstance(checks, list) or len(checks) != 2 or any(row.get("passed") is not True for row in checks):
            raise ValueError("Original M5/M6 preservation checks did not pass")
    runs = declaration["runs"]
    if ([row.get("run_id") for row in report.get("runs", [])] != [row["run_id"] for row in runs]
            or len(runs) != 5):
        raise ValueError("Partial capture run identities differ from the immutable declaration")
    expected = {(run["run_id"], state["step_index"]): (run, state)
                for run in runs for state in run["selected_states"]}
    if len(expected) != 15 or sum(len(run["selected_states"]) for run in runs) != 15:
        raise ValueError("Declaration has missing or duplicate selected snapshots")
    accepted, seen, failed = [], set(), []
    for result, run in zip(report["runs"], runs):
        cleanup = result.get("cleanup_checks", {})
        if (not cleanup or any(value is not True for value in cleanup.values())
                or result.get("cleanup_error") or result.get("cleanup_verification_error")
                or any(result.get(key) != run[key] for key in ("seed", "split", "encounter_group_id"))):
            raise ValueError("A partial source run lacks safe cleanup or declared identity")
        for group in result["groups"]:
            key = (group.get("run_id"), group.get("step_index"))
            if key not in expected or key in seen or key[0] != run["run_id"]:
                raise ValueError("Undeclared or duplicate source capture group")
            seen.add(key)
            declared_run, state = expected[key]
            if (group.get("source_state") != state
                    or any(group.get(field) != declared_run[field] for field in ("split", "encounter_group_id"))):
                raise ValueError("Source capture changed a declared snapshot or split")
            if group.get("passed") is True:
                if (group.get("held_state") is not True or not group.get("retained_group")
                        or not group.get("coexistence_checks")
                        or any(value is not True for value in group["coexistence_checks"].values())):
                    raise ValueError("Accepted source group lacks held-state/coexistence evidence")
                accepted.append(key)
            elif group.get("passed") is False:
                attempts = group.get("capture_attempts", [])
                if (group.get("retained_group") or len(attempts) != capture.HEADROOM_ATTEMPTS
                        or any(not capture.is_no_render_headroom(row.get("response")) for row in attempts)
                        or group.get("capture_response") != attempts[-1]["response"]
                        or attempts[-1].get("retry_exhausted") is not True):
                    raise ValueError("Only an exhausted exact no-render failure may be supplemented")
                failed.append(key)
            else:
                raise ValueError("Source group passed flag must be explicit")
        should_pass = run["run_id"] != PENDING_RUN
        if result.get("passed") is not should_pass:
            raise ValueError("Source attempt run status does not match the retained partial workload")
    pending = [key for key in expected if key not in set(accepted)]
    wanted = [(PENDING_RUN, step) for step in capture.STEPS]
    if (pending != wanted or failed != [(PENDING_RUN, 8)] or len(accepted) != 12
            or len(report.get("traceable_images", [])) != 120
            or len({row.get("image_id") for row in report["traceable_images"]}) != 120):
        raise ValueError("Supplement must contain only the three missing declared test snapshots")
    return {"accepted_keys": accepted, "pending_keys": pending}


def image_rows(run, state, checks, group, campaign):
    rows = []
    for image in checks["images"]:
        row = {"image_id": f"{run['run_id']}__step_{state['step_index']:03d}__{image['variant']}__gsd_{image['gsd_cm_px']:g}",
               "run_id": run["run_id"], "related_run_ids": run["related_run_ids"],
               "encounter_group_id": run["encounter_group_id"], "split": run["split"], "seed": run["seed"],
               "step_index": state["step_index"], "simulation_time_s": state["simulation_time_s"],
               "original_gama_depth_m": state["agents"][0]["depth_m"],
               "behavioural_state": state["agents"][0]["behavioural_state"],
               "source_canonical_state_sha256": run["canonical_state_sha256"], "source_files": run["source_files"], **image}
        for name in ("rgb_file", "annotation_file", "yolo_file"):
            row[name] = str((group / image[name]).relative_to(campaign))
        row["group_manifest"] = str((group / "manifest.json").relative_to(campaign))
        row["group_manifest_sha256"] = live.digest(group / "manifest.json")
        rows.append(row)
    return rows


def build_pending_plan(campaign, declaration_path=capture.DECLARATION):
    campaign, declaration_path = map(live.safe_path, (campaign, declaration_path))
    declaration = capture.validate_declaration(declaration_path)
    report = json.loads((campaign / "results.json").read_text())
    selection = select_pending(declaration, report)
    if (report["declaration"] != capture.pin(declaration_path)
            or live.digest(campaign / "declaration.json") != report["declaration"]["sha256"]
            or capture.runtime_code_pins() != report["runtime_code_before"]):
        raise ValueError("Original declaration or frozen capture protocol code changed")
    accepted, rebuilt = [], []
    for run in declaration["runs"]:
        result = next(row for row in report["runs"] if row["run_id"] == run["run_id"])
        for state in run["selected_states"]:
            key = (run["run_id"], state["step_index"])
            if key not in selection["accepted_keys"]:
                continue
            step = campaign / "captures" / run["run_id"] / f"step_{state['step_index']:03d}"
            group_result = json.loads((step / "group_result.json").read_text())
            retained = next(row for row in result["groups"] if row["step_index"] == state["step_index"])
            if group_result != retained:
                raise ValueError("Retained group result differs from the original campaign report")
            checks = capture.validate_group(step / "group", state, group_result["capture_response"])
            if checks != group_result["group_checks"]:
                raise ValueError("Accepted source group changed since original validation")
            rebuilt.extend(image_rows(run, state, checks, step / "group", campaign))
            accepted.append({"run_id": run["run_id"], "step_index": state["step_index"],
                             "source_step_directory": str(step), "source_group_directory": str(step / "group"),
                             "group_result": capture.pin(step / "group_result.json"),
                             "group_manifest": capture.pin(step / "group/manifest.json")})
    if rebuilt != report["traceable_images"]:
        raise ValueError("Original partial image records do not bind the accepted actual groups")
    pending = [{"run_id": key[0], "step_index": key[1], "split": "test",
                "source_state": next(state for run in declaration["runs"] if run["run_id"] == key[0]
                                     for state in run["selected_states"] if state["step_index"] == key[1])}
               for key in selection["pending_keys"]]
    return {"kind": "m7_pending_only_supplement_plan", "declaration": capture.pin(declaration_path),
            "source_campaign": str(campaign), "source_campaign_result": capture.pin(campaign / "results.json"),
            "source_campaign_passed": False, "accepted_source_groups": accepted, "pending_groups": pending,
            "accepted_source_images": 120, "pending_images": 30, "source_tree_pins": tree_pins(campaign),
            "capture_protocol_code_pins": report["runtime_code_before"], "no_accepted_groups_recaptured": True,
            "same_immutable_declaration": True, "no_source_or_image_substitution": True,
            "biological_approval": False, "milestone_8_started": False}


def supplement_code_pins():
    paths = [Path(__file__), Path(__file__).with_name("aggregate_gama_dataset_v2.py")]
    return sorted(capture.runtime_code_pins() + [capture.pin(path) for path in paths], key=lambda row: row["path"])


def cleanup_checks(before, after, status):
    checks = live.coexistence(before, after)
    checks.update(layers_restored=before["inspection"]["layers"] == after["inspection"]["layers"],
                  actor_released=status["owned"] is False and status["actor_count"] == 0,
                  private_root_absent=status["root_present_on_active_stage"] is False)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--source-campaign", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--declaration", type=Path, default=capture.DECLARATION)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    address = urlparse(args.url)
    if (address.scheme not in ("http", "https") or address.hostname not in ("localhost", "127.0.0.1", "::1")
            or address.username or address.password or address.query or address.fragment or address.path not in ("", "/")):
        parser.error("Use a loopback MARLIN URL without credentials, paths or query parameters")
    output, source, declaration_path = map(live.safe_path, (args.output, args.source_campaign, args.declaration))
    if output.is_relative_to(source) or source.is_relative_to(output):
        parser.error("Supplement must be separate from the immutable source campaign")
    output.mkdir(parents=True, exist_ok=False)
    token, plan, code_pins, seals = None, None, None, []
    report = {"kind": "m7_pending_only_capture_attempt", "milestone": 7, "passed": False,
              "preflight_only": args.preflight_only, "started_at_utc": now(), "scene_mutation_attempted": False,
              "biological_approval": False, "milestone_8_started": False, "runs": [], "traceable_images": [],
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
              "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
              "exact_visible_or_refracted_outlines_claimed": False}

    def request(path, payload=None, expect_ok=True, with_http_code=False):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = urllib.request.Request(args.url.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1200) as response:
            value, code = json.load(response), response.status
        if not isinstance(value, dict) or (expect_ok and value.get("ok") is not True):
            raise ValueError(f"{path}: {live.redact(value, token)}")
        return (value, code) if with_http_code else value

    def audit():
        return request("/integration/gama/marine/audit")

    try:
        plan = build_pending_plan(source, declaration_path)
        # Exclusive write and hash happen before checkpoints/acquisition/rendering.
        live.write_json(output / "pending_plan.json", {**plan, "saved_before_rendering_at_utc": now()})
        report["pending_plan"] = capture.pin(output / "pending_plan.json")
        report["declaration"] = plan["declaration"]
        shutil.copyfile(declaration_path, output / "declaration.json")
        if live.digest(output / "declaration.json") != plan["declaration"]["sha256"]:
            raise ValueError("Supplement declaration copy differs from the immutable source")
        seals = [capture.load_seal(live.M5_MANIFEST), capture.load_seal(capture.M6_MANIFEST, capture.ALLOWED_M6_DELTAS)]
        report["preservation_before"] = [capture.verify_seal(seal) for seal in seals]
        if not all(row["passed"] for row in report["preservation_before"]):
            raise ValueError("Protected source evidence changed before the supplement")
        code_pins = supplement_code_pins()
        report["runtime_code_before"] = code_pins
        report["disk_preflight"] = capture.disk_preflight(output)
        if not report["disk_preflight"]["passed"]:
            raise ValueError("Insufficient free space for retained supplemental evidence")
        report["before"] = audit()
        report["actor_before"] = request(BASE + "/status")
        live.require_demo(report["before"])
        if report["actor_before"]["owned"] or report["actor_before"]["root_present_on_active_stage"]:
            raise ValueError("Refusing an existing owner/private root")
        if args.preflight_only:
            time.sleep(2)
            report["second_audit"] = audit()
            report["preflight_checks"] = live.coexistence(report["before"], report["second_audit"])
            report["preflight_checks"]["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["second_audit"]["inspection"]["layers"]
            report["passed"] = all(report["preflight_checks"].values())
        else:
            declaration = capture.validate_declaration(declaration_path)
            run = next(row for row in declaration["runs"] if row["run_id"] == PENDING_RUN)
            states, actual = capture.verified_run(run["seed"])
            if any(actual[key] != run[key] for key in ("source_files", "canonical_state_sha256", "runtime", "actual_execution")):
                raise ValueError("Declared actual test trajectory changed before replay")
            result = {"run_id": run["run_id"], "seed": run["seed"], "split": run["split"],
                      "encounter_group_id": run["encounter_group_id"], "passed": False, "groups": [],
                      "before": report["before"], "actor_before": report["actor_before"]}
            report["runs"].append(result)
            run_output = output / "captures" / run["run_id"]
            run_output.mkdir(parents=True, exist_ok=False)
            try:
                result["checkpoint_before_acquire"] = request("/debug/scene/checkpoint", {})
                report["scene_mutation_attempted"] = True
                acquired = request(BASE + "/acquire", {"agent_id": states[0]["agents"][0]["agent_id"]})
                token = acquired["ownership_token"]
                result["acquired"] = live.redact(acquired, token)
                for step in states[:max(capture.STEPS) + 1]:
                    applied = request(BASE + "/step", {"ownership_token": token, "step": step})
                    if applied.get("applied") is not True or applied.get("duplicate") is not False:
                        raise ValueError("Actual GAMA step was not accepted exactly once")
                    if step["step_index"] not in capture.STEPS:
                        continue
                    if not any(row["source_state"] == step for row in plan["pending_groups"]):
                        raise ValueError("Refusing a capture outside the saved pending-only plan")
                    step_output = run_output / f"step_{step['step_index']:03d}"
                    step_output.mkdir(exist_ok=False)
                    group = {"run_id": run["run_id"], "step_index": step["step_index"], "source_state": step,
                             "split": run["split"], "encounter_group_id": run["encounter_group_id"], "passed": False}
                    result["groups"].append(group)
                    print(json.dumps({"event": "capture_started", "run_id": run["run_id"], "step_index": step["step_index"],
                                      "planned_supplement_groups": 3, "accepted_source_groups_preserved": 12}), flush=True)
                    try:
                        group["actor_before"] = request(BASE + "/status")
                        group["pose_before"] = live.compare_pose(step, group["actor_before"], acquired["meters_per_scene_unit"])
                        group["capture_attempts"] = []
                        response = capture.capture_with_headroom_retry(
                            lambda: request(BASE + "/dataset-capture", {"ownership_token": token}, expect_ok=False, with_http_code=True),
                            lambda: request(BASE + "/status"), step, group["actor_before"], acquired["meters_per_scene_unit"],
                            group["capture_attempts"], code_pins, code_read=supplement_code_pins)
                        group["capture_response"] = live.redact(response, token)
                        if response.get("directory"):
                            group["retained_group"] = live.copy_group(response["directory"], step_output)
                        if response.get("ok") is not True:
                            raise ValueError("Pending capture failed; all returned responses and any group were retained")
                        if not group.get("retained_group") or group["capture_attempts"][-1].get("held_state_after_response") is not True:
                            raise ValueError("Returned group retained, but held actor could not be verified")
                        group["group_checks"] = capture.validate_group(step_output / "group", step, response)
                        group["actor_after"] = request(BASE + "/status")
                        capture._assert_held_state(group["actor_after"], step, group["actor_before"], acquired["meters_per_scene_unit"])
                        group["pose_after"] = live.compare_pose(step, group["actor_after"], acquired["meters_per_scene_unit"])
                        group["held_state"] = True
                        group["capture_attempts"][-1].update(status_after_capture=group["actor_after"], held_state_after_capture=True)
                        group["during"] = audit()
                        group["coexistence_checks"] = live.coexistence(result["before"], group["during"])
                        if not all(group["coexistence_checks"].values()):
                            raise ValueError("Pending capture changed the original marine demonstration")
                        report["traceable_images"].extend(image_rows(run, step, group["group_checks"], step_output / "group", output))
                        group["passed"] = True
                    except BaseException as error:
                        group["error"] = live.redact(f"{type(error).__name__}: {error}", token)
                        raise
                    finally:
                        live.write_json(step_output / "group_result.json", live.redact(group, token))
                        print(json.dumps({"event": "capture_finished", "run_id": run["run_id"], "step_index": step["step_index"],
                                          "passed": group["passed"], "evidence": str(step_output)}), flush=True)
            except BaseException as error:
                result["error"] = live.redact(f"{type(error).__name__}: {error}", token)
            finally:
                if token is not None:
                    try:
                        result["release"] = request(BASE + "/release", {"ownership_token": token})
                    except BaseException as error:
                        result["cleanup_error"] = live.redact(f"{type(error).__name__}: {error}", token)
                    try:
                        time.sleep(2)
                        result["after_release"] = audit()
                        result["actor_after_release"] = request(BASE + "/status")
                        result["cleanup_checks"] = cleanup_checks(result["before"], result["after_release"], result["actor_after_release"])
                    except BaseException as error:
                        result["cleanup_verification_error"] = live.redact(f"{type(error).__name__}: {error}", token)
                    result["passed"] = (not result.get("error") and not result.get("cleanup_error")
                        and not result.get("cleanup_verification_error") and len(result["groups"]) == 3
                        and all(row["passed"] for row in result["groups"])
                        and all(result.get("cleanup_checks", {"missing": False}).values()))
                live.write_json(run_output / "run_result.json", live.redact(result, token))
                token = None
            report["cleanup_checks"] = result.get("cleanup_checks", {"missing": False})
            report["capture_counts"] = {"target_present": sum(row["target_present"] for row in report["traceable_images"]),
                                        "target_absent": sum(not row["target_present"] for row in report["traceable_images"]),
                                        "groups": sum(row["passed"] for row in result["groups"])}
            report["passed"] = result["passed"] and report["capture_counts"] == {"target_present": 15, "target_absent": 15, "groups": 3}
            if not report["passed"]:
                raise ValueError("Pending-only supplement did not complete; no source or image was substituted")
    except BaseException as error:
        report["error"] = live.redact(f"{type(error).__name__}: {error}", token)
        report["passed"] = False
    finally:
        try:
            report["preservation_after"] = [capture.verify_seal(seal) for seal in seals]
            report["runtime_code_after"] = supplement_code_pins() if code_pins is not None else None
            report["runtime_code_unchanged"] = code_pins is not None and report["runtime_code_after"] == code_pins
            report["declaration_unchanged"] = plan is not None and capture.pin(declaration_path) == plan["declaration"]
            report["source_campaign_unchanged"] = plan is not None and tree_pins(source) == plan["source_tree_pins"]
            report["pending_plan_unchanged"] = "pending_plan" in report and capture.pin(output / "pending_plan.json") == report["pending_plan"]
            report["passed"] = (report["passed"] and all(row["passed"] for row in report["preservation_after"])
                and report["runtime_code_unchanged"] and report["declaration_unchanged"]
                and report["source_campaign_unchanged"] and report["pending_plan_unchanged"])
        except BaseException as error:
            report["preservation_error"] = live.redact(f"{type(error).__name__}: {error}", token)
            report["passed"] = False
        report["finished_at_utc"] = now()
        live.write_json(output / "results.json", live.redact(report, token))
    print(json.dumps({"event": "pending_supplement_finished", "passed": report["passed"], "preflight_only": args.preflight_only,
                      "results": str(output / "results.json"), "capture_counts": report.get("capture_counts"), "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
