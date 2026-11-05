"""Finite M5 fresh-process replay job; no job poller remains after completion."""
import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_marlin_m5_native', ROOT/'native_m5.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
_m5_finite_task = asyncio.ensure_future(native.main('fresh01', 'fresh'))
