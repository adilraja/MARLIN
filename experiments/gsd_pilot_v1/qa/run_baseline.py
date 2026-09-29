"""Run existing offline MARLIN regressions without importing Kit or writing bytecode.

Run with the official Blender Python runtime described in ../README.md.
This audits existing tests; it does not certify live rendering or biology.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXTENSION = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({"test": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({"test": test.id(), "status": "error"})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({"test": test.id(), "status": "skipped", "reason": reason})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("usd", "image"), default="usd")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    # Blender owns its command-line flags before the separator.
    if "bpy" in sys.modules and "--" not in sys.argv:
        argv = []
    args = parser.parse_args(argv)
    sys.path[:0] = [str(EXTENSION), str(EXTENSION / "tests"), str(ROOT / "tools")]
    suite = unittest.TestSuite()
    image_modules = {"test_gama_counterfactual", "test_tile_diagnostics"}
    if args.suite == "usd":
        for path in sorted((EXTENSION / "tests").glob("test_*.py")):
            suite.addTests(unittest.TestLoader().loadTestsFromName(path.stem))
    for path in sorted((ROOT / "tools").glob("test_*.py")):
        if (path.stem in image_modules) == (args.suite == "image"):
            suite.addTests(unittest.TestLoader().loadTestsFromName(path.stem))
    with (OUT / ("baseline_" + args.suite + ".log")).open("w") as stream:
        result = unittest.TextTestRunner(
            stream=stream, verbosity=2, resultclass=RecordedResult
        ).run(suite)
    packages = {}
    for name in ("numpy", "pillow", "torch", "torchvision", "ultralytics"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        from pxr import Usd
        usd_version = list(Usd.GetVersion())
    except ImportError:
        usd_version = None
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runtime": {"python": sys.version, "platform": platform.platform(),
                    "usd_version": usd_version, "packages": packages},
        "suite": args.suite,
        "scope": "Existing offline extension and top-level tool regressions; no live Kit/render certification",
        "tests_run": result.testsRun,
        "passed": sum(item["status"] == "passed" for item in result.records),
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "successful": result.wasSuccessful(),
        "records": result.records,
    }
    (OUT / ("baseline_" + args.suite + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    if not result.wasSuccessful():
        raise RuntimeError("MARLIN baseline failures: see qa/baseline_" + args.suite + ".log")


if __name__ == "__main__":
    main()
