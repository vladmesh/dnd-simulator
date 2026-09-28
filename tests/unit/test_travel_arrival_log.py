"""The arrival line a journey leaves in the traveller's log (flee or ordinary travel).

How long the road took (whole minutes rounded up, as the flee menu shows them; an hour
or more as hours + minutes) and where it ended, by the location's display name.
"""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Character, Entity, Race
from dnd_simulator.core.events import EntityArrivedPayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import language_context
from dnd_simulator.layers.entities.perception import format_travel_duration, perceive_event


def _arrived(seconds: int, *, fled: bool, entity_id: str = "hero", name: str = "Forest Road") -> Event:
    return Event(
        event_type=EventType.ENTITY_ARRIVED,
        source_layer="entities",
        data=EntityArrivedPayload(entity_id, "forest_road", name, 1000, 1000 + seconds, fled=fled),
    )


def _lookup(*entities: Entity):  # type: ignore[no-untyped-def]
    by_id = {e.id: e for e in entities}
    return by_id.get


_HERO = Character(id="hero", name="Hero", location_id="forest_road", race=Race.HUMAN)
_WITNESS = Character(id="witness", name="Witness", location_id="forest_road", race=Race.HUMAN)


class TestDuration:
    @pytest.mark.parametrize(
        ("minutes", "ru"),
        [
            (1, "1 минуту"),
            (2, "2 минуты"),
            (5, "5 минут"),
            (11, "11 минут"),
            (21, "21 минуту"),
            (22, "22 минуты"),
            (24, "24 минуты"),
        ],
    )
    def test_russian_minute_plurals(self, minutes: int, ru: str) -> None:
        with language_context("ru"):
            assert format_travel_duration(minutes * 60) == ru

    @pytest.mark.parametrize(("minutes", "en"), [(1, "1 minute"), (2, "2 minutes"), (21, "21 minutes")])
    def test_english_minute_plurals(self, minutes: int, en: str) -> None:
        with language_context("en"):
            assert format_travel_duration(minutes * 60) == en

    @pytest.mark.parametrize(("seconds", "minutes"), [(0, 1), (59, 1), (60, 1), (61, 2), (1439, 24), (1440, 24)])
    def test_rounds_up_to_whole_minutes_like_the_flee_menu(self, seconds: int, minutes: int) -> None:
        with language_context("en"):
            assert format_travel_duration(seconds) == f"{minutes} minute" + ("s" if minutes != 1 else "")

    @pytest.mark.parametrize(
        ("minutes", "ru", "en"),
        [
            (60, "1 час", "1 hour"),
            (61, "1 час 1 минуту", "1 hour 1 minute"),
            (125, "2 часа 5 минут", "2 hours 5 minutes"),
            (300, "5 часов", "5 hours"),
        ],
    )
    def test_an_hour_or_more_reads_as_hours_and_minutes(self, minutes: int, ru: str, en: str) -> None:
        with language_context("ru"):
            assert format_travel_duration(minutes * 60) == ru
        with language_context("en"):
            assert format_travel_duration(minutes * 60) == en


class TestArrivalLine:
    @pytest.mark.parametrize(
        ("minutes", "fled", "ru"),
        [
            (1, True, "Ты бежал 1 минуту до локации «Forest Road»."),
            (2, True, "Ты бежал 2 минуты до локации «Forest Road»."),
            (5, True, "Ты бежал 5 минут до локации «Forest Road»."),
            (21, True, "Ты бежал 21 минуту до локации «Forest Road»."),
            (1, False, "Ты шёл 1 минуту до локации «Forest Road»."),
            (2, False, "Ты шёл 2 минуты до локации «Forest Road»."),
            (5, False, "Ты шёл 5 минут до локации «Forest Road»."),
            (21, False, "Ты шёл 21 минуту до локации «Forest Road»."),
        ],
    )
    def test_russian_line_for_the_traveller(self, minutes: int, fled: bool, ru: str) -> None:
        with language_context("ru"):
            assert perceive_event(_arrived(minutes * 60, fled=fled), _HERO, _lookup(_HERO)) == ru

    def test_english_lines_for_the_traveller(self) -> None:
        with language_context("en"):
            assert (
                perceive_event(_arrived(1440, fled=True), _HERO, _lookup(_HERO))
                == "You ran for 24 minutes to Forest Road."
            )
            assert (
                perceive_event(_arrived(60, fled=False), _HERO, _lookup(_HERO))
                == "You walked for 1 minute to Forest Road."
            )

    def test_uses_the_display_name_not_the_id(self) -> None:
        with language_context("en"):
            line = perceive_event(_arrived(720, fled=False, name="Лесная дорога"), _HERO, _lookup(_HERO))
        assert line == "You walked for 12 minutes to Лесная дорога."
        assert "forest_road" not in line

    def test_a_witness_sees_the_traveller_arrive(self) -> None:
        with language_context("en"):
            line = perceive_event(_arrived(720, fled=True), _WITNESS, _lookup(_HERO, _WITNESS))
        assert line == f"{_WITNESS.perceive(_HERO)} arrives."
        assert "minute" not in line
