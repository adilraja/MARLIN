"""Create standalone scientific M5 figures from retained, verified records.

Run with /usr/bin/python3 -B. No GAMA launch, HTTP request, Kit operation or
source-image modification occurs. Existing M4 rendered poses are reused only
after exact canonical equality to the representative actual M5 trajectory and
verification against the sealed M4 manifest and original raw-image hashes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ["MPLCONFIGDIR"] = "/tmp/marlin-m5-mpl"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

import analyze_gama_porpoise as analyzer
import gama_porpoise as runner

ROOT = runner.ROOT
STATE_COLORS = {"surface": "#75b9c7", "shallow_swim": "#7bb89c", "descent": "#e0ac69",
                "submerged_swim": "#8b9dce", "ascent": "#ca91b4"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .2,
                     "svg.fonttype": "none", "savefig.dpi": 180})


def _resolve(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Evidence paths must stay inside the repository")
    return path


def _record(path):
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": runner.sha(path)}


def _read(path, inputs):
    inputs[str(path)] = _record(path)
    return json.loads(path.read_text())


def _verified_poses(analysis, representative, plan, inputs):
    source = analysis["representative_pose_source"]
    if source.get("canonical_equal_to_m5") is not True or source.get("m5_run_id") != representative["run_id"]:
        raise ValueError("Analysis did not establish representative M5/M4 state equality")
    manifest_path = ROOT / "experiments/gama_marlin_v1/qa/milestone_4_manifest.json"
    manifest = _read(manifest_path, inputs)
    sealed = {entry["path"]: entry for entry in manifest["outputs"]}

    def sealed_file(path):
        key = str(path.relative_to(ROOT))
        actual = _record(path)
        if key not in sealed or actual["sha256"] != sealed[key]["sha256"] or actual["bytes"] != sealed[key]["bytes"]:
            raise ValueError(f"M4 sealed evidence mismatch: {key}")
        inputs[str(path)] = actual

    results_path = _resolve(source["path"])
    sealed_file(results_path)
    if runner.sha(results_path) != source["source_results_sha256"]:
        raise ValueError("Analysis/M4 result hash mismatch")
    results = _read(results_path, inputs)
    sidecar_path = results_path.parent / "porpoise_replay_demo.json"
    sealed_file(sidecar_path)
    sidecar = _read(sidecar_path, inputs)
    trajectory_path = _resolve(source["trajectory"])
    trajectory = _read(trajectory_path, inputs)
    if results.get("passed") is not True or len(results["captures"]) != 6:
        raise ValueError("Expected the accepted six-pose M4 live run")
    if _resolve(results["trajectory"]) != trajectory_path or sidecar["trajectory"] != results["trajectory"]:
        raise ValueError("M4 pose trajectory identity mismatch")
    if runner.sha(trajectory_path) != results["trajectory_sha256"] or sidecar["trajectory_sha256"] != results["trajectory_sha256"] or sidecar["results_sha256"] != runner.sha(results_path):
        raise ValueError("M4 trajectory/result provenance hash mismatch")
    if runner.canonical_states(trajectory) != runner.canonical_states(representative["states"]):
        raise ValueError("Actual M5 representative states differ from M4's source GAMA states")
    if results["acquired"]["calibration"]["asset_sha256"] != plan["pins"]["asset_sha256"]:
        raise ValueError("M4 and pinned M5 assets differ")
    if results["acquired"].get("pose_mapping") != "static_pose_proxy_v1":
        raise ValueError("Expected the documented unchanged static pose proxy")
    frames = {frame["retained_frame"]: frame for frame in sidecar["frames"]}
    captures = []
    for capture in results["captures"]:
        path = results_path.parent / capture["retained_frame"]
        sealed_file(path)
        frame = frames[capture["retained_frame"]]
        if runner.sha(path) != frame["retained_frame_sha256"]:
            raise ValueError("Raw pose image hash mismatch")
        step = capture["gama_state"]
        if step != trajectory[step["step_index"]] or step["step_index"] != frame["step_index"] or step["simulation_time_s"] != frame["simulation_time_s"]:
            raise ValueError("Rendered pose is not linked to its source GAMA step")
        if capture.get("render_product_camera_verified") is not True or capture.get("ok") is not True:
            raise ValueError("Pose did not verify its actual capture camera")
        captures.append({"path": path, "state": step, "raw_sha256": runner.sha(path)})
    return captures, {"source": str(results_path.relative_to(ROOT)),
                      "source_results_sha256": runner.sha(results_path),
                      "m3_trajectory": str(trajectory_path.relative_to(ROOT)),
                      "canonical_state_sha256": hashlib.sha256(runner.canonical_states(trajectory)).hexdigest(),
                      "m5_run_id": representative["run_id"], "canonical_equal_to_m5": True,
                      "new_m5_kit_capture": False, "pose_mapping": "static_pose_proxy_v1",
                      "frames": [{"path": str(item["path"].relative_to(ROOT)), "sha256": item["raw_sha256"],
                                  "step_index": item["state"]["step_index"], "simulation_time_s": item["state"]["simulation_time_s"],
                                  "state": item["state"]["agents"][0]["behavioural_state"]} for item in captures]}


def _save(fig, output, stem, outputs):
    for suffix in ("png", "svg"):
        path = output / f"{stem}.{suffix}"
        fig.savefig(path, facecolor="white")
        outputs.append(_record(path))
    plt.close(fig)


def _trajectories(primary, output, outputs):
    fig, ax = plt.subplots(figsize=(11.5, 8))
    colors = plt.get_cmap("tab10")
    for i, run in enumerate(primary):
        positions = [step["agents"][0]["horizontal_position_m"] for step in run["states"]]
        x, z = zip(*positions)
        color = colors(i)
        ax.plot(x, z, color=color, linewidth=1.8,
                label=f"Seed {run['seed']}  |  phase {run['initial_phase_deg']:.3f}°")
        ax.scatter([x[0]], [z[0]], color=color, edgecolor="black", linewidth=.6, s=48, zorder=4)
    ax.set(xlabel="X (m)", ylabel="Z (m)", xlim=(-9, 9), ylim=(-9, 9),
           title="Ten actual GAMA trajectories: seed varied initial phase only")
    ax.set_aspect("equal", adjustable="box")
    ax.axhline(0, color="#777777", linewidth=.6, alpha=.6)
    ax.axvline(0, color="#777777", linewidth=.6, alpha=.6)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False, fontsize=9)
    fig.text(.08, .04, "Dots mark t = 0 s. Each 20 s record contains 41 samples at 0.5 s intervals.\n"
             "Engineering model; these traces do not establish wild-animal distributions or biological suitability.", fontsize=9)
    fig.subplots_adjust(left=.08, right=.66, bottom=.13, top=.92)
    _save(fig, output, "m5_ten_seed_trajectories", outputs)


def _depth(representative, output, outputs):
    states, measured = representative["states"], representative["metrics"]
    times = [state["simulation_time_s"] for state in states]
    depths = [state["agents"][0]["depth_m"] for state in states]
    fig, (ax, timeline) = plt.subplots(2, 1, figsize=(12, 6.8), sharex=True,
                                      gridspec_kw={"height_ratios": [4, 1]})
    for episode in measured["episodes"]:
        ax.axvspan(episode["start_s"], episode["end_s"], color=STATE_COLORS[episode["state"]], alpha=.18)
        timeline.barh(.5, episode["duration_s"], left=episode["start_s"], height=.85,
                      color=STATE_COLORS[episode["state"]], edgecolor="white")
        text = episode["state"].replace("_", "\n") + f"\n{episode['duration_s']:g} s"
        if episode["right_censored"]:
            text += " observed*"
        timeline.text((episode["start_s"] + episode["end_s"]) / 2, .5, text,
                      ha="center", va="center", fontsize=8)
    ax.plot(times, depths, color="#17495b", marker="o", markersize=3, linewidth=1.8)
    ax.set(ylabel="Motion-root depth below mean sea level (m)", ylim=(3.3, -.1),
           title="Representative seed 184729: measured depth and state exposure")
    ax.text(.01, .04, "Positive depth points down; fixed Y = 0 datum.\nBody clearance and instantaneous wave clearance were not measured.",
            transform=ax.transAxes, fontsize=9, bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none"})
    timeline.set(xlabel="Simulation time (s)", xlim=(0, 20), ylim=(0, 1), yticks=[])
    timeline.grid(False)
    fig.text(.08, .025, "* Final surface episode was right-censored at 20 s; the FSM did not exit this state. Exposure used [tᵢ, tᵢ₊₁) intervals.\n"
             "All durations and depths were engineering assumptions; balanced state coverage does not estimate natural occupancy.", fontsize=9)
    fig.subplots_adjust(left=.09, right=.98, bottom=.15, top=.92, hspace=.08)
    _save(fig, output, "m5_representative_depth_and_states", outputs)


def _rates(representative, output, outputs):
    states, measured = representative["states"], representative["metrics"]
    intervals = measured["interval_series"]
    midpoints = [(row["start_s"] + row["end_s"]) / 2 for row in intervals]
    fig, (speed, turn) = plt.subplots(2, 1, figsize=(12, 7.4), sharex=True)
    speed.plot(midpoints, [r["three_dimensional_chord_speed_mps"] for r in intervals],
               color="#72558d", linewidth=1.8, label="Measured 3D chord speed (includes vertical movement)")
    speed.plot([s["simulation_time_s"] for s in states], [s["agents"][0]["speed_mps"] for s in states],
               color="#c96537", linewidth=2, label="GAMA instantaneous horizontal speed metadata")
    speed.plot(midpoints, [r["horizontal_chord_speed_mps"] for r in intervals],
               color="#237c89", linestyle="--", linewidth=1.5, label="Measured horizontal chord speed")
    speed.set(ylabel="Speed (m/s)", ylim=(0, 1.3), title="Representative seed 184729: measured speed and circular turning")
    speed.legend(loc="upper left", frameon=False, fontsize=9)
    difference = measured["exported_speed_mps"]["mean"] - measured["horizontal_chord_speed_mps"]["mean"]
    speed.text(.99, .07, f"Chord sampling lowered horizontal speed by {difference:.8f} m/s.\n"
               "The overlapping horizontal curves represent different quantities.", transform=speed.transAxes,
               ha="right", va="bottom", fontsize=9)
    turn.plot(midpoints, [r["turn_rate_deg_per_s"] for r in intervals], color="#237c89", marker="o", markersize=3)
    expected = measured["expected_turn_rate_deg_per_s"]
    turn.axhline(expected, color="#c96537", linestyle="--", linewidth=1, label=f"Declared v/R = {expected:.6f}°/s")
    turn.set(xlabel="Simulation time (s)", ylabel="Signed circular heading rate (°/s)", xlim=(0, 20),
             ylim=(expected - .03, expected + .03))
    turn.legend(loc="upper right", frameon=False)
    turn.text(.01, .09, "Heading differences were wrapped to [−180°, 180°).\nPositive heading followed +Z toward +X; no angular discontinuity was introduced at 360°.",
              transform=turn.transAxes, fontsize=9)
    fig.text(.08, .025, "Recorded 0.5 s intervals; finite differences are sampled secants. The instantaneous horizontal metadata did not include vertical speed.\n"
             "These fixed engineering rates were not validated against animal observations.", fontsize=9)
    fig.subplots_adjust(left=.09, right=.98, bottom=.15, top=.92, hspace=.24)
    _save(fig, output, "m5_representative_speed_and_turning", outputs)


def _poses(captures, output, outputs):
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.7))
    for ax, capture in zip(axes.flat, captures):
        state = capture["state"]
        agent = state["agents"][0]
        with Image.open(capture["path"]) as image:
            ax.imshow(image.convert("RGB"))
        ax.axis("off")
        label = agent["behavioural_state"].replace("_", " ")
        ax.set_title(f"t = {state['simulation_time_s']:g} s  |  {label}\n"
                     f"Root depth {agent['depth_m']:.3f} m  |  heading {agent['heading_deg']:.2f}°", fontsize=10)
    fig.suptitle("Recorded MARLIN static pose proxy — six actual M4 renders", fontsize=15, y=.98)
    fig.text(.5, .935, "Seed 184729 matched the new M5 GAMA states exactly; these were existing renders, not new M5 Kit captures.", ha="center", fontsize=10)
    fig.text(.03, .025, "Camera followed the animal, using temporary below-surface diagnostic lighting; identical screen placement does not imply a stationary trajectory.\n"
             "All five labels used the same upright static mesh. Body animation, dive pitch, breathing and anatomical water clearance remained unvalidated.\n"
             "Source: experiments/gama_marlin_v1/qa/m4_live_03/results.json; original PNG hashes and the sealed M4 manifest were verified.", fontsize=9)
    fig.subplots_adjust(left=.02, right=.98, bottom=.14, top=.875, wspace=.04, hspace=.13)
    _save(fig, output, "m5_representative_recorded_poses", outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = {}
    plan = _read(_resolve(args.plan), inputs)
    analysis = _read(_resolve(args.analysis), inputs)
    config = _read(runner.CONFIG, inputs)
    if analysis.get("engineering_passed") is not True:
        raise ValueError("Plot only the accepted engineering campaign analysis")
    primary = []
    primary_ids = [item["run_id"] for item in plan["runs"] if not item["repeat"]]
    runs = {item["run_id"]: item for item in analysis["runs"]}
    if len(primary_ids) != 10 or len(set(primary_ids)) != 10:
        raise ValueError("The declared plan must contain ten distinct primary runs")
    for run_id in primary_ids:
        run = dict(runs[run_id])
        directory = _resolve(run["directory"])
        execution = _read(directory / "execution.json", inputs)
        states = _read(directory / "trajectory.json", inputs)
        validation = _read(directory / "validation.json", inputs)
        if execution.get("status") != "passed" or execution["run_id"] != run_id or execution["actual_seed"] != run["seed"]:
            raise ValueError("Primary run execution identity mismatch")
        if runner.sha(directory / "trajectory.json") != execution["trajectory_sha256"]:
            raise ValueError("Primary trajectory hash mismatch")
        if hashlib.sha256(runner.canonical_states(states)).hexdigest() != run["canonical_sha256"]:
            raise ValueError("Primary analysis canonical hash mismatch")
        for key in ("runtime", "launcher_sha256", "runtime_configuration_sha256", "model_sha256", "configuration_sha256", "asset_calibration_sha256", "asset_sha256"):
            if execution[key] != plan["pins"][key]:
                raise ValueError(f"Primary execution pin mismatch: {key}")
        measured = analyzer.metrics(states, config)
        if not measured["passed"] or measured != run["metrics"]:
            raise ValueError("Measured metrics disagree with accepted analysis")
        if validation["initial_phase_deg"] != run["initial_phase_deg"]:
            raise ValueError("Initial phase does not match retained GAMA validation")
        run.update(states=states)
        primary.append(run)
    if [run["seed"] for run in primary] != plan["seeds"]:
        raise ValueError("Primary plot seeds differ from declared order")
    representative = next(run for run in primary if run["seed"] == 184729)
    captures, pose_provenance = _verified_poses(analysis, representative, plan, inputs)
    output = _resolve(args.output)
    if output.exists():
        raise ValueError("Figure output exists; choose a new output directory")
    output.mkdir(parents=True)
    outputs = []
    _trajectories(primary, output, outputs)
    _depth(representative, output, outputs)
    _rates(representative, output, outputs)
    _poses(captures, output, outputs)
    manifest = {"milestone": 5, "kind": "scientific_review_figures", "engineering_passed": True,
                "biological_approval": False, "human_review_completed": False,
                "plotter": _record(Path(__file__).resolve()),
                "inputs": list(inputs.values()), "outputs": outputs,
                "representative_pose_provenance": pose_provenance,
                "notes": ["All curves used retained actual GAMA outputs; repeats were not counted as extra independent seeds.",
                          "Rendered poses reused sealed M4 evidence only after exact M5/M3 canonical comparison.",
                          "Contact sheets resized images for display; the original raw PNG files were not modified.",
                          "Biological review remained a separate named human decision."]}
    runner.write_json(output / "plot_manifest.json", manifest)
    print(json.dumps({"output": str(output), "figures": len(outputs), "plot_manifest": str(output / "plot_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
