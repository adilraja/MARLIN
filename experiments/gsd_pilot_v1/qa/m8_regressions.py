"""Run final read-only regression suites into new M8 evidence files."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
PYTHON = REPO / "artifacts/gsd_pilot_v1_m6/venv/bin/python"
BLENDER = Path("/home/madil/opt/blender-5.0.1-linux-x64/blender")
TESTS = "source/extensions/cris.madil.render_service/cris/madil/render_service/tests"


def run(name, command):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(arg) for arg in command], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=300)
    path = EXP / f"qa/m8_regression_{name}.log"
    path.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f"{name} failed with {result.returncode}: {result.stdout[-2000:]}")
    test_count = re.search(r"Ran (\d+) tests?", result.stdout)
    return {"command": [str(arg) for arg in command], "return_code": result.returncode,
            "tests": int(test_count.group(1)) if test_count else None,
            "log": str(path.relative_to(EXP)),
            "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    results = {}
    results["blender_usd_service_suite"] = run("blender_usd", [
        BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
        "--python-expr",
        "import unittest; suite=unittest.defaultTestLoader.discover('" + TESTS +
        "',pattern='test_*.py'); result=unittest.TextTestRunner(verbosity=1).run(suite); assert result.wasSuccessful()",
    ])
    assert results["blender_usd_service_suite"]["tests"] == 77
    results["reconstruction_contract"] = run("reconstruction", [
        sys.executable, "-B", "experiments/gsd_pilot_v1/qa/test_reconstruction_contract.py",
    ])
    assert results["reconstruction_contract"]["tests"] == 8
    results["detection_metrics_contract"] = run("metrics", [
        sys.executable, "-B", "experiments/gsd_pilot_v1/ml/metrics.py",
    ])
    results["m7_historical_package"] = run("m7_package", [
        sys.executable, "-B", "experiments/gsd_pilot_v1/qa/m7_package.py",
    ])
    assert "sealed_manifest_verified" in (EXP / "qa/m8_regression_m7_package.log").read_text()
    report = {"passed": True, "read_only_against_M1_to_M7_evidence": True,
              "service_tests": 77, "reconstruction_contract_tests": 8,
              "results": results}
    (EXP / "qa/m8_regression_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "service_tests": 77,
                      "reconstruction_contract_tests": 8}, indent=2))


if __name__ == "__main__":
    main()
