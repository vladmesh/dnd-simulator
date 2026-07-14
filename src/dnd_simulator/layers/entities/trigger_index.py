"""Event-type index for creature activation trigger conditions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.triggers import ActivationTrigger, EventCondition


class TriggerBoundary(StrEnum):
    ON = "on"
    UNTIL = "until"


@dataclass(frozen=True)
class TriggerMatch:
    creature: Creature
    trigger: ActivationTrigger
    boundary: TriggerBoundary


@dataclass(frozen=True)
class _IndexedCondition:
    creature: Creature
    trigger: ActivationTrigger
    boundary: TriggerBoundary
    condition: EventCondition


class TriggerIndex:
    """Indexes both boundaries by EventType; matching never scans all creatures."""

    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._buckets: dict[EventType, list[_IndexedCondition]] = defaultdict(list)
        for entity in entities or []:
            self.add(entity)

    def add(self, entity: Entity) -> None:
        if not isinstance(entity, Creature):
            return
        self.remove(entity.id)
        for trigger in entity.triggers:
            self._add_condition(entity, trigger, TriggerBoundary.ON, trigger.definition.on)
            self._add_condition(entity, trigger, TriggerBoundary.UNTIL, trigger.definition.until)

    def remove(self, entity_id: str) -> None:
        for event_type, entries in list(self._buckets.items()):
            remaining = [entry for entry in entries if entry.creature.id != entity_id]
            if remaining:
                self._buckets[event_type] = remaining
            else:
                del self._buckets[event_type]

    def match(self, event: Event) -> list[TriggerMatch]:
        return [
            TriggerMatch(entry.creature, entry.trigger, entry.boundary)
            for entry in self._buckets.get(event.event_type, ())
            if entry.trigger.armed and entry.condition.matches(event)
        ]

    def _add_condition(
        self,
        creature: Creature,
        trigger: ActivationTrigger,
        boundary: TriggerBoundary,
        condition: EventCondition,
    ) -> None:
        self._buckets[condition.event_type].append(
            _IndexedCondition(
                creature=creature,
                trigger=trigger,
                boundary=boundary,
                condition=condition,
            )
        )
