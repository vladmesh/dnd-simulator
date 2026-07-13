"""Typed event location and perception-log boundaries for entities."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.awareness import PerceivedEvent
from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.events import SquadMovePayload, TypedPayload, payload_to_data
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.entities.perception import perceive_event

_LOGGED_EVENTS = frozenset(
    {
        EventType.ENTITY_SAY,
        EventType.ENTITY_ATTACK,
        EventType.ENTITY_DIED,
        EventType.ENTITY_DODGE,
        EventType.ENTITY_FLEE,
        EventType.ENTITY_MOVE,
        EventType.ENTITY_DASH,
        EventType.ENTITY_DISENGAGE,
        EventType.ENTITY_USE_ITEM,
        EventType.ENTITY_BLESS,
        EventType.ENTITY_EQUIP,
        EventType.ENTITY_UNEQUIP,
        EventType.ENTITY_SECOND_WIND,
        EventType.ENTITY_ACTION_SURGE,
        EventType.ENTITY_LAY_ON_HANDS,
        EventType.OPPORTUNITY_ATTACK,
        EventType.COMBAT_STARTED,
        EventType.COMBAT_ENDED,
        EventType.ENCOUNTER_SPAWNED,
        EventType.SQUAD_MOVE,
        EventType.SQUAD_COMBAT,
        EventType.SQUAD_MATERIALIZED,
        EventType.SQUAD_DEMATERIALIZED,
    }
)


class EventLog:
    """Record typed events at locations and expose structured perception."""

    def __init__(self, entities: dict[str, Entity], location_log: dict[str, list[Event]] | None = None) -> None:
        self._entities = entities
        self._location_log = location_log if location_log is not None else {}

    def location_for(self, event: Event) -> str | None:
        payload = event.payload
        if not isinstance(payload, TypedPayload):
            raise TypeError("event payload must be a TypedPayload")
        for entity_id in (getattr(payload, "entity_id", None), getattr(payload, "attacker_id", None)):
            if isinstance(entity_id, str) and (entity := self._entities.get(entity_id)) is not None:
                return entity.location_id
        if isinstance(payload, SquadMovePayload):
            return payload.to_location_id or payload.from_location_id
        location_id = getattr(payload, "location_id", None)
        return location_id if isinstance(location_id, str) and location_id else None

    def record(self, event: Event) -> None:
        if event.event_type not in _LOGGED_EVENTS:
            return
        payload = event.payload
        if isinstance(payload, SquadMovePayload):
            for location_id in (payload.from_location_id, payload.to_location_id):
                if location_id:
                    self._location_log.setdefault(location_id, []).append(event)
            return
        if event_location := self.location_for(event):
            self._location_log.setdefault(event_location, []).append(event)

    def perceived_events(self, creature: Creature, get_entity: Callable[[str], Entity | None]) -> list[PerceivedEvent]:
        if not isinstance(creature, Character):
            return []
        events = self._location_log.get(creature.location_id, [])
        new_events = events[creature._last_seen_log_index :]
        creature._last_seen_log_index = len(events)
        result: list[PerceivedEvent] = []
        for event in new_events:
            if event.observer_ids is not None and creature.id not in event.observer_ids:
                continue
            payload = event.payload
            actor_id = getattr(payload, "entity_id", None) or getattr(payload, "attacker_id", None)
            target_id = getattr(payload, "target_id", None)
            actor = get_entity(actor_id) if isinstance(actor_id, str) else None
            result.append(
                PerceivedEvent(
                    description=perceive_event(event, creature, get_entity),
                    event_type=event.event_type,
                    actor_id=actor_id if isinstance(actor_id, str) else None,
                    actor_name=actor.name if actor is not None else None,
                    target_id=target_id if isinstance(target_id, str) else None,
                    data=payload_to_data(payload),
                )
            )
        return result
