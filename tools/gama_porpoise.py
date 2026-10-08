"""Run the real GAMA porpoise model and validate its retained v2 state exports.

Record-first only: no HTTP client, actor acquisition, capture or scene mutation.
Use a new run ID/output directory for every execution, including failed attempts.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "integrations/gama/porpoise_behaviour.gaml"
CONFIG = ROOT / "experiments/gama_marlin_v1/porpoise_model_config.json"
MODULE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
package = types.ModuleType("_gama_porpoise_boundary")
package.__path__ = [str(MODULE)]
sys.modules[package.__name__] = package
exchange = importlib.import_module(package.__name__ + ".exchange_v2")
PARAMETERS = ("step", "path_radius_m", "horizontal_speed_mps", "surface_depth_m",
              "shallow_depth_m", "submerged_depth_m", "initial_surface_s",
              "shallow_swim_s", "descent_s", "submerged_swim_s", "ascent_s", "final_surface_s")
DURATIONS = PARAMETERS[6:]
OUTPUTS = ("schema_version", "run_id", "agent_id", "species", "vertical_reference",
           "agent_count", "step_index", "simulation_time_s", "simulation_step_s",
           "actual_seed", "initial_phase_deg", "behavioural_state", "x_m", "z_m",
           "heading_deg", "speed_mps", "depth_m", *PARAMETERS[1:3], *PARAMETERS[3:])
# horizontal_speed_mps is exported as speed_mps, so avoid a second name for it.
OUTPUTS = tuple(dict.fromkeys(n for n in OUTPUTS if n != "horizontal_speed_mps"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_config(config):
    p = config["parameters"]
    if set(p) != set(PARAMETERS):
        raise ValueError("Unexpected or missing model parameters")
    for name, value in p.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not p["surface_depth_m"] < p["shallow_depth_m"] < p["submerged_depth_m"]:
        raise ValueError("Engineering depths must increase surface < shallow < submerged")
    for name in DURATIONS:
        ratio = p[name] / p["step"]
        if not math.isfinite(ratio) or ratio < 1 or not math.isclose(ratio, round(ratio), rel_tol=0, abs_tol=1e-9):
            raise ValueError("Each state duration must be a positive whole number of simulation steps")
    samples = round(sum(p[n] for n in DURATIONS) / p["step"]) + 1
    if not 7 <= samples <= 10000:
        raise ValueError("Demonstration must have 7..10000 samples")
    for name in ("position_m", "heading_deg", "depth_m", "speed_mps", "clock_s"):
        value = config["tolerances"][name]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Tolerances must be finite and positive")
    if config["experiment"] != "record_porpoise" or config["biological_approval"] is not False:
        raise ValueError("Only the unapproved engineering demonstration is supported")
    return samples


def expected_vertical(t, p):
    """Independent acceptance oracle only; never substitutes for exported states."""
    elapsed = 0.0
    phases = (("surface", "initial_surface_s", "surface_depth_m", "surface_depth_m"),
              ("shallow_swim", "shallow_swim_s", "surface_depth_m", "shallow_depth_m"),
              ("descent", "descent_s", "shallow_depth_m", "submerged_depth_m"),
              ("submerged_swim", "submerged_swim_s", "submerged_depth_m", "submerged_depth_m"),
              ("ascent", "ascent_s", "submerged_depth_m", "surface_depth_m"))
    for state, duration, start, finish in phases:
        if t < elapsed + p[duration]:
            u = (t - elapsed) / p[duration]
            return state, p[start] + (p[finish] - p[start]) * u*u*(3 - 2*u)
        elapsed += p[duration]
    return "surface", p["surface_depth_m"]


def read_trajectory(path, config, run_id, seed):
    count = validate_config(config)
    p, tol = config["parameters"], config["tolerances"]
    tree = ET.parse(path).getroot()
    entries = tree.findall("Step")
    if tree.tag != "Simulation" or len(entries) != count:
        raise ValueError(f"Expected one complete {count}-sample GAMA Simulation")
    snapshots, transitions = [], []
    buffer = exchange.StepBuffer()
    errors = {"radius_m": 0.0, "heading_deg": 0.0, "depth_m": 0.0,
              "horizontal_chord_m": 0.0, "clock_s": 0.0}
    phase = None
    previous_position = None
    for index, entry in enumerate(entries):
        values = {}
        for variable in entry.findall("Variable"):
            name = variable.attrib["name"]
            if name in values:
                raise ValueError(f"Duplicate exported variable: {name}")
            values[name] = variable.text if variable.text is not None else variable.attrib.get("value")
        if set(values) != set(OUTPUTS):
            raise ValueError(f"Unexpected GAMA variables: missing={set(OUTPUTS)-values.keys()}, extra={values.keys()-set(OUTPUTS)}")

        def number(name):
            value = float(values[name])
            if not math.isfinite(value):
                raise ValueError(f"Non-finite GAMA output: {name}")
            return value

        if int(entry.attrib["id"]) != index or number("step_index") != index:
            raise ValueError("Raw GAMA step index must be contiguous from zero")
        actual_seed = number("actual_seed")
        if actual_seed != seed or not actual_seed.is_integer():
            raise ValueError("Actual exported GAMA seed differs from requested seed")
        if number("agent_count") != 1 or values["run_id"] != run_id:
            raise ValueError("GAMA must export exactly one agent and the requested run ID")
        for name in PARAMETERS:
            output_name = {"step": "simulation_step_s", "horizontal_speed_mps": "speed_mps"}.get(name, name)
            if number(output_name) != p[name]:
                raise ValueError(f"Effective GAMA parameter differs from configuration: {name}")
        if phase is None:
            phase = number("initial_phase_deg")
            if not 0 <= phase < 360:
                raise ValueError("Initial phase is outside [0,360)")
        elif number("initial_phase_deg") != phase:
            raise ValueError("Initial phase changed during the run")
        snapshot = {"schema_version": values["schema_version"], "run_id": values["run_id"],
                    "step_index": index, "simulation_time_s": number("simulation_time_s"),
                    "simulation_step_s": number("simulation_step_s"), "seed": int(actual_seed),
                    "agents": [{"agent_id": values["agent_id"], "species": values["species"],
                                "behavioural_state": values["behavioural_state"],
                                "horizontal_position_m": [number("x_m"), number("z_m")],
                                "heading_deg": number("heading_deg"), "speed_mps": number("speed_mps"),
                                "vertical_reference": values["vertical_reference"], "depth_m": number("depth_m")}]}
        buffer.accept(snapshot)
        agent = snapshot["agents"][0]
        t = snapshot["simulation_time_s"]
        clock_error = abs(t - index*p["step"])
        errors["clock_s"] = max(errors["clock_s"], clock_error)
        if clock_error > tol["clock_s"]:
            raise ValueError("Exported simulation clock differs from configured step")
        state, expected_depth = expected_vertical(t, p)
        errors["depth_m"] = max(errors["depth_m"], abs(agent["depth_m"] - expected_depth))
        if agent["behavioural_state"] != state or errors["depth_m"] > tol["depth_m"]:
            raise ValueError("Exported state or depth differs from declared timed model")
        if not transitions or transitions[-1]["state"] != state:
            transitions.append({"state": state, "step_index": index, "simulation_time_s": t})
        x, z = agent["horizontal_position_m"]
        radius = math.hypot(x, z)
        errors["radius_m"] = max(errors["radius_m"], abs(radius - p["path_radius_m"]))
        heading = math.degrees(math.atan2(z, -x)) % 360
        errors["heading_deg"] = max(errors["heading_deg"], abs((agent["heading_deg"] - heading + 180) % 360 - 180))
        expected_angle = math.radians(phase) + p["horizontal_speed_mps"] * t / p["path_radius_m"]
        if max(abs(x-p["path_radius_m"]*math.sin(expected_angle)), abs(z-p["path_radius_m"]*math.cos(expected_angle))) > tol["position_m"]:
            raise ValueError("Exported position differs from seeded continuous trajectory")
        if previous_position is not None:
            chord = math.hypot(x-previous_position[0], z-previous_position[1])
            expected_chord = 2*p["path_radius_m"]*math.sin(p["horizontal_speed_mps"]*p["step"]/(2*p["path_radius_m"]))
            errors["horizontal_chord_m"] = max(errors["horizontal_chord_m"], abs(chord-expected_chord))
        previous_position = (x, z)
        snapshots.append(snapshot)
    if errors["radius_m"] > tol["position_m"] or errors["horizontal_chord_m"] > tol["position_m"] or errors["heading_deg"] > tol["heading_deg"]:
        raise ValueError("Radius, continuous horizontal movement or tangent heading failed")
    if [row["state"] for row in transitions] != ["surface", "shallow_swim", "descent", "submerged_swim", "ascent", "surface"]:
        raise ValueError("Incomplete behavioural state sequence")
    return snapshots, {"passed": True, "samples": count, "transitions": transitions,
                       "initial_phase_deg": phase, "maximum_errors": errors,
                       "depth_range_m": [min(s["agents"][0]["depth_m"] for s in snapshots),
                                         max(s["agents"][0]["depth_m"] for s in snapshots)],
                       "biological_approval": False}


def canonical_states(snapshots):
    # Run identity differs across fresh processes; all scientific state fields stay.
    return json.dumps([{k: v for k, v in s.items() if k != "run_id"} for s in snapshots],
                      sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path, data):
    with path.open("x") as f:
        f.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def execute(run_id, seed, output):
    exchange._identifier(run_id, "run_id")
    if type(seed) is not int or not 0 <= seed <= 2**31-1:
        raise ValueError("This GAML model accepts integer seeds in [0,2^31-1]")
    config = json.loads(CONFIG.read_text())
    count = validate_config(config)
    launcher = shutil.which("gama-headless")
    if launcher is None:
        raise RuntimeError("Installed gama-headless launcher not found")
    if output.exists():
        raise ValueError("Run output already exists; choose a new output/run ID")
    workspace = ROOT / "artifacts/gama_marlin_v1/workspaces" / run_id
    if workspace.exists():
        raise ValueError("Run workspace already exists; choose a new run ID")
    calibration = json.loads((ROOT / config["asset_calibration_record"]).read_text())
    asset = ROOT / calibration["asset"]["path"]
    if sha(asset) != calibration["asset"]["sha256"]:
        raise ValueError("Existing porpoise asset differs from Pilot calibration")
    output.mkdir(parents=True)
    workspace.mkdir(parents=True)
    shutil.copy2(MODEL, output / "model.gaml")
    write_json(output / "configuration.json", {"configuration": config, "run_id": run_id, "requested_seed": seed})
    plan = ET.Element("Experiment_plan")
    sim = ET.SubElement(plan, "Simulation", id="0", sourcePath=str(output / "model.gaml"),
                        finalStep=str(count), experiment=config["experiment"], seed=str(seed))
    params = ET.SubElement(sim, "Parameters")
    for name, value in {**config["parameters"], "requested_seed": seed, "exchange_run_id": run_id}.items():
        kind = "STRING" if isinstance(value, str) else "INT" if type(value) is int else "FLOAT"
        ET.SubElement(params, "Parameter", var=name, type=kind, value=str(value))
    outputs = ET.SubElement(sim, "Outputs")
    for i, name in enumerate(OUTPUTS):
        ET.SubElement(outputs, "Output", id=str(i), name=name, framerate="1")
    ET.indent(plan)
    plan_path = output / "experiment.xml"
    ET.ElementTree(plan).write(plan_path, encoding="utf-8", xml_declaration=True)
    raw = output / "raw"
    command = [launcher, "-m", "1024m", "-ws", str(workspace), str(plan_path), str(raw)]
    runtime_config = Path("/opt/gama-platform/configuration/config.ini")
    runtime = dict(line.split("=", 1) for line in runtime_config.read_text().splitlines()
                   if line.startswith(("gama.version=", "gama.commit=", "gama.jdk=")))
    report = {"status": "started", "run_id": run_id, "requested_seed": seed,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "command": command, "cwd": str(ROOT), "runtime": runtime,
              "launcher": str(Path(launcher).resolve()), "launcher_sha256": sha(Path(launcher)),
              "runtime_configuration_sha256": sha(runtime_config),
              "model_source": str(MODEL.relative_to(ROOT)), "model_sha256": sha(MODEL),
              "configuration_sha256": sha(CONFIG), "experiment_plan_sha256": sha(plan_path),
              "asset_calibration_sha256": sha(ROOT / config["asset_calibration_record"]),
              "asset_sha256": sha(asset), "biological_approval": False,
              "marlin_http_used": False, "scene_actor_acquired": False}
    start = time.monotonic()
    try:
        with (output / "launcher.log").open("x") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        report["return_code"] = result.returncode
        if result.returncode:
            raise RuntimeError("GAMA failed; see retained launcher.log and raw outputs")
        raw_path = raw / "simulation-outputs0.xml"
        states, validation = read_trajectory(raw_path, config, run_id, seed)
        if sha(output / "model.gaml") != report["model_sha256"] or sha(MODEL) != report["model_sha256"] or sha(CONFIG) != report["configuration_sha256"]:
            raise RuntimeError("Model/configuration changed during execution")
        write_json(output / "trajectory.json", states)
        write_json(output / "validation.json", validation)
        report.update(status="passed", actual_seed=states[0]["seed"],
                      canonical_state_sha256=hashlib.sha256(canonical_states(states)).hexdigest(),
                      canonical_comparison_excluded_fields=["run_id"], samples=len(states),
                      raw_xml_sha256=sha(raw_path), trajectory_sha256=sha(output / "trajectory.json"))
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        report["elapsed_wall_time_s"] = time.monotonic() - start
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "execution.json", report)
    print(json.dumps(report, indent=2))
    return report["status"] == "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=184729)
    parser.add_argument("--output", type=Path, help="New directory; defaults to this sprint's trajectories/run-id")
    args = parser.parse_args()
    output = (args.output or ROOT / "experiments/gama_marlin_v1/trajectories" / args.run_id).resolve()
    if not execute(args.run_id, args.seed, output):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
