"""Equip/unequip action descriptions must localize under DND_LANGUAGE=ru.

Sprint 024, Phase 2, Task 2. The transport payload builder runs
``_(definition.description)`` per action; the RU ``.po`` must carry the
equip/unequip description translations so a Russian player sees Russian
tooltips, not the English base string.
"""

from __future__ import annotations

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import PeacefulAwareness
from dnd_simulator.i18n import language_context
from dnd_simulator.service.transport_payloads import _awareness_to_dict

_EQUIP_ACTIONS = [
    ActionType.UNEQUIP,  # weapon
    ActionType.EQUIP_ARMOR,
    ActionType.UNEQUIP_ARMOR,
    ActionType.EQUIP_SHIELD,
    ActionType.UNEQUIP_SHIELD,
    ActionType.EQUIP_HEAD,
    ActionType.UNEQUIP_HEAD,
    ActionType.EQUIP_FEET,
    ActionType.UNEQUIP_FEET,
    ActionType.EQUIP_RING,
    ActionType.UNEQUIP_RING,
]


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def _peaceful(actions: list[ActionType]) -> PeacefulAwareness:
    return PeacefulAwareness(
        hour=10,
        day=1,
        month=6,
        year=1490,
        weather={},
        location_name="Town Square",
        region_name="Valley",
        settlements=None,
        territory_owner=None,
        nation_info=None,
        available_actions=actions,
    )


def _descriptions_ru() -> dict[str, str]:
    with language_context("ru"):
        result = _awareness_to_dict(_peaceful(_EQUIP_ACTIONS))
    return {a["name"]: a["description"] for a in result["available_actions"]}


def test_equip_descriptions_localize_to_russian() -> None:
    by_name = _descriptions_ru()
    for action in _EQUIP_ACTIONS:
        description = by_name[str(action)]
        assert _has_cyrillic(description), f"{action} description not translated: {description!r}"
        assert "—" not in description


def test_equip_descriptions_english_base_has_no_em_dash() -> None:
    with language_context("en"):
        result = _awareness_to_dict(_peaceful(_EQUIP_ACTIONS))
    for action_info in result["available_actions"]:
        assert "—" not in action_info["description"]
