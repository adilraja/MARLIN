"""Finite metadata-only Kit audit; does not enable annotators or author a scene."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback

OUT = Path(__file__).resolve().parents[2] / 'baseline' / 'runtime_query.json'


async def main():
    import omni.kit.app
    app = omni.kit.app.get_app()
    report = dict(schema_version=1, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  pid=os.getpid(), scope='Isolated metadata-only process; no live MARLIN scene existed',
                  annotators_enabled_by_probe=False, scene_authored=False, captures=0)
    try:
        for _ in range(4):
            await app.next_update_async()
        manager = app.get_extension_manager()
        entries = manager.get_extensions()
        relevant = ('omni.replicator', 'omni.syntheticdata', 'omni.hydra',
                    'omni.kit.capture', 'omni.kit.renderer.capture',
                    'omni.kit.viewport', 'omni.usd', 'omni.graph', 'omni.anim')
        report['build_version'] = app.get_build_version()
        report['extension_inventory_count'] = len(entries)
        report['extensions'] = [
            {key: entry.get(key) for key in ('id', 'name', 'version', 'enabled')}
            for entry in entries if (entry.get('name') or '').startswith(relevant)
        ]
        import omni.usd
        from pxr import Usd, UsdGeom
        stage = omni.usd.get_context().get_stage()
        report['usd_version'] = list(Usd.GetVersion())
        report['stage'] = None if stage is None else dict(
            identifier=stage.GetRootLayer().identifier,
            meters_per_unit=UsdGeom.GetStageMetersPerUnit(stage),
            up_axis=str(UsdGeom.GetStageUpAxis(stage)),
            prim_count=sum(1 for _ in stage.Traverse()))
        report['passed'] = True
    except BaseException as error:
        report.update(passed=False, error=str(error), traceback=traceback.format_exc())
    finally:
        OUT.write_text(json.dumps(report, indent=2) + '\n')
        app.post_quit(0 if report.get('passed') else 1)


_metadata_task = asyncio.ensure_future(main())
