"""Format raw events into subjective text through an observer's perception."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import _

GetEntityFn = Callable[[str], Entity | None]

# ---------------------------------------------------------------------------
# Translatable dynamic values — listed here so pygettext3 can extract them.
# At runtime, _() is called on the raw string from event data.
# ---------------------------------------------------------------------------
# fmt: off
_TRANSLATABLE_STRINGS = [
    # Damage types (DamageType enum values)
    _("slashing"), _("piercing"), _("bludgeoning"),
    _("fire"), _("cold"), _("lightning"), _("thunder"), _("acid"), _("poison"),
    _("radiant"), _("necrotic"), _("force"), _("psychic"),
    # Damage source labels (from combat_manager._build_damage_components)
    _("weapon"), _("ability"), _("sneak_attack"), _("dueling"),
    # Roll labels
    _("AC"),
    # Common item/weapon names (from YAML catalogs)
    _("Health Potion"),
    _("Dagger"), _("Longsword"), _("Shortsword"), _("Greataxe"), _("Handaxe"),
    _("Shortbow"), _("Longbow"), _("Light Crossbow"),
    _("Mace"), _("Quarterstaff"), _("Javelin"), _("Spear"),
    # Fallback labels
    _("an item"), _("a weapon"),
]
# fmt: on


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
    if event.event_type == EventType.ENTITY_DISENGAGE:
        return _perceive_disengage(event, observer, get_entity)
    if event.event_type == EventType.OPPORTUNITY_ATTACK:
        return _perceive_opportunity_attack(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_DODGE:
        return _perceive_dodge(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_FLEE:
        return _perceive_flee(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_MOVE:
        return _perceive_move(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_DASH:
        return _perceive_dash(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_USE_ITEM:
        return _perceive_use_item(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_BLESS:
        return _perceive_bless(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_EQUIP:
        return _perceive_equip(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_UNEQUIP:
        return _perceive_unequip(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_BUY:
        return _perceive_buy(event, observer, get_entity)
    if event.event_type == EventType.ENTITY_SELL:
        return _perceive_sell(event, observer, get_entity)
    if event.event_type == EventType.TURN_SKIPPED:
        return _perceive_turn_skipped(event, observer, get_entity)
    if event.event_type == EventType.ROUND_START:
        round_number = event.data.get("round_number", "?")
        return _("— Round {n} —").format(n=round_number)
    if event.event_type == EventType.COMBAT_STARTED:
        return _perceive_combat_started(event, observer, get_entity)
    if event.event_type == EventType.COMBAT_ENDED:
        return _("Combat ended.")
    if event.event_type == EventType.SQUAD_MOVE:
        return _perceive_squad_move(event, observer)
    if event.event_type == EventType.SQUAD_COMBAT:
        return _perceive_squad_combat(event)
    if event.event_type == EventType.SQUAD_MATERIALIZED:
        return _perceive_squad_materialized(event)
    if event.event_type == EventType.SQUAD_DEMATERIALIZED:
        return _perceive_squad_dematerialized(event)
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


def _format_roll(atk_roll: dict[str, object], ac: object) -> str:
    """Build attack roll string from structured components.

    Format: [adv d20(14)+5=19 vs AC 13]
    Components are generic — no knowledge of specific bonuses.
    """
    parts: list[str] = []
    if atk_roll["advantage"] and not atk_roll["disadvantage"]:
        parts.append(_("adv "))
    elif atk_roll["disadvantage"] and not atk_roll["advantage"]:
        parts.append(_("disadv "))

    parts.append(f"d20({atk_roll['natural']})")

    components = atk_roll["components"]
    assert isinstance(components, list)
    modifier_total = sum(c["value"] for c in components)
    if modifier_total >= 0:
        parts.append(f"+{modifier_total}")
    else:
        parts.append(str(modifier_total))
    parts.append(f"={atk_roll['total']}")
    ac_label = _("AC")
    parts.append(f" vs {ac_label} {ac}")
    return " [" + "".join(parts) + "]"


def _format_damage(damage: object, damage_components: list[dict[str, object]], critical: bool) -> str:
    """Build damage string from structured components.

    Format: , 10 damage (1d8 slashing + 1d6 sneak_attack + 2 dueling)
    """
    detail_parts: list[str] = []
    for dc in damage_components:
        if dc["dice"] and dc["source"] != "weapon":
            detail_parts.append(f"{dc['dice']} {_(str(dc['source']))}")
        elif dc["dice"]:
            detail_parts.append(f"{dc['dice']} {_(str(dc['type']))}")
        elif dc["amount"]:
            detail_parts.append(f"+{dc['amount']} {_(str(dc['source']))}")
    detail = " (" + " + ".join(detail_parts) + ")" if detail_parts else ""

    if critical:
        return _(", CRIT! {damage} damage{detail}").format(damage=damage, detail=detail)
    return _(", {damage} damage{detail}").format(damage=damage, detail=detail)


def _perceive_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    d = event.data
    attacker_id = str(d["attacker_id"])
    target_id = str(d["target_id"])
    hit = d["hit"]
    weapon = d.get("weapon", "")
    critical = d.get("critical", False)
    is_oa = bool(d.get("is_opportunity_attack"))
    atk_roll = d["attack_roll"]
    assert isinstance(atk_roll, dict)

    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)

    weapon_str = f" ({_(str(weapon))})" if weapon else ""
    oa_str = _(" (opportunity attack)") if is_oa else ""
    roll_str = _format_roll(atk_roll, d["ac"])

    if not hit:
        outcome_str = _(", miss")
    elif "damage_components" in d:
        damage_components = d["damage_components"]
        assert isinstance(damage_components, list)
        outcome_str = _format_damage(d["damage"], damage_components, bool(critical))
    elif "damage" in d:
        outcome_str = _(", {damage} damage").format(damage=d["damage"])
    else:
        outcome_str = ""

    if attacker_id == observer.id:
        return _("You attack {target}{weapon}{oa}{roll}{outcome}").format(
            target=target, weapon=weapon_str, oa=oa_str, roll=roll_str, outcome=outcome_str
        )
    if target_id == observer.id:
        return _("{attacker} attacks you{weapon}{oa}{roll}{outcome}").format(
            attacker=attacker, weapon=weapon_str, oa=oa_str, roll=roll_str, outcome=outcome_str
        )
    return _("{attacker} attacks {target}{weapon}{oa}{roll}{outcome}").format(
        attacker=attacker, target=target, weapon=weapon_str, oa=oa_str, roll=roll_str, outcome=outcome_str
    )


def _perceive_disengage(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    if entity_id == observer.id:
        return _("You disengage")
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} disengages").format(entity=desc)


def _perceive_opportunity_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    """Brief contextual note for the OA log marker.

    The detailed attack info is in the preceding ENTITY_ATTACK event
    (annotated with '(opportunity attack)'), so this is kept minimal.
    """
    attacker_id = str(event.data.get("attacker_id", ""))
    target_id = str(event.data.get("target_id", ""))
    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)
    if attacker_id == observer.id:
        return _("You seize the opening against {target}!").format(target=target)
    if target_id == observer.id:
        return _("{attacker} seizes the opening against you!").format(attacker=attacker)
    return _("{attacker} seizes the opening against {target}!").format(attacker=attacker, target=target)


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

    desc_suffix = f" \u00ab{description}\u00bb" if description else ""

    if entity_id == observer.id:
        return _("You move {direction} ({distance} ft){desc}").format(
            direction=dir_label, distance=distance_ft, desc=desc_suffix
        )
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} moves {direction} ({distance} ft){desc}").format(
        entity=desc, direction=dir_label, distance=distance_ft, desc=desc_suffix
    )


def _perceive_dash(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    extra_ft = event.data.get("extra_movement_ft", 0)
    if entity_id == observer.id:
        return _("You dash (+{ft} ft movement)").format(ft=extra_ft)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} dashes (+{ft} ft movement)").format(entity=desc, ft=extra_ft)


def _perceive_use_item(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    item_name = _(str(event.data.get("item_name", "an item")))
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
    weapon_name = _(str(event.data.get("weapon_name", "a weapon")))
    if entity_id == observer.id:
        return _("You equip {weapon}").format(weapon=weapon_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} equips {weapon}").format(entity=desc, weapon=weapon_name)


def _perceive_unequip(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    entity_id = str(event.data.get("entity_id", ""))
    weapon_name = _(str(event.data.get("weapon_name", "a weapon")))
    if entity_id == observer.id:
        return _("You put away {weapon}").format(weapon=weapon_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} puts away {weapon}").format(entity=desc, weapon=weapon_name)


def _perceive_buy(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    buyer_id = str(event.data.get("buyer_id", ""))
    merchant_id = str(event.data.get("merchant_id", ""))
    item_name = _(str(event.data.get("item_name", "an item")))
    price = event.data.get("price", 0)

    merchant = _describe(observer, merchant_id, get_entity)
    if buyer_id == observer.id:
        return _("You buy {item} from {merchant} for {price} gold").format(
            item=item_name, merchant=merchant, price=price
        )
    buyer = _describe(observer, buyer_id, get_entity)
    return _("{buyer} buys {item} from {merchant} for {price} gold").format(
        buyer=buyer, item=item_name, merchant=merchant, price=price
    )


def _perceive_sell(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    seller_id = str(event.data.get("seller_id", ""))
    merchant_id = str(event.data.get("merchant_id", ""))
    item_name = _(str(event.data.get("item_name", "an item")))
    price = event.data.get("price", 0)

    merchant = _describe(observer, merchant_id, get_entity)
    if seller_id == observer.id:
        return _("You sell {item} to {merchant} for {price} gold").format(
            item=item_name, merchant=merchant, price=price
        )
    seller = _describe(observer, seller_id, get_entity)
    return _("{seller} sells {item} to {merchant} for {price} gold").format(
        seller=seller, item=item_name, merchant=merchant, price=price
    )


def _perceive_combat_started(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    names = event.data.get("turn_order_names", [])
    order_str = ", ".join(str(n) for n in names) if names else "?"
    return _("Combat started! Initiative order: {order}").format(order=order_str)


# -- Squad events --


def _perceive_squad_move(event: Event, observer: Character) -> str:
    name = str(event.data.get("squad_name", _("A group")))
    to_loc = event.data.get("to", "")
    from_loc = event.data.get("from", "")
    at_dest = observer.location_id == to_loc
    at_origin = observer.location_id == from_loc
    if at_dest and at_origin:
        return _("{name} passes through").format(name=name)
    if at_dest:
        return _("{name} arrives").format(name=name)
    if at_origin:
        return _("{name} departs").format(name=name)
    return _("{name} is on the move").format(name=name)


def _perceive_squad_combat(event: Event) -> str:
    winner = str(event.data.get("winner_name", _("A group")))
    loser = str(event.data.get("loser_name", _("another group")))
    loser_strength = event.data.get("loser_strength", 1)
    if loser_strength == 0:
        return _("{winner} destroyed {loser}").format(winner=winner, loser=loser)
    return _("{winner} defeated {loser}").format(winner=winner, loser=loser)


def _perceive_squad_materialized(event: Event) -> str:
    name = str(event.data.get("squad_name", _("A group")))
    count = event.data.get("creature_count", 0)
    return _("{name} appears — {count} creatures materialize").format(name=name, count=count)


def _perceive_squad_dematerialized(event: Event) -> str:
    name = str(event.data.get("squad_name", _("A group")))
    return _("{name} moves on, disappearing into the distance").format(name=name)
