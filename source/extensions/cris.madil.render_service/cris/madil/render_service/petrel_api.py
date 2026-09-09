"""Kit update subscription and HTTP controls for the petrel preview only."""
from typing import Literal, Optional

import carb
import omni.kit.app
import omni.usd
from pydantic import BaseModel, Field

from .api import router
from .petrel_playback import PetrelPlayback

_players = {}
_subscription = None
_last_error = None


def _update(event):
    global _subscription, _last_error
    stage = omni.usd.get_context().get_stage()
    for name, player in list(_players.items()):
        try:
            if player.stage != stage or not player.is_valid():
                player.close()
                del _players[name]
                continue
            player.advance(float(event.payload['dt']))
        except Exception as exc:
            _last_error = str(exc)
            carb.log_error('Petrel playback: ' + str(exc))
            player.close()
            del _players[name]
    if not _players:
        _subscription = None


def shutdown_petrel_playback():
    global _subscription
    _subscription = None
    for player in _players.values():
        player.close()
    _players.clear()


class PlaybackRequest(BaseModel):
    name: str = 'PetrelRigTest'
    action: Literal['start', 'pause', 'resume', 'stop'] = 'start'
    mode: Optional[Literal['flap', 'glide']] = None
    speed: Optional[float] = Field(default=None, ge=0.05, le=4.0)
    transition_seconds: float = Field(default=0.5, ge=0.0, le=10.0)


@router.post('/scene/birds/petrel/playback', summary='Control independent petrel skeletal playback')
async def control_playback(data: PlaybackRequest):
    global _subscription, _last_error
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return {'ok': False, 'error': 'No live USD stage'}
    player = _players.get(data.name)
    if player and (player.stage != stage or not player.is_valid()):
        player.close()
        del _players[data.name]
        player = None
    if data.action == 'stop':
        if player:
            player.close()
            del _players[data.name]
        if not _players:
            _subscription = None
        return {'ok': True, 'active': False, 'name': data.name}
    if not player and data.action != 'start':
        return {'ok': False, 'error': 'Start independent playback first'}
    created = False
    try:
        if not player:
            player = PetrelPlayback(stage, data.name)
            created = True
        player.control(data.action, data.mode, data.speed, data.transition_seconds)
        _players[data.name] = player
        if _subscription is None:
            _subscription = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
                _update, name='MARLIN independent petrel playback')
        _last_error = None
        return {'ok': True, 'active': True, **player.status()}
    except Exception as exc:
        if created:
            player.close()
            _players.pop(data.name, None)
        return {'ok': False, 'error': str(exc)}


@router.get('/scene/birds/petrel/playback', summary='Inspect independent petrel playback')
async def playback_status():
    return {'ok': True, 'players': [p.status() for p in _players.values()], 'last_error': _last_error}
