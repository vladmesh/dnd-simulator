from __future__ import annotations

import pytest

from dnd_simulator.core.events import (
    SquadMaterializedPayload,
    SquadMovePayload,
    WeatherChangedPayload,
)
from dnd_simulator.core.models import Event, EventType


def test_typed_weather_and_squad_payloads_expose_domain_fields() -> None:
    weather = Event(
        event_type=EventType.WEATHER_CHANGED,
        source_layer="geography",
        data=WeatherChangedPayload("north", "clear", "rain", 8.5),
    )
    move = Event(
        event_type=EventType.SQUAD_MOVE,
        source_layer="ecology",
        data=SquadMovePayload("wolves", "Wolf Pack", "forest", "road"),
    )
    materialized = Event(
        event_type=EventType.SQUAD_MATERIALIZED,
        source_layer="entities",
        data=SquadMaterializedPayload("wolves", "Wolf Pack", "road", 3),
    )

    assert weather.data.new_weather == "rain"
    assert move.data.to_location_id == "road"
    assert materialized.data.creature_count == 3


def test_event_rejects_payload_for_another_event_type() -> None:
    with pytest.raises(TypeError, match=r"SQUAD_MOVE.*WeatherChangedPayload"):
        Event(
            event_type=EventType.SQUAD_MOVE,
            source_layer="ecology",
            data=WeatherChangedPayload("north", "clear", "rain", 8.5),
        )
