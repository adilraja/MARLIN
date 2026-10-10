"""Capture one remaining predeclared snapshot with the frozen M7 protocol.

Only seed 2147483647 steps 16 and 32 are permitted. Earlier accepted groups
are pinned and never captured again. Kit restart/recovery is a separate task.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
import capture_gama_dataset_pending_v2 as pending

capture, live = pending.capture, pending.live
BASE, QA = capture.BASE, capture.SPRINT / "qa"
ORIGINAL = QA / "m7_live_02"
SUPPLEMENT = QA / "m7_supplement_01"
RUN_ID = "m5_positive_seed_2147483647_a"
ALLOWED_STEPS = (16, 32)
CLEANUP_KEYS = frozenset((
    "eleven_original_swimmers_running", "all_original_swimmers_advanced",
    "controller_configuration_preserved", "no_deformation_errors",
    "ocean_advanced", "ocean_configuration_preserved",
    "renderer_settings_preserved", "stable_scene_attributes_preserved",
    "original_camera_preserved", "layers_restored", "actor_released",
    "private_root_absent"))


def now():
    return datetime.now(timezone.utc).isoformat()


def code_pins():
    """Keep all 31 frozen pins and add this new workload-selection helper."""
    return sorted(pending.supplement_code_pins() + [capture.pin(Path(__file__))],
                  key=lambda row: row["path"])


def require_cleanup(result):
    checks = result.get("cleanup_checks", {})
    if (set(checks) != CLEANUP_KEYS or any(value is not True for value in checks.values())
            or result.get("cleanup_error") or result.get("cleanup_verification_error")):
        raise ValueError("Require all twelve cleanup checks and no cleanup error")


def verified_source_attempt(directory, declaration, expected_step, passed):
    """Validate accepted groups and preserve exact failed attempt status."""
    report = json.loads((directory / "results.json").read_text())
    expected_kind = ("m7_pending_only_capture_attempt" if directory == SUPPLEMENT
                     else "m7_single_pending_snapshot_attempt")
    if (report.get("kind") != expected_kind or report.get("passed") is not passed
            or report.get("preflight_only") is not False
            or report.get("biological_approval") is not False
            or report.get("declaration") != capture.pin(capture.DECLARATION)
            or report.get("declaration_unchanged") is not True
            or live.digest(directory / "declaration.json") != report["declaration"]["sha256"]
            or report.get("runtime_code_unchanged") is not True
            or report.get("runtime_code_before") != report.get("runtime_code_after")
            or report.get("pending_plan_unchanged") is not True
            or report.get("pending_plan") != capture.pin(directory / "pending_plan.json")):
        raise ValueError("Source attempt status, declaration or source preservation differs")
    frozen = pending.supplement_code_pins()
    recorded = report["runtime_code_before"]
    if directory == SUPPLEMENT:
        if recorded != frozen or report.get("source_campaign_unchanged") is not True:
            raise ValueError("Failed supplement changed frozen capture code or original evidence")
    elif (recorded != code_pins() or report.get("source_trees_unchanged") is not True
          or report.get("pending_plan_unchanged") is not True):
        raise ValueError("Prior one-snapshot continuation changed its helper or source trees")
    for phase in ("preservation_before", "preservation_after"):
        checks = report.get(phase, [])
        if len(checks) != 2 or any(row.get("passed") is not True for row in checks):
            raise ValueError("Source attempt did not preserve both M5/M6 seals")
    if len(report.get("runs", [])) != 1:
        raise ValueError("Source continuation must contain exactly one declared run")
    result = report["runs"][0]
    run = next(row for row in declaration["runs"] if row["run_id"] == RUN_ID)
    if (result.get("run_id") != RUN_ID or result.get("passed") is not passed
            or any(result.get(key) != run[key] for key in ("seed", "split", "encounter_group_id"))):
        raise ValueError("Source continuation run identity/status differs")
    require_cleanup(result)
    expected_groups = [(8, True), (16, False)] if directory == SUPPLEMENT else [(expected_step, True)]
    if [(row.get("step_index"), row.get("passed")) for row in result["groups"]] != expected_groups:
        raise ValueError("Source continuation did not contain the exact expected accepted/failed groups")
    rebuilt, accepted, failures = [], [], []
    for group in result["groups"]:
        state = next(row for row in run["selected_states"] if row["step_index"] == group["step_index"])
        if (group.get("run_id") != RUN_ID or group.get("source_state") != state
                or any(group.get(key) != run[key] for key in ("split", "encounter_group_id"))):
            raise ValueError("A source continuation substituted the selected state or split")
        step_directory = directory / "captures" / RUN_ID / f"step_{state['step_index']:03d}"
        if json.loads((step_directory / "group_result.json").read_text()) != group:
            raise ValueError("Source group result differs from the retained attempt report")
        if group["passed"]:
            if (group.get("held_state") is not True or not group.get("retained_group")
                    or not group.get("coexistence_checks")
                    or any(value is not True for value in group["coexistence_checks"].values())):
                raise ValueError("Accepted source group lacks held-state/coexistence evidence")
            checks = capture.validate_group(step_directory / "group", state, group["capture_response"])
            if checks != group["group_checks"]:
                raise ValueError("Accepted source capture validation changed")
            rebuilt.extend(pending.image_rows(run, state, checks, step_directory / "group", directory))
            accepted.append({"run_id": RUN_ID, "step_index": state["step_index"],
                             "source_step_directory": str(step_directory),
                             "source_group_directory": str(step_directory / "group"),
                             "group_result": capture.pin(step_directory / "group_result.json"),
                             "group_manifest": capture.pin(step_directory / "group/manifest.json")})
        else:
            attempts = group.get("capture_attempts", [])
            if (group.get("retained_group") or len(attempts) != capture.HEADROOM_ATTEMPTS
                    or any(not capture.is_no_render_headroom(row.get("response")) for row in attempts)
                    or group.get("capture_response") != attempts[-1]["response"]
                    or attempts[-1].get("retry_exhausted") is not True):
                raise ValueError("Only the exact exhausted pre-render headroom refusal may remain pending")
            failures.append({"run_id": RUN_ID, "step_index": state["step_index"],
                             "passed": False, "capture_response": group["capture_response"],
                             "capture_attempts": attempts,
                             "group_result": capture.pin(step_directory / "group_result.json")})
    if (rebuilt != report["traceable_images"] or len(rebuilt) != 10
            or report.get("capture_counts") != {"target_present": 5, "target_absent": 5, "groups": 1}):
        raise ValueError("Source continuation's ten accepted image records changed")
    return {"directory": str(directory), "result": capture.pin(directory / "results.json"),
            "passed": passed, "accepted_groups": accepted, "failed_group_statuses": failures}, pending.tree_pins(directory)


def build_plan(step):
    if type(step) is not int or step not in ALLOWED_STEPS:
        raise ValueError("Only the still-pending declared steps 16 and 32 are allowed")
    original_plan = pending.build_pending_plan(ORIGINAL, capture.DECLARATION)
    declaration = capture.validate_declaration(capture.DECLARATION)
    supplement, supplement_tree = verified_source_attempt(SUPPLEMENT, declaration, 8, False)
    saved = json.loads((SUPPLEMENT / "pending_plan.json").read_text())
    saved.pop("saved_before_rendering_at_utc", None)
    original = json.loads((ORIGINAL / "results.json").read_text())
    if saved != original_plan:
        raise ValueError("Failed supplement's exact saved original pending plan no longer matches")
    attempts = [{"directory": str(ORIGINAL), "result": capture.pin(ORIGINAL / "results.json"),
                 "passed": False, "accepted_groups": original_plan["accepted_source_groups"],
                 "failed_group_statuses": [{"run_id": RUN_ID, "step_index": 8, "passed": False,
                    "capture_response": original["runs"][-1]["groups"][-1]["capture_response"]}]}, supplement]
    trees = [original_plan["source_tree_pins"], supplement_tree]
    accepted = original_plan["accepted_source_groups"] + supplement["accepted_groups"]
    if step == 32:
        previous, previous_tree = verified_source_attempt(QA / "m7_supplement_step_016", declaration, 16, True)
        attempts.append(previous)
        trees.append(previous_tree)
        accepted.extend(previous["accepted_groups"])
    accepted_keys = [(row["run_id"], row["step_index"]) for row in accepted]
    if (len(set(accepted_keys)) != len(accepted_keys) or (RUN_ID, step) in accepted_keys
            or len(accepted) != (13 if step == 16 else 14)):
        raise ValueError("Refusing to recapture an accepted snapshot")
    run = next(row for row in declaration["runs"] if row["run_id"] == RUN_ID)
    selected = next(row for row in run["selected_states"] if row["step_index"] == step)
    return {"kind": "m7_single_pending_snapshot_plan", "declaration": capture.pin(capture.DECLARATION),
            "source_attempts": attempts, "source_tree_pins": trees,
            "accepted_source_groups": accepted, "accepted_source_images": 10 * len(accepted),
            "pending_groups": [{"run_id": RUN_ID, "step_index": step, "split": "test", "source_state": selected}],
            "pending_images": 10, "frozen_capture_protocol_code_pins": pending.supplement_code_pins(),
            "qa_helper_pin": capture.pin(Path(__file__)), "capture_code_pins": code_pins(),
            "no_accepted_groups_recaptured": True, "same_immutable_declaration": True,
            "no_source_or_image_substitution": True, "all_prior_attempt_statuses_retained": True,
            "uninterrupted_successful_capture_claimed": False,
            "biological_approval": False, "milestone_8_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True, type=int, choices=ALLOWED_STEPS)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    address = urlparse(args.url)
    if (address.scheme not in ("http", "https") or address.hostname not in ("localhost", "127.0.0.1", "::1")
            or address.username or address.password or address.query or address.fragment or address.path not in ("", "/")):
        parser.error("Use a loopback MARLIN URL without credentials, paths or query parameters")
    output = live.safe_path(QA / f"m7_supplement_step_{args.step:03d}")
    if args.output is not None and live.safe_path(args.output) != output:
        parser.error("Use the fixed new QA directory for the selected step")
    output.mkdir(parents=True, exist_ok=False)
    token, plan, pins, seals = None, None, None, []
    report = {"kind": "m7_single_pending_snapshot_attempt", "milestone": 7, "passed": False,
              "preflight_only": args.preflight_only, "started_at_utc": now(), "selected_step_index": args.step,
              "scene_mutation_attempted": False, "biological_approval": False, "milestone_8_started": False,
              "runs": [], "traceable_images": [], "uninterrupted_successful_capture_claimed": False,
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
              "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
              "exact_visible_or_refracted_outlines_claimed": False}

    def request(path, payload=None, expect_ok=True, with_http_code=False):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = urllib.request.Request(args.url.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1200) as response:
            value, http_code = json.load(response), response.status
        if not isinstance(value, dict) or (expect_ok and value.get("ok") is not True):
            raise ValueError(f"{path}: {live.redact(value, token)}")
        return (value, http_code) if with_http_code else value

    def audit():
        return request("/integration/gama/marine/audit")

    try:
        plan = build_plan(args.step)
        live.write_json(output / "pending_plan.json", {**plan, "saved_before_acquire_and_rendering_at_utc": now()})
        report.update(pending_plan=capture.pin(output / "pending_plan.json"), declaration=plan["declaration"],
                      source_attempts=plan["source_attempts"], source_tree_pins_before=plan["source_tree_pins"])
        with (output / "declaration.json").open("xb") as stream:
            stream.write(capture.DECLARATION.read_bytes())
        if live.digest(output / "declaration.json") != plan["declaration"]["sha256"]:
            raise ValueError("Declaration copy differs from its immutable source")
        seals = [capture.load_seal(live.M5_MANIFEST), capture.load_seal(capture.M6_MANIFEST, capture.ALLOWED_M6_DELTAS)]
        report["preservation_before"] = [capture.verify_seal(seal) for seal in seals]
        if not all(row["passed"] for row in report["preservation_before"]):
            raise ValueError("Protected M5/M6 evidence changed before capture")
        pins = code_pins()
        if pins != plan["capture_code_pins"]:
            raise ValueError("Capture code changed after pending-plan construction")
        report.update(runtime_code_before=pins, frozen_capture_protocol_before=pending.supplement_code_pins(),
                      qa_helper_before=capture.pin(Path(__file__)))
        report["disk_preflight"] = capture.disk_preflight(output)
        if not report["disk_preflight"]["passed"]:
            raise ValueError("Insufficient free space for unchanged retained capture evidence")
        report["before"] = audit()
        report["actor_before"] = request(BASE + "/status")
        live.require_demo(report["before"])
        if report["actor_before"]["owned"] or report["actor_before"]["root_present_on_active_stage"]:
            raise ValueError("Refusing an existing owner/private root")
        if args.preflight_only:
            time.sleep(2)
            report["second_audit"] = audit()
            checks = live.coexistence(report["before"], report["second_audit"])
            checks["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["second_audit"]["inspection"]["layers"]
            report.update(preflight_checks=checks, passed=all(checks.values()))
        else:
            declaration = capture.validate_declaration(capture.DECLARATION)
            run = next(row for row in declaration["runs"] if row["run_id"] == RUN_ID)
            states, actual = capture.verified_run(run["seed"])
            if any(actual[key] != run[key] for key in ("source_files", "canonical_state_sha256", "runtime", "actual_execution")):
                raise ValueError("Declared actual trajectory changed before replay")
            result = {"run_id": RUN_ID, "seed": run["seed"], "split": run["split"],
                      "encounter_group_id": run["encounter_group_id"], "passed": False, "groups": [],
                      "before": report["before"], "actor_before": report["actor_before"]}
            report["runs"].append(result)
            run_output = output / "captures" / RUN_ID
            run_output.mkdir(parents=True, exist_ok=False)
            try:
                result["checkpoint_before_acquire"] = request("/debug/scene/checkpoint", {})
                report["scene_mutation_attempted"] = True
                acquired = request(BASE + "/acquire", {"agent_id": states[0]["agents"][0]["agent_id"]})
                token = acquired["ownership_token"]
                result["acquired"] = live.redact(acquired, token)
                result["replayed_step_indices"] = []
                for state in states[:args.step + 1]:
                    applied = request(BASE + "/step", {"ownership_token": token, "step": state})
                    if applied.get("applied") is not True or applied.get("duplicate") is not False:
                        raise ValueError("Actual GAMA step was not accepted exactly once")
                    result["replayed_step_indices"].append(state["step_index"])
                state = states[args.step]
                if state != plan["pending_groups"][0]["source_state"]:
                    raise ValueError("Refusing a capture outside the saved exact pending plan")
                step_output = run_output / f"step_{args.step:03d}"
                step_output.mkdir(exist_ok=False)
                group = {"run_id": RUN_ID, "step_index": args.step, "source_state": state,
                         "split": run["split"], "encounter_group_id": run["encounter_group_id"], "passed": False}
                result["groups"].append(group)
                print(json.dumps({"event": "capture_started", "run_id": RUN_ID, "step_index": args.step,
                                  "planned_groups": 1, "accepted_source_images_preserved": plan["accepted_source_images"]}), flush=True)
                try:
                    group["actor_before"] = request(BASE + "/status")
                    group["pose_before"] = live.compare_pose(state, group["actor_before"], acquired["meters_per_scene_unit"])
                    group["capture_attempts"] = []
                    response = capture.capture_with_headroom_retry(
                        lambda: request(BASE + "/dataset-capture", {"ownership_token": token}, expect_ok=False, with_http_code=True),
                        lambda: request(BASE + "/status"), state, group["actor_before"], acquired["meters_per_scene_unit"],
                        group["capture_attempts"], pins, code_read=code_pins)
                    group["capture_response"] = live.redact(response, token)
                    if response.get("directory"):
                        group["retained_group"] = live.copy_group(response["directory"], step_output)
                    if response.get("ok") is not True:
                        raise ValueError("Pending capture failed; all responses and any returned group were retained")
                    if not group.get("retained_group") or group["capture_attempts"][-1].get("held_state_after_response") is not True:
                        raise ValueError("Group retained, but held actor could not be verified")
                    group["group_checks"] = capture.validate_group(step_output / "group", state, response)
                    group["actor_after"] = request(BASE + "/status")
                    capture._assert_held_state(group["actor_after"], state, group["actor_before"], acquired["meters_per_scene_unit"])
                    group["pose_after"] = live.compare_pose(state, group["actor_after"], acquired["meters_per_scene_unit"])
                    group["held_state"] = True
                    group["capture_attempts"][-1].update(status_after_capture=group["actor_after"], held_state_after_capture=True)
                    group["during"] = audit()
                    group["coexistence_checks"] = live.coexistence(result["before"], group["during"])
                    if not all(group["coexistence_checks"].values()):
                        raise ValueError("Pending capture changed the existing marine demonstration")
                    report["traceable_images"].extend(pending.image_rows(run, state, group["group_checks"], step_output / "group", output))
                    group["passed"] = True
                except BaseException as error:
                    group["error"] = live.redact(f"{type(error).__name__}: {error}", token)
                    raise
                finally:
                    live.write_json(step_output / "group_result.json", live.redact(group, token))
                    print(json.dumps({"event": "capture_finished", "run_id": RUN_ID, "step_index": args.step,
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
                        result["cleanup_checks"] = pending.cleanup_checks(result["before"], result["after_release"], result["actor_after_release"])
                        require_cleanup(result)
                    except BaseException as error:
                        result["cleanup_verification_error"] = live.redact(f"{type(error).__name__}: {error}", token)
                result["passed"] = (not result.get("error") and not result.get("cleanup_error")
                    and not result.get("cleanup_verification_error") and len(result["groups"]) == 1
                    and all(row["passed"] for row in result["groups"])
                    and set(result.get("cleanup_checks", {})) == CLEANUP_KEYS
                    and all(result.get("cleanup_checks", {}).values()))
                live.write_json(run_output / "run_result.json", live.redact(result, token))
            report["cleanup_checks"] = result.get("cleanup_checks", {"missing": False})
            report["capture_counts"] = {"target_present": sum(row["target_present"] for row in report["traceable_images"]),
                                        "target_absent": sum(not row["target_present"] for row in report["traceable_images"]),
                                        "groups": sum(row["passed"] for row in result["groups"])}
            report["passed"] = result["passed"] and report["capture_counts"] == {"target_present": 5, "target_absent": 5, "groups": 1}
            if not report["passed"]:
                raise ValueError("Single pending snapshot attempt did not complete; no state/image was substituted")
    except BaseException as error:
        report["error"] = live.redact(f"{type(error).__name__}: {error}", token)
        report["passed"] = False
    finally:
        try:
            report["preservation_after"] = [capture.verify_seal(seal) for seal in seals]
            report["runtime_code_after"] = code_pins() if pins is not None else None
            report["runtime_code_unchanged"] = pins is not None and report["runtime_code_after"] == pins
            report["frozen_capture_protocol_after"] = pending.supplement_code_pins()
            report["qa_helper_after"] = capture.pin(Path(__file__))
            report["declaration_unchanged"] = plan is not None and capture.pin(capture.DECLARATION) == plan["declaration"]
            report["source_tree_pins_after"] = ([] if plan is None else
                [pending.tree_pins(Path(attempt["directory"])) for attempt in plan["source_attempts"]])
            report["source_trees_unchanged"] = plan is not None and report["source_tree_pins_after"] == plan["source_tree_pins"]
            report["pending_plan_unchanged"] = "pending_plan" in report and capture.pin(output / "pending_plan.json") == report["pending_plan"]
            report["passed"] = (report["passed"] and len(report["preservation_after"]) == 2
                and all(row["passed"] for row in report["preservation_after"])
                and report["runtime_code_unchanged"] and report["declaration_unchanged"]
                and report["source_trees_unchanged"] and report["pending_plan_unchanged"])
        except BaseException as error:
            report["preservation_error"] = live.redact(f"{type(error).__name__}: {error}", token)
            report["passed"] = False
        report["finished_at_utc"] = now()
        live.write_json(output / "results.json", live.redact(report, token))
    print(json.dumps({"event": "single_pending_snapshot_finished", "passed": report["passed"],
                      "preflight_only": args.preflight_only, "results": str(output / "results.json"),
                      "capture_counts": report.get("capture_counts"), "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
