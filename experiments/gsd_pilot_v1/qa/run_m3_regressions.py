"""Reuse baseline runner with isolated M3 outputs; preserve original audit bytes."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_baseline
run_baseline.OUT=Path(__file__).resolve().parent/'m3_regressions'
run_baseline.OUT.mkdir(exist_ok=True)
run_baseline.main()
