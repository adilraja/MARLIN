"""Registry index/metadata only. No extension enable, pull or installation API."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback

OUT = Path(os.environ['ANNOTATION_DEPENDENCY_OUTPUT'])


def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, default=str)+'\n')


async def main():
    import carb.settings
    import omni.kit.app
    app = omni.kit.app.get_app()
    manager = app.get_extension_manager()
    settings = carb.settings.get_settings()
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                  build_version=app.get_build_version(), scope='Metadata only; no provider activation',
                  content_pull_calls=0, captures=0)
    before = list(manager.get_extension_packages())
    save('installed_before.json', before)
    enabled_before = sorted(e['id'] for e in manager.get_extensions() if e['enabled'])
    try:
        assert settings.get('/app/extensions/registryEnabled') is True
        assert not settings.get('/app/extensions/syncRegistryOnStartup')
        assert not os.access(os.environ['ANNOTATION_CONTENT_FORBIDDEN'], os.W_OK)
        for _ in range(4):
            await app.next_update_async()
        result['providers'] = list(manager.get_registry_providers())
        result['registries'] = settings.get('/exts/omni.kit.registry.nucleus/registries')
        save('progress.json', dict(phase='starting_index_sync', **result))
        result['sync_result'] = manager.sync_registry()
        save('progress.json', dict(phase='index_sync_returned', **result))
        queries = {}
        for name in ('omni.replicator.core', 'omni.syntheticdata'):
            queries[name] = dict(versions=list(manager.fetch_extension_versions(name)),
                                 packages=list(manager.fetch_extension_packages(name)),
                                 preferred=manager.get_registry_extension_dict(name))
            save('provider_queries.json', queries)
        registry = list(manager.get_registry_extensions())
        save('registry_inventory.json', registry)
        pinned_core = ['omni.usd-1.16.0', 'omni.graph.core-3.1.3',
                       'omni.hydra.rtx-1.0.4', 'omni.kit.renderer.capture-2.0.1']
        solutions = {}
        for name in ('omni.replicator.core', 'omni.syntheticdata'):
            solution = list(manager.solve_extensions([name, *pinned_core], add_enabled=True))
            # This installed Kit build returns solution entries as dictionaries,
            # although the generic manual describes a list of extension IDs.
            ids = [entry['id'] if isinstance(entry, dict) else entry for entry in solution[1]]
            metadata = {eid: manager.get_registry_extension_dict(eid)
                        or manager.get_extension_dict(eid) for eid in ids}
            solutions[name] = dict(input=[name,*pinned_core], result=solution, metadata=metadata)
            save('solutions.json', solutions)
        capture_inputs=['omni.replicator.core-1.13.27',*pinned_core]
        for name in ('omni.kit.loop-default','omni.kit.viewport.window',
                     'omni.kit.viewport.utility','omni.rtx.settings.core'):
            matches=[row['id'] for row in before if row['name']==name]
            assert len(matches)==1, (name,matches)
            capture_inputs.append(matches[0])
        solution=list(manager.solve_extensions(capture_inputs,add_enabled=False))
        ids=[entry['id'] if isinstance(entry,dict) else entry for entry in solution[1]]
        solutions['proposed_isolated_capture']=dict(input=capture_inputs,add_enabled=False,
            result=solution,metadata={eid:manager.get_registry_extension_dict(eid)
                                     or manager.get_extension_dict(eid) for eid in ids})
        save('solutions.json',solutions)
        result['registry_extension_count'] = len(registry)
        result['provider_package_counts'] = {k:len(v['packages']) for k,v in queries.items()}
        result['passed'] = True
    except BaseException as error:
        result.update(passed=False,error=str(error),traceback=traceback.format_exc())
    finally:
        after = list(manager.get_extension_packages())
        save('installed_after.json', after)
        result['installed_package_ids_unchanged'] = sorted(e['package_id'] for e in before) == sorted(e['package_id'] for e in after)
        result['enabled_ids_unchanged'] = enabled_before == sorted(e['id'] for e in manager.get_extensions() if e['enabled'])
        result['content_destination_empty'] = not any(Path(os.environ['ANNOTATION_CONTENT_FORBIDDEN']).iterdir())
        result['passed'] = bool(result.get('passed') and result['installed_package_ids_unchanged']
                                and result['enabled_ids_unchanged'] and result['content_destination_empty'])
        settings.set_bool('/app/extensions/registryEnabled', False)
        save('query.json', result)
        app.post_quit(0 if result['passed'] else 1)


_dependency_query = asyncio.ensure_future(main())
