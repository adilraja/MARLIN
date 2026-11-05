"""Small opt-in Kit Services surface for the v3 contract."""
from .exchange import _object
from .exchange_v3 import validate_step


def register(router, actor, context):
    @router.post('/integration/gama/v3/validate')
    async def validate(payload: dict):
        try:
            return {'ok': True, 'snapshot': validate_step(payload), 'rendered': False}
        except ValueError as error:
            return {'ok': False, 'error': str(error), 'rendered': False}

    @router.get('/integration/gama/v3/actor/status')
    async def status():
        stage, busy = context()
        return {'ok': True, **actor().status(stage, busy)}

    def operation(name, fields, action):
        async def endpoint(payload: dict):
            try:
                _object(payload, fields, (), name)
                stage, busy = context()
                return {'ok': True, **action(actor(), stage, busy, payload)}
            except (ValueError, OSError) as error:
                return {'ok': False, 'error': str(error), 'rendered': False}
        endpoint.__name__ = name + '_v3'
        router.post('/integration/gama/v3/actor/' + name)(endpoint)

    operation('acquire', ('agent_id',), lambda a,s,b,p: a.acquire(s,p['agent_id'],b))
    operation('step', ('ownership_token','step'), lambda a,s,b,p: a.apply(s,p['ownership_token'],p['step'],b))
    operation('evaluate', ('ownership_token','simulation_time_s'), lambda a,s,b,p: a.evaluate(s,p['ownership_token'],p['simulation_time_s'],b))
    operation('pause', ('ownership_token','paused'), lambda a,s,b,p: a.set_paused(s,p['ownership_token'],p['paused'],b))
    operation('reset', ('ownership_token',), lambda a,s,b,p: a.reset(s,p['ownership_token'],b))
    operation('release', ('ownership_token',), lambda a,s,b,p: (a.release(p['ownership_token'],b) or {'released': True}))
