"""Format raw events into subjective text through an observer's perception."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.models import Event, EventType

GetEntityFn = Callable[[str], Entity | None]


def perceive_event(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    """Describe an event from the observer's point of view.

    Uses observer.perceive() to describe participants, so the same event
    looks different to different observers.
    """
    if event.event_type == EventType.ENTITY_SAY:
        return _perceive_say(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_ATTACK:
        return _perceive_attack(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_DIED:
        return _perceive_death(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_DODGE:
        return _perceive_dodge(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_FLEE:
        return _perceive_flee(event, observer, get_entity)
    if event.event_type == EventType.COMBAT_STARTED:
        return _perceive_combat_started(event, observer, get_entity)
    if event.event_type == EventType.COMBAT_ENDED:
        return "Бой окончен."
    return f"Что-то произошло ({event.event_type.value})"


def _describe(observer: Character, entity_id: str, get_entity: GetEntityFn) -> str:
    """Get observer's perception of an entity by ID.

    Includes entity ID in parentheses so LLM can cross-reference
    event participants with the nearby entities list.
    """
    entity = get_entity(entity_id)
    if entity is None:
        return "кто-то"
    if entity.id == observer.id:
        return "ты"
    desc = observer.perceive(entity)
    return f"{desc} (id: {entity_id})"


def _perceive_say(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    speaker_id = event.data.get("entity_id", "")
    text = event.data.get("text", "")
    assert isinstance(speaker_id, str)
    assert isinstance(text, str)

    speaker = _describe(observer, speaker_id, get_entity)
    if speaker_id == observer.id:
        return f"Ты говоришь: «{text}»"
    return f"{speaker} говорит: «{text}»"


def _perceive_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    attacker_id = event.data.get("attacker_id", "")
    target_id = event.data.get("target_id", "")
    hit = event.data.get("hit", True)
    damage = event.data.get("damage")
    weapon = event.data.get("weapon", "")
    assert isinstance(attacker_id, str)
    assert isinstance(target_id, str)

    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)

    weapon_str = f" ({weapon})" if weapon else ""
    if not hit:
        outcome_str = ", промах"
    elif damage is not None:
        outcome_str = f", {damage} урона"
    else:
        outcome_str = ""

    if attacker_id == observer.id:
        return f"Ты атакуешь {target}{weapon_str}{outcome_str}"
    if target_id == observer.id:
        return f"{attacker} атакует тебя{weapon_str}{outcome_str}"
    return f"{attacker} атакует {target}{weapon_str}{outcome_str}"


def _perceive_death(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    assert isinstance(entity_id, str)

    if entity_id == observer.id:
        return "Ты погибаешь"
    desc = _describe(observer, entity_id, get_entity)
    return f"{desc} погибает"


def _perceive_dodge(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    description = event.data.get("description", "")
    assert isinstance(entity_id, str)

    desc_suffix = f" «{description}»" if description else ""
    if entity_id == observer.id:
        return f"Ты принимаешь защитную стойку{desc_suffix}"
    desc = _describe(observer, entity_id, get_entity)
    return f"{desc} принимает защитную стойку{desc_suffix}"


def _perceive_flee(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    description = event.data.get("description", "")
    assert isinstance(entity_id, str)

    desc_suffix = f" «{description}»" if description else ""
    if entity_id == observer.id:
        return f"Ты пытаешься сбежать{desc_suffix}"
    desc = _describe(observer, entity_id, get_entity)
    return f"{desc} пытается сбежать{desc_suffix}"


def _perceive_combat_started(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    names = event.data.get("turn_order_names", [])
    order_str = ", ".join(str(n) for n in names) if names else "?"
    return f"Бой начался! Порядок инициативы: {order_str}"
