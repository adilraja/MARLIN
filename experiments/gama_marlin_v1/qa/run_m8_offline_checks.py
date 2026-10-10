"""Retain fresh M8 offline MARLIN, camera and GAMA regression evidence.

No Kit connection, GPU capture, simulation execution or training is started.
Canonical source and explicitly listed retained inputs are pinned before/after.
Existing Pilot runners' sealed output filenames are never used for new logs.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
SERVICE = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"
BRIDGE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
USD_PYTHON = Path("/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11")
SYSTEM_PYTHON = Path("/usr/bin/python3")
FORBIDDEN = frozenset(("_build", "extscache", "__pycache__", ".cache"))


def now():
    return datetime.now(timezone.utc).isoformat()


def checked(path):
    path = Path(path)
    if FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated/cache inputs are prohibited")
    resolved = path.resolve()
    if FORBIDDEN.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Input resolves into generated/cache content")
    return resolved


def sha(path):
    value = hashlib.sha256()
    with checked(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def pin(path):
    path = checked(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def jobs():
    service = str(SERVICE.relative_to(ROOT))
    rows = [{"name": "marlin_service", "python": USD_PYTHON,
             "args": ["-m", "unittest", "discover", "-s", service + "/tests", "-p", "test_*.py", "-v"],
             "expected_tests": 77, "category": "existing_marlin_service",
             "scope": "Canonical16-module service suite: actual USD calibration/petrel stages plus pure movement, camera math, settings/AST and retained asset/config checks; no live Kit."}]
    tools = [
        ("hidef_marine", USD_PYTHON, 8, "existing_camera", "Actual USD frozen snapshots and translated camera rays; NumPy maps and fake settings/AST gates."),
        ("sony_camera", USD_PYTHON, 6, "existing_camera", "Independent pinhole/map calculations plus actual USD camera ray projection; no rendered pixels."),
        ("capture_projection", USD_PYTHON, 6, "existing_camera", "Actual USD camera/render-product contracts; fake viewport/UI matrices test resolution, pixel aspect and crop rejection."),
        ("native_tiles", USD_PYTHON, 6, "existing_camera", "Actual USD tile-camera/product projection and exact NumPy pixel coverage; fake viewport settling/reset boundaries."),
        ("tile_diagnostics", SYSTEM_PYTHON, 4, "existing_camera", "Synthetic NumPy/Pillow pixels and evidence-rejection fixtures; no retained render is produced."),
        ("gama_actor", USD_PYTHON, 8, "bridge", "Original actor lifecycle with actual USD layers/transforms; fake capture gate."),
        ("gama_actor_v2", USD_PYTHON, 24, "bridge", "Actual calibrated asset/USD composed poses, ownership/layers, duplicate/reset/guard semantics and bounded cleanup."),
        ("gama_exchange", SYSTEM_PYTHON, 9, "bridge", "Original pure schema/coordinate/replay validation."),
        ("gama_exchange_v2", SYSTEM_PYTHON, 23, "bridge", "V2 pure schema, strict scalar/state identity, coordinate and replay validation."),
        ("gama_live", SYSTEM_PYTHON, 3, "bridge", "Fake transport replay/protocol boundaries; the filename does not imply a live Kit run."),
        ("gama_porpoise", SYSTEM_PYTHON, 11, "bridge", "Retained actual raw GAMA export parsing and explicit invalid XML/state fixtures; no new GAMA process."),
        ("gama_porpoise_analysis", SYSTEM_PYTHON, 14, "bridge", "Measured retained M3 constraints plus explicitly synthetic rotation/mutation analysis fixtures; no biological acceptance."),
        ("gama_v2_stage", USD_PYTHON, 8, "bridge", "Actual USD coordinates/layers with fake Kit Services route/context boundaries."),
        ("gama_paired_state", USD_PYTHON, 20, "capture", "Actual USD freezing, dependency/state/camera hashes and direct geometric GSD/projections."),
        ("gama_paired_transaction", USD_PYTHON, 13, "capture", "Actual USD/PorpoiseActor with fake timeline/viewport/PNG/capture; cleanup, cancellation and unique output-path guards."),
        ("gama_dataset_state", USD_PYTHON, 18, "capture", "Actual USD positive/RemovePrim negative variant, background identity, mesh projection and annotation checks."),
        ("gama_dataset_transaction", USD_PYTHON, 11, "capture", "Actual USD/actor with fake Kit capture/timeline; exact10-view variants and failure/restoration guards."),
        ("gama_dataset_routes", USD_PYTHON, 4, "capture", "Actual route handlers with fake Kit request/context boundaries; no HTTP service started."),
        ("gama_dataset_client", SYSTEM_PYTHON, 42, "capture", "Actual sealed-source plan plus explicit unit annotation/pixel/transport fixtures and injected bounded no-render headroom retries."),
        ("gama_capture_preflight", SYSTEM_PYTHON, 2, "capture", "Fake GPU preflight/garbage collection boundaries; no GPU queried or renderer started."),
        ("gama_dataset_pending", SYSTEM_PYTHON, 31, "capture", "Actual12-group source revalidation and exact3 missing states; test-only report/copy mutation fixtures."),
        ("gama_counterfactual", SYSTEM_PYTHON, 4, "capture", "Explicit synthetic pixel attribution/noise threshold tests; no new render or scientific inference."),
    ]
    rows.extend({"name": name, "python": python, "args": ["tools/test_" + name + ".py", "-v"],
                 "expected_tests": count, "category": category, "scope": scope}
                for name, python, count, category, scope in tools)
    rows.extend([
        {"name": "pilot_reconstruction_contract", "python": SYSTEM_PYTHON,
         "args": ["experiments/gsd_pilot_v1/qa/test_reconstruction_contract.py", "-v"], "expected_tests": 8,
         "category": "existing_pilot", "scope": "Actual pure verifier functions compiled from AST, with explicit reconstruction/preview evidence mutation fixtures."},
        {"name": "pilot_metric_contract", "python": SYSTEM_PYTHON,
         "args": ["experiments/gsd_pilot_v1/ml/metrics.py"], "expected_stdout": "M7 metric contract passed",
         "category": "existing_pilot", "scope": "Existing pure IoU/one-to-one/101-point AP self-test; no model loading, evaluation rerun or training."},
        {"name": "pilot_sealed_package", "python": SYSTEM_PYTHON,
         "args": ["experiments/gsd_pilot_v1/qa/m7_package.py"], "expected_stdout": "sealed_manifest_verified",
         "category": "existing_pilot", "scope": "Existing completed-seal branch only: retained historical package/source/result/checkpoint hashes; no seal or training-output rewrite."},
    ])
    return rows


def execute(out, name, command, env, timeout=180):
    started, clock = now(), time.monotonic()
    try:
        result = subprocess.run([str(arg) for arg in command], cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        stdout, stderr, code, error = result.stdout, result.stderr, result.returncode, None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or ""
        code, error = None, "TimeoutExpired"
    stdout_path, stderr_path = out / (name + ".stdout.log"), out / (name + ".stderr.log")
    for path, value in ((stdout_path, stdout), (stderr_path, stderr)):
        with path.open("x") as stream:
            stream.write(value)
    return {"command": [str(arg) for arg in command], "cwd": str(ROOT), "return_code": code,
            "started_at_utc": started, "ended_at_utc": now(), "elapsed_seconds": time.monotonic() - clock,
            "stdout": pin(stdout_path), "stderr": pin(stderr_path),
            "explicit_environment": {key: env[key] for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONPATH")},
            **({"execution_error": error} if error else {})}, stdout + "\n" + stderr


def run_job(job, out, env):
    result, text = execute(out, job["name"], [job["python"], "-B", *job["args"]], env)
    match = re.search(r"Ran (\d+) tests?", text)
    result.update(name=job["name"], category=job["category"], scope=job["scope"],
                  tests=int(match.group(1)) if match else None,
                  skipped=int(re.search(r"skipped=(\d+)", text).group(1)) if re.search(r"skipped=(\d+)", text) else 0)
    if "expected_tests" in job:
        result["expected_tests"] = job["expected_tests"]
        result["passed"] = result["return_code"] == 0 and result["tests"] == job["expected_tests"] and result["skipped"] == 0
    else:
        result["expected_stdout"] = job["expected_stdout"]
        result["passed"] = result["return_code"] == 0 and job["expected_stdout"] in text
    write(out / (job["name"] + ".execution.json"), result)
    print(json.dumps({"name": result["name"], "passed": result["passed"], "tests": result["tests"],
                      "return_code": result["return_code"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = checked(args.output)
    if not output.is_relative_to(QA) or not output.name.startswith("m8_"):
        raise ValueError("Retain a new m8_* directory under this GAMA QA folder")
    output.mkdir(parents=True, exist_ok=False)
    suite_jobs = jobs()
    # The historical package executable has a write branch only when no seal
    # exists. Require the existing seal and pin it before invoking that check.
    package_seal = ROOT / "experiments/gsd_pilot_v1/qa/milestone_7_manifest.json"
    if not package_seal.is_file():
        raise ValueError("Historical package seal must exist; refusing its creation branch")
    paths = set(SERVICE.glob("*.py")) | set((SERVICE / "tests").glob("test_*.py")) | set(BRIDGE.glob("*.py"))
    paths |= set((ROOT / "tools").glob("*.py")) | set((SERVICE.parents[2] / "config").glob("*.json"))
    paths |= set((BRIDGE.parents[2] / "config").glob("*.json"))
    paths |= set((ROOT / "assets/cetaceans").glob("*/usd/*.usd"))
    paths |= {ROOT / "assets/birds/european_storm_petrel/usd/european_storm_petrel_rigged.usd",
              ROOT / "experiments/gsd_pilot_v1/wildlife/harbour_porpoise.json",
              ROOT / "experiments/gama_marlin_v1/m7_capture_declaration.json",
              ROOT / "experiments/gama_marlin_v1/porpoise_model_config.json"}
    trajectory_root = ROOT / "experiments/gama_marlin_v1/trajectories"
    for name in ("execution.json", "configuration.json", "trajectory.json", "validation.json",
                 "model.gaml", "experiment.xml", "raw/simulation-outputs0.xml"):
        paths |= set(trajectory_root.glob("*/" + name))
    paths |= {Path(__file__), package_seal, ROOT / "AGENTS.md",
              ROOT / "Codex-Instructions/Current-Sprint/GAMA_MARLIN_SPRINT_SPECIFICATION.md",
              ROOT / "experiments/gsd_pilot_v1/qa/test_reconstruction_contract.py",
              ROOT / "experiments/gsd_pilot_v1/qa/verify_m3_reconstruction.py",
              ROOT / "experiments/gsd_pilot_v1/qa/m7_package.py", ROOT / "experiments/gsd_pilot_v1/ml/metrics.py",
              QA / "m7_live_02/results.json", QA / "m7_live_02/declaration.json"}
    before = [pin(path) for path in sorted(paths)]
    write(output / "source_pins_before.json", before)
    syntax = []
    for path in sorted(paths):
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
            syntax.append(pin(path))
    write(output / "job_inventory.json", [{**job, "python": str(job["python"])} for job in suite_jobs])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SERVICE))
    runtime_source = "import json,platform,sys; from importlib import metadata; result={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{}}\nfor name in ('numpy','pillow'):\n try: result['packages'][name]=metadata.version(name)\n except metadata.PackageNotFoundError: result['packages'][name]=None\ntry:\n from pxr import Usd\n result['usd_version']=list(Usd.GetVersion())\nexcept ImportError: result['usd_version']=None\nprint(json.dumps(result))"
    runtimes = {}
    for name, python in (("system", SYSTEM_PYTHON), ("blender_usd", USD_PYTHON)):
        runtime, text = execute(output, "runtime_" + name, [python, "-B", "-c", runtime_source], env, 30)
        runtime["executable_pin"] = pin(python)
        runtime["reported_runtime"] = json.loads(text.strip()) if runtime["return_code"] == 0 else None
        runtimes[name] = runtime
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_job, job, output, env) for job in suite_jobs]
        for future in as_completed(futures):
            results.append(future.result())
    order = {job["name"]: index for index, job in enumerate(suite_jobs)}
    results.sort(key=lambda row: order[row["name"]])
    after = [pin(path) for path in sorted(paths)]
    write(output / "source_pins_after.json", after)
    diff, _ = execute(output, "git_diff_check", ["git", "diff", "--check"], env, 30)
    report = {"kind": "m8_offline_regression_execution", "milestone": 8, "recorded_at_utc": now(),
              "runner_command": [sys.executable, "-B", *sys.argv], "runtimes": runtimes, "results": results,
              "total_unittest_cases": sum(row["tests"] or 0 for row in results),
              "additional_passed_contract_checks": sum(row["tests"] is None and row["passed"] for row in results),
              "source_pins_unchanged": before == after, "source_pin_count": len(before),
              "python_syntax_checked": syntax, "git_diff_check": diff,
              "live_kit_calls_made": False, "new_gpu_renders": 0, "new_gama_executions": 0, "ml_training_started": False,
              "biological_approval": False, "live_marine_demonstration_certified_by_this_command": False,
              "live_mutating_runner_left_to_root": {"path": "tools/verify_gama_marine.py",
                  "requirements": "Already running11gallery swimmers and ocean; actor acquire, actual trajectory step replay, GPU capture, release and after-cleanup audits. Not executed by this offline command."},
              "historical_runner_not_executed": {"path": "experiments/gsd_pilot_v1/qa/m8_regressions.py",
                  "reason": "Its logs/report target sealed Pilot filenames; equivalent checks ran into this new directory."}}
    report["passed"] = (all(row["passed"] for row in results) and before == after and diff["return_code"] == 0
                         and all(row["return_code"] == 0 for row in runtimes.values()))
    write(output / "results.json", report)
    print(json.dumps({"passed": report["passed"], "tests": report["total_unittest_cases"],
                      "additional_checks": report["additional_passed_contract_checks"], "report": str(output / "results.json")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
