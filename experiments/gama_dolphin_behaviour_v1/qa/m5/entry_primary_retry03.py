"""Finite primary-02 run under the retained, clarified capture-state protocol."""
import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_marlin_m5_native_v4', ROOT/'native_m5.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
_m5_finite_task = asyncio.ensure_future(native.main('primary02', 'primary'))
