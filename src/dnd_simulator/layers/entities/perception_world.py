"""Perception handlers for combat lifecycle and ecology events."""

from __future__ import annotations

from dnd_simulator.core.character import Character
from dnd_simulator.core.events import CombatStartedPayload, RoundStartPayload, SquadCombatPayload, SquadMovePayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.perception_common import GetEntityFn


def combat_started(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, CombatStartedPayload)
    return _("Combat started! Initiative order: {order}").format(order=", ".join(payload.turn_order_names) or "?")


def round_start(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, RoundStartPayload)
    return _("— Round {n} —").format(n=payload.round_number)


def squad_move(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, SquadMovePayload)
    if observer.location_id == payload.to_location_id:
        return _("{name} arrives").format(name=payload.squad_name)
    if observer.location_id == payload.from_location_id:
        return _("{name} departs").format(name=payload.squad_name)
    return _("{name} is on the move").format(name=payload.squad_name)


def squad_combat(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, SquadCombatPayload)
    template = _("{winner} destroyed {loser}") if payload.loser_strength == 0 else _("{winner} defeated {loser}")
    return template.format(winner=payload.winner_name, loser=payload.loser_name)


DISPATCH = {
    EventType.COMBAT_STARTED: combat_started,
    EventType.ROUND_START: round_start,
    EventType.SQUAD_MOVE: squad_move,
    EventType.SQUAD_COMBAT: squad_combat,
}
