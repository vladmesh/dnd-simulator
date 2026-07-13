"""Typed activation trigger definitions shared by content and runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, get_origin, get_type_hints

from pydantic import TypeAdapter, ValidationError

from dnd_simulator.core.events import EVENT_PAYLOAD_TYPES
from dnd_simulator.core.models import Event, EventType


@dataclass(frozen=True)
class EventCondition:
    """An event type plus exact typed payload fields that must match."""

    event_type: EventType
    match_fields: tuple[tuple[str, object], ...] = ()

    @classmethod
    def from_mapping(cls, event_type: EventType, values: dict[str, object]) -> EventCondition:
        payload_type = EVENT_PAYLOAD_TYPES[event_type]
        annotations = get_type_hints(payload_type)
        payload_fields = {name for name, annotation in annotations.items() if get_origin(annotation) is not ClassVar}
        normalized: list[tuple[str, object]] = []

        for name, value in values.items():
            if name not in payload_fields:
                raise ValueError(f"{event_type.value} payload has no field '{name}'")
            try:
                typed_value = TypeAdapter(annotations[name]).validate_python(value, strict=True)
            except ValidationError as exc:
                raise ValueError(f"invalid {event_type.value}.{name} match value: {value!r}") from exc
            normalized.append((name, typed_value))

        return cls(event_type=event_type, match_fields=tuple(sorted(normalized)))

    def matches(self, event: Event) -> bool:
        if event.event_type is not self.event_type:
            return False
        return all(event.payload.get(name) == expected for name, expected in self.match_fields)


@dataclass(frozen=True)
class TriggerDefinition:
    """Stable content definition of a paired activation trigger."""

    id: str
    on: EventCondition
    until: EventCondition

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("trigger id must not be empty")


@dataclass
class ActivationTrigger:
    """Mutable state for one creature's trigger definition."""

    definition: TriggerDefinition
    armed: bool = True
    active: bool = False
