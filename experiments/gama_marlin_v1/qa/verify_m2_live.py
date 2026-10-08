"""Verify live M2 validation and previews; never acquire or author a scene actor.

Requires an already-running MARLIN bridge. Resets only a new, initially empty v2
validation buffer. Writes new evidence files exclusively, preserving prior runs.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=QA / "m2_live_results.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Live evidence already exists; choose a new output path")
    base = "http://127.0.0.1:8011"
    trace = []

    def call(path, payload=None):
        request = Request(base + path, data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            value = json.load(response)
            trace.append({"path": path, "request": payload, "http_status": response.status,
                          "response": value})
        return value

    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "base_url": base, "scene_actor_acquired": False, "trace": trace,
              "biological_approval": False, "passed": False}
    needs_reset = False
    try:
        before = call("/debug/scene/inspection")
        assert before["ok"], before
        v1_before = call("/integration/gama/status")
        status = call("/integration/gama/v2/status")
        assert status["ok"] and status["latest"] is None and status["accepted_steps"] == 0, status
        report["current_stage"] = call("/integration/gama/stage")["stage_coordinates"]
        assert report["current_stage"]["stage_available"], report["current_stage"]
        data = json.loads((ROOT / "integrations/gama/examples/step_v2.json").read_text())
        valid = call("/integration/gama/v2/validate", data)
        assert valid["ok"] and valid["snapshot"] == data and not valid["rendered"], valid
        preview = call("/integration/gama/v2/preview", data)
        if report["current_stage"]["suitable_for_v2"]:
            assert preview["ok"], preview
            units = report["current_stage"]["meters_per_scene_unit"]
            resolved = preview["transforms"][0]
            assert resolved["position_scene_units"] == [1.25 / units, -.8 / units, -2.5 / units], resolved
            assert not preview["rendered"], preview
            report["live_conversion_preview"] = "passed"
        else:
            assert preview["ok"] is False, preview
            report["live_conversion_preview"] = "correctly_rejected_unsuitable_current_stage"
        before_buffer = call("/integration/gama/v2/status")
        assert before_buffer["accepted_steps"] == 0 and before_buffer["latest"] is None, before_buffer
        first = call("/integration/gama/v2/steps", data)
        assert first["ok"] and first["accepted"] and not first["duplicate"], first
        needs_reset = True
        duplicate = call("/integration/gama/v2/steps", data)
        assert duplicate["ok"] and duplicate["duplicate"], duplicate
        for field, value in (("position_m", [1, 2, 3]), ("vertical_reference", "instantaneous_wave_surface"),
                             ("depth_m", -1)):
            bad = deepcopy(data)
            bad["agents"][0][field] = value
            assert call("/integration/gama/v2/steps", bad)["ok"] is False
        older = deepcopy(data)
        older.update(step_index=9, simulation_time_s=4.5)
        assert call("/integration/gama/v2/steps", older)["ok"] is False
        after_rejections = call("/integration/gama/v2/status")
        assert after_rejections["accepted_steps"] == 1 and after_rejections["latest"] == data, after_rejections
        assert not after_rejections["scene_control_enabled"], after_rejections
        assert call("/integration/gama/status") == v1_before, "v1 state changed"
        assert call("/debug/scene/inspection") == before, "Scene inspection changed"
        assert call("/integration/gama/stage")["stage_coordinates"] == report["current_stage"], "Stage metadata changed"
        report["checks"] = {"live_routes_registered": True, "valid_state_accepted": True,
                            "latest_duplicate_idempotent": True, "invalid_states_rejected": 4,
                            "buffer_atomic_after_rejection": True, "v1_state_unchanged": True,
                            "scene_inspection_unchanged": True, "stage_metadata_unchanged": True,
                            "preview_did_not_buffer_state": True}
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if needs_reset:
            try:
                reset = call("/integration/gama/v2/reset", {})
                final = call("/integration/gama/v2/status")
                report["validation_buffer_cleaned"] = (reset["ok"] and final["latest"] is None and final["accepted_steps"] == 0)
                if not report["validation_buffer_cleaned"]:
                    report["passed"] = False
            except Exception as error:
                report["cleanup_error"] = str(error)
                report["passed"] = False
        source = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
        report["source_sha256"] = {n: hashlib.sha256((source / n).read_bytes()).hexdigest()
                                   for n in ("extension.py", "exchange_v2.py", "stage_coordinates.py")}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as out:
            out.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "trace"}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
