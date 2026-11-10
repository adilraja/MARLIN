"""Read supported manager metadata; close only this private USD context and quit."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import traceback

OUT = Path(os.environ['ABOVE_WATER_M2_OUTPUT'])


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + '\n')


async def main():
    import carb.settings
    import omni.kit.app
    import omni.usd
    app = omni.kit.app.get_app()
    settings = carb.settings.get_settings()
    result = dict(schema_version=1, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  pid=os.getpid(), build_version=app.get_build_version(), captures=0,
                  provider_enable_attempted=False, registry_refreshed=False,
                  packages_pulled=False, scene_authored=False)
    started = time.monotonic()
    try:
        assert not settings.get('/app/extensions/registryEnabled')
        assert not settings.get('/app/extensions/syncRegistryOnStartup')
        while not app.is_app_ready():
            if time.monotonic() - started > 100:
                raise TimeoutError('App readiness did not arrive within 100 seconds')
            await app.next_update_async()
        for _ in range(4):
            await app.next_update_async()
        result['app_ready'] = app.is_app_ready()
        result['ready_after_worker_seconds'] = time.monotonic() - started
        manager = app.get_extension_manager()
        if os.environ.get('ABOVE_WATER_M2_REGISTRY_QUERY') == '1':
            # Metadata fetches only. Never call pull_extension, enable a remote
            # provider, solve with downloads, or run a package/pip installer.
            remote = dict(providers=list(manager.get_registry_providers()),
                          queries={}, pulls_attempted=False)
            save('registry_queries.json', remote)
            for name in ('omni.replicator.core', 'omni.syntheticdata'):
                remote['queries'][name] = {
                    'versions': list(manager.fetch_extension_versions(name)),
                    'packages': list(manager.fetch_extension_packages(name))}
                save('registry_queries.json', remote)
            result['registry_metadata_queried'] = True
        queries = ('get_extensions', 'get_extension_packages',
                   'get_registry_extensions', 'get_registry_extension_packages')
        inventory = {}
        for method in queries:
            inventory[method] = list(getattr(manager, method)())
        # Paths and package dictionaries come only from supported runtime APIs.
        # Do not open or scan any generated runtime/cache directory in this probe.
        inventory['get_folders'] = list(manager.get_folders())
        save('inventory.json', inventory)
        result['inventory_counts'] = {k: len(v) for k, v in inventory.items()}
        result['native_provider_entries'] = {
            k: [entry for entry in values
                if any(name in json.dumps(entry, default=str)
                       for name in ('omni.replicator.core', 'omni.syntheticdata'))]
            for k, values in inventory.items() if k != 'get_folders'
        }
        result['settings'] = {key: settings.get(key) for key in (
            '/app/extensions/registryEnabled', '/app/extensions/syncRegistryOnStartup',
            '/app/file/ignoreUnsavedOnExit', '/app/settings/loadUserConfig',
            '/app/settings/saveUserConfig', '/renderer/multiGpu/enabled')}
        context = omni.usd.get_context()
        stage = context.get_stage()
        result['stage_before_cleanup'] = None if stage is None else {
            'identifier': stage.GetRootLayer().identifier,
            'prims': sum(1 for _ in stage.Traverse())}
        if stage is not None:
            assert stage.GetRootLayer().anonymous, 'Refuse to close a non-private scene'
            await context.close_stage_async()
        result['stage_closed'] = context.get_stage() is None
        result['passed'] = result['app_ready'] and result['stage_closed']
    except BaseException as error:
        result.update(passed=False, error=str(error), traceback=traceback.format_exc())
    finally:
        result['quit_request'] = 'IApp.post_quit (normal, cancellable)'
        result['quit_requested_utc'] = datetime.now(timezone.utc).isoformat()
        save('query.json', result)
        app.post_quit(0 if result.get('passed') else 1)


_m2_query_task = asyncio.ensure_future(main())
