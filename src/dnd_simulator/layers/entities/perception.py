"""Format raw events into subjective text through an observer's perception."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import _

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
    if event.event_type in (EventType.ENTITY_MOVE, EventType.ENTITY_DASH):
        return _perceive_move(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_USE_ITEM:
        return _perceive_use_item(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_BLESS:
        return _perceive_bless(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_EQUIP:
        return _perceive_equip(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_UNEQUIP:
        return _perceive_unequip(event, observer, get_entity)
    if event.event_type == EventType.TURN_SKIPPED:
        return _perceive_turn_skipped(event, observer, get_entity)
    if event.event_type == EventType.COMBAT_STARTED:
        return _perceive_combat_started(event, observer, get_entity)
    if event.event_type == EventType.COMBAT_ENDED:
        return _("Combat ended.")
    if event.event_type == EventType.CUSTOM and event.data.get("inspect_target"):
        return _perceive_inspect(event, observer, get_entity)
    return _("Something happened ({type})").format(type=event.event_type.value)


def _describe(observer: Character, entity_id: str, get_entity: GetEntityFn) -> str:
    """Get observer's perception of an entity by ID."""
    entity = get_entity(entity_id)
    if entity is None:
        return _("someone")
    if entity.id == observer.id:
        return _("you")
    return observer.perceive(entity)


def _perceive_say(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    speaker_id = event.data.get("entity_id", "")
    text = event.data.get("text", "")
    assert isinstance(speaker_id, str)
    assert isinstance(text, str)

    speaker = _describe(observer, speaker_id, get_entity)
    if speaker_id == observer.id:
        return _('You say: "{text}"').format(text=text)
    return _('{speaker} says: "{text}"').format(speaker=speaker, text=text)


def _perceive_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    attacker_id = event.data.get("attacker_id", "")
    target_id = event.data.get("target_id", "")
    hit = event.data.get("hit", True)
    damage = event.data.get("damage")
    weapon = event.data.get("weapon", "")
    d20_roll = event.data.get("roll", 0)
    total = event.data.get("total", 0)
    ac = event.data.get("ac", 0)
    critical = event.data.get("critical", False)
    advantage = event.data.get("advantage", False)
    disadvantage = event.data.get("disadvantage", False)
    bless_bonus = event.data.get("bless_bonus", 0)
    assert isinstance(attacker_id, str)
    assert isinstance(target_id, str)

    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)

    weapon_str = f" ({weapon})" if weapon else ""

    # Dice roll detail: "d20(14)+3=17 vs AC 13"
    roll_parts: list[str] = []
    if advantage and not disadvantage:
        roll_parts.append(_("adv "))
    elif disadvantage and not advantage:
        roll_parts.append(_("disadv "))
    roll_parts.append(f"d20({d20_roll})")
    modifier = int(total) - int(d20_roll)
    if modifier >= 0:
        roll_parts.append(f"+{modifier}")
    else:
        roll_parts.append(str(modifier))
    if bless_bonus:
        roll_parts.append(f"+{bless_bonus}bless")
    roll_parts.append(f"={total}")
    roll_parts.append(f" vs AC {ac}")
    roll_str = " [" + "".join(roll_parts) + "]"

    if critical and hit:
        outcome_str = _(", CRIT! {damage} damage").format(damage=damage) if damage else _(", CRIT!")
    elif not hit:
        outcome_str = _(", miss")
    elif damage is not None:
        outcome_str = _(", {damage} damage").format(damage=damage)
    else:
        outcome_str = ""

    if attacker_id == observer.id:
        return _("You attack {target}{weapon}{roll}{outcome}").format(
            target=target, weapon=weapon_str, roll=roll_str, outcome=outcome_str
        )
    if target_id == observer.id:
        return _("{attacker} attacks you{weapon}{roll}{outcome}").format(
            attacker=attacker, weapon=weapon_str, roll=roll_str, outcome=outcome_str
        )
    return _("{attacker} attacks {target}{weapon}{roll}{outcome}").format(
        attacker=attacker, target=target, weapon=weapon_str, roll=roll_str, outcome=outcome_str
    )


def _perceive_death(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    assert isinstance(entity_id, str)

    if entity_id == observer.id:
        return _("You die")
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} dies").format(entity=desc)


def _perceive_dodge(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    description = event.data.get("description", "")
    assert isinstance(entity_id, str)

    desc_suffix = f" \u00ab{description}\u00bb" if description else ""
    if entity_id == observer.id:
        return _("You take a defensive stance{desc}").format(desc=desc_suffix)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} takes a defensive stance{desc}").format(entity=desc, desc=desc_suffix)


def _perceive_flee(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    description = event.data.get("description", "")
    assert isinstance(entity_id, str)

    desc_suffix = f" \u00ab{description}\u00bb" if description else ""
    if entity_id == observer.id:
        return _("You try to flee{desc}").format(desc=desc_suffix)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} tries to flee{desc}").format(entity=desc, desc=desc_suffix)


def _perceive_move(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    from dnd_simulator.rules.movement import direction_label

    entity_id = event.data.get("entity_id", "")
    assert isinstance(entity_id, str)
    description = event.data.get("description", "")
    distance_ft = event.data.get("distance_ft", 0)
    from_x = event.data.get("from_x", 0)
    from_y = event.data.get("from_y", 0)
    to_x = event.data.get("to_x", 0)
    to_y = event.data.get("to_y", 0)
    assert isinstance(from_x, int) and isinstance(from_y, int)
    assert isinstance(to_x, int) and isinstance(to_y, int)

    dx = to_x - from_x
    dy = to_y - from_y
    dir_label = direction_label(dx, dy)

    is_dash = event.event_type == EventType.ENTITY_DASH
    verb = _("dashes") if is_dash else _("moves")
    desc_suffix = f" \u00ab{description}\u00bb" if description else ""

    if entity_id == observer.id:
        verb_self = _("dash") if is_dash else _("move")
        return _("You {verb} {direction} ({distance} ft){desc}").format(
            verb=verb_self, direction=dir_label, distance=distance_ft, desc=desc_suffix
        )
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} {verb} {direction} ({distance} ft){desc}").format(
        entity=desc, verb=verb, direction=dir_label, distance=distance_ft, desc=desc_suffix
    )


def _perceive_use_item(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    item_name = str(event.data.get("item_name", _("an item")))
    healed = event.data.get("healed", 0)

    if entity_id == observer.id:
        return _("You use {item} (healed {hp} HP)").format(item=item_name, hp=healed)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} uses {item} (healed {hp} HP)").format(entity=desc, item=item_name, hp=healed)


def _perceive_inspect(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    from dnd_simulator.core.character import Creature

    target_id = str(event.data.get("inspect_target", ""))
    target = get_entity(target_id)
    if target is None:
        return _("You look around but see no one matching '{id}'.").format(id=target_id)
    desc = observer.perceive(target)
    parts = [_("You inspect {desc}.").format(desc=desc)]
    if isinstance(target, Creature):
        if target.current_hp < target.max_hp // 2:
            parts.append(_("They look badly wounded."))
        elif target.current_hp < target.max_hp:
            parts.append(_("They have minor injuries."))
        else:
            parts.append(_("They look healthy."))
    return " ".join(parts)


def _perceive_turn_skipped(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = event.data.get("entity_id", "")
    conditions = event.data.get("conditions", [])
    assert isinstance(entity_id, str)

    cond_str = ", ".join(str(c) for c in conditions) if conditions else "?"
    if entity_id == observer.id:
        return _("You can't act ({conditions}) — turn skipped").format(conditions=cond_str)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} can't act ({conditions}) — turn skipped").format(entity=desc, conditions=cond_str)


def _perceive_bless(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    duration = event.data.get("duration_rounds", "?")
    if entity_id == observer.id:
        return _("You invoke a blessing (+d4 to attack rolls for {n} rounds)").format(n=duration)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} invokes a blessing (+d4 to attack rolls for {n} rounds)").format(entity=desc, n=duration)


def _perceive_equip(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    weapon_name = str(event.data.get("weapon_name", _("a weapon")))
    if entity_id == observer.id:
        return _("You equip {weapon}").format(weapon=weapon_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} equips {weapon}").format(entity=desc, weapon=weapon_name)


def _perceive_unequip(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    weapon_name = str(event.data.get("weapon_name", _("a weapon")))
    if entity_id == observer.id:
        return _("You put away {weapon}").format(weapon=weapon_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} puts away {weapon}").format(entity=desc, weapon=weapon_name)


def _perceive_combat_started(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    names = event.data.get("turn_order_names", [])
    order_str = ", ".join(str(n) for n in names) if names else "?"
    return _("Combat started! Initiative order: {order}").format(order=order_str)
