"""Seal completed M4 evidence without rerunning or mutating the live scene."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    seal = QA / "milestone_4_manifest.json"
    if seal.exists():
        raise SystemExit("Preserve the existing M4 seal")
    offline = read(QA / "m4_final2_offline_results.json")
    assert offline["passed"] and offline["total_tests"] == 86
    for row in offline["python_syntax_checked"]:
        assert sha(ROOT / row["path"]) == row["sha256"], row["path"]
    for row in offline["results"]:
        assert row["passed"] and sha(ROOT / row["log"]) == row["log_sha256"]
    live_directory = QA / "m4_live_03"
    live = read(live_directory / "results.json")
    review = read(QA / "m4_visual_review.json")
    demo = read(live_directory / "porpoise_replay_demo.json")
    final = read(QA / "m4_final_live_status.json")
    assert live["passed"] and final["passed"] and review["passed"]
    assert len(live["cardinal_fixtures"]) == 4 and len(live["actual_gama_transforms"]) == 41
    assert live["maximum_position_error_m"] <= live["declared_tolerances"]["position_euclidean_m"] == 1e-5
    assert live["maximum_heading_error_deg"] <= live["declared_tolerances"]["heading_circular_deg"] == 1e-4
    assert sha(ROOT / live["trajectory"]) == live["trajectory_sha256"] == demo["trajectory_sha256"]
    assert sha(live_directory / "results.json") == demo["results_sha256"]
    assert demo["duration_ms"] == 12000 and demo["frame_count"] == 6
    assert sha(live_directory / "porpoise_replay_demo.gif") == demo["output_sha256"] == review["gif_sha256"]
    assert not review["biological_approval"] and review["all_six_frames_show_actual_porpoise_closeup"]
    assert not live["actor_after_release"]["root_present_on_active_stage"]
    for capture, frame in zip(live["captures"], demo["frames"]):
        assert capture["retained_frame"] == frame["retained_frame"]
        assert sha(live_directory / frame["retained_frame"]) == frame["retained_frame_sha256"]
        assert capture["render_product_camera_verified"]
        assert capture["previous_camera_restored"] and capture["owned_layer_restored"] and capture["controller_gate_restored"]
        for key in ("projection_before_capture", "projection_after_capture"):
            assert capture[key]["render_product"]["camera"] == "/MarlinGamaPorpoise/DiagnosticCamera"
    source = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
    paths = [source / name for name in ("actor.py", "actor_v2.py", "extension.py", "visual_v2.py")]
    paths += [ROOT / "tools" / name for name in ("test_gama_actor_v2.py", "verify_gama_porpoise_live.py", "build_gama_porpoise_demo.py")]
    paths += [ROOT / "integrations/gama/PORPOISE_REPLAY_V2.md",
              ROOT / "experiments/gama_marlin_v1/M4_STATE_TRANSFER_OWNERSHIP_AND_RECOVERY.md",
              QA / "run_m4_checks.py", Path(__file__)]
    for path in sorted(QA.glob("m4*")):
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(p for p in sorted(path.iterdir()) if p.is_file())
    rows = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(set(paths))]
    record = {"milestone": 4, "name": "Verify state transfer, control ownership and recovery",
              "passed": True, "offline_tests": 86, "actual_gama_states_applied_live": 41,
              "cardinal_fixtures_separate_from_gama": 4, "accepted_live_run": "m4_live_03",
              "visual_demo_duration_ms": 12000, "outputs": rows,
              "live_final_bridge_owned": False, "live_final_private_root_present": False,
              "live_final_original_swimmers_running": 11, "live_final_ocean_running": True,
              "biological_approval": False, "pose_mapping": "static_pose_proxy_v1",
              "milestone_5_started": False,
              "prior_evidence_preservation": "m4_final2_offline_results.json"}
    with seal.open("x") as out:
        out.write(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "sealed_outputs": len(rows), "manifest": str(seal)}))


if __name__ == "__main__":
    main()
