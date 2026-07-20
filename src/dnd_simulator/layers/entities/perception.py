"""Format raw events into subjective text through an observer's perception."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.events import (
    ActionFlavorPayload,
    AttackResolvedPayload,
    AttackRollPayload,
    BuyPayload,
    CombatEndedPayload,
    DamageComponentPayload,
    EntityActorPayload,
    EntityBlessPayload,
    EntityDashPayload,
    EntityDiedPayload,
    EntityLayOnHandsPayload,
    EntityMovePayload,
    EntitySayPayload,
    EntitySecondWindPayload,
    EntityUseItemPayload,
    EquipmentPayload,
    InspectPayload,
    OpportunityAttackPayload,
    ReputationChangedPayload,
    SellPayload,
    SquadDematerializedPayload,
    SquadMaterializedPayload,
    TakePayload,
    TurnSkippedPayload,
    XpGainedPayload,
)
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.perception_world import DISPATCH as WORLD_DISPATCH

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


def _describe(observer: Character, entity_id: str, get_entity: GetEntityFn) -> str:
    """Get observer's perception of an entity by ID."""
    entity = get_entity(entity_id)
    if entity is None:
        return _("someone")
    if entity.id == observer.id:
        return _("you")
    return observer.perceive(entity)


# ---------------------------------------------------------------------------
# Per-event-type handlers
# ---------------------------------------------------------------------------


def _perceive_say(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntitySayPayload)
    speaker_id = payload.entity_id
    text = payload.text

    speaker = _describe(observer, speaker_id, get_entity)
    if speaker_id == observer.id:
        return _('You say: "{text}"').format(text=text)
    return _('{speaker} says: "{text}"').format(speaker=speaker, text=text)


def _format_roll(atk_roll: AttackRollPayload, ac: int) -> str:
    """Build attack roll string from structured components.

    Format: [adv d20(14)+5=19 vs AC 13]
    Components are generic — no knowledge of specific bonuses.
    """
    parts: list[str] = []
    if atk_roll.advantage and not atk_roll.disadvantage:
        parts.append(_("adv "))
    elif atk_roll.disadvantage and not atk_roll.advantage:
        parts.append(_("disadv "))

    parts.append(f"d20({atk_roll.natural})")

    modifier_total = sum(component.value for component in atk_roll.components)
    if modifier_total >= 0:
        parts.append(f"+{modifier_total}")
    else:
        parts.append(str(modifier_total))
    parts.append(f"={atk_roll.total}")
    ac_label = _("AC")
    parts.append(f" vs {ac_label} {ac}")
    return " [" + "".join(parts) + "]"


def _format_damage(damage: int, damage_components: tuple[DamageComponentPayload, ...], critical: bool) -> str:
    """Build damage string from structured components.

    Format: , 10 damage (1d8 slashing + 1d6 sneak_attack + 2 dueling)
    """
    detail_parts: list[str] = []
    for component in damage_components:
        if component.dice and component.source != "weapon":
            detail_parts.append(f"{component.dice} {_(component.source)}")
        elif component.dice:
            detail_parts.append(f"{component.dice} {_(component.type)}")
        elif component.amount:
            detail_parts.append(f"+{component.amount} {_(component.source)}")
    detail = " (" + " + ".join(detail_parts) + ")" if detail_parts else ""

    if critical:
        return _(", CRIT! {damage} damage{detail}").format(damage=damage, detail=detail)
    return _(", {damage} damage{detail}").format(damage=damage, detail=detail)


def _perceive_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, AttackResolvedPayload)
    attacker_id = payload.attacker_id
    target_id = payload.target_id
    hit = payload.hit
    weapon = payload.weapon
    critical = payload.critical
    is_oa = payload.is_opportunity_attack

    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)

    weapon_str = f" ({_(str(weapon))})" if weapon else ""
    oa_str = _(" (opportunity attack)") if is_oa else ""
    roll_str = _format_roll(payload.attack_roll, payload.ac)

    if not hit:
        outcome_str = _(", miss")
    elif payload.damage is not None:
        outcome_str = _format_damage(payload.damage, payload.damage_components, critical)
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


def _perceive_combat_ended(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, CombatEndedPayload)
    return _("Combat ended.")


def _perceive_disengage(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityActorPayload)
    entity_id = payload.entity_id
    if entity_id == observer.id:
        return _("You disengage")
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} disengages").format(entity=desc)


def _perceive_opportunity_attack(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    """Brief contextual note for the OA log marker.

    The detailed attack info is in the preceding ENTITY_ATTACK event
    (annotated with '(opportunity attack)'), so this is kept minimal.
    """
    payload = event.payload
    assert isinstance(payload, OpportunityAttackPayload)
    attacker_id = payload.attacker_id
    target_id = payload.target_id
    attacker = _describe(observer, attacker_id, get_entity)
    target = _describe(observer, target_id, get_entity)
    if attacker_id == observer.id:
        return _("You seize the opening against {target}!").format(target=target)
    if target_id == observer.id:
        return _("{attacker} seizes the opening against you!").format(attacker=attacker)
    return _("{attacker} seizes the opening against {target}!").format(attacker=attacker, target=target)


def _perceive_death(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityDiedPayload)
    entity_id = payload.entity_id
    if entity_id == observer.id:
        return _("You die")
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} dies").format(entity=desc)


def _perceive_dodge(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, ActionFlavorPayload)
    entity_id = payload.entity_id
    description = payload.description

    desc_suffix = f" \u00ab{description}\u00bb" if description else ""
    if entity_id == observer.id:
        return _("You take a defensive stance{desc}").format(desc=desc_suffix)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} takes a defensive stance{desc}").format(entity=desc, desc=desc_suffix)


def _perceive_flee(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, ActionFlavorPayload)
    entity_id = payload.entity_id
    description = payload.description

    desc_suffix = f" \u00ab{description}\u00bb" if description else ""
    if entity_id == observer.id:
        return _("You try to flee{desc}").format(desc=desc_suffix)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} tries to flee{desc}").format(entity=desc, desc=desc_suffix)


def _perceive_move(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    from dnd_simulator.rules.movement import direction_label

    payload = event.payload
    assert isinstance(payload, EntityMovePayload)
    entity_id = payload.entity_id
    description = ""
    distance_ft = payload.distance_ft
    from_x = payload.from_x
    from_y = payload.from_y
    to_x = payload.to_x
    to_y = payload.to_y
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
    payload = event.payload
    assert isinstance(payload, EntityDashPayload)
    entity_id = payload.entity_id
    extra_ft = payload.extra_movement_ft
    if entity_id == observer.id:
        return _("You dash (+{ft} ft movement)").format(ft=extra_ft)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} dashes (+{ft} ft movement)").format(entity=desc, ft=extra_ft)


def _perceive_use_item(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityUseItemPayload)
    entity_id = payload.entity_id
    item_name = _(payload.item_name)
    healed = payload.healed

    if healed == 0:
        if entity_id == observer.id:
            return _("You use {item}, but you are already at full health").format(item=item_name)
        desc = _describe(observer, entity_id, get_entity)
        return _("{entity} uses {item}, but is already at full health").format(entity=desc, item=item_name)
    if entity_id == observer.id:
        return _("You use {item} (healed {hp} HP)").format(item=item_name, hp=healed)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} uses {item} (healed {hp} HP)").format(entity=desc, item=item_name, hp=healed)


def _perceive_inspect(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    from dnd_simulator.core.character import Creature

    payload = event.payload
    assert isinstance(payload, InspectPayload)
    target_id = str(payload.inspect_target)
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
        if target.conditions:
            cond_list = ", ".join(_(c.value) for c in sorted(target.conditions, key=lambda c: c.value))
            parts.append(_("Conditions: {list}.").format(list=cond_list))
    return " ".join(parts)


def _perceive_turn_skipped(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, TurnSkippedPayload)
    entity_id = payload.entity_id
    conditions = payload.conditions

    cond_str = ", ".join(str(c) for c in conditions) if conditions else "?"
    if entity_id == observer.id:
        return _("You can't act ({conditions}) — turn skipped").format(conditions=cond_str)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} can't act ({conditions}) — turn skipped").format(entity=desc, conditions=cond_str)


def _perceive_bless(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityBlessPayload)
    entity_id = payload.entity_id
    duration = payload.duration_rounds
    if entity_id == observer.id:
        return _("You invoke a blessing (+d4 to attack rolls for {n} rounds)").format(n=duration)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} invokes a blessing (+d4 to attack rolls for {n} rounds)").format(entity=desc, n=duration)


def _perceive_second_wind(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntitySecondWindPayload)
    entity_id = payload.entity_id
    healed = payload.healed
    self_acting = entity_id == observer.id
    if healed == 0:
        if self_acting:
            return _("You catch your breath, but you are already at full health")
        desc = _describe(observer, entity_id, get_entity)
        return _("{entity} catches their breath, already at full health").format(entity=desc)
    if self_acting:
        return _("You catch your breath, regaining {hp} HP").format(hp=healed)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} catches their breath, regaining {hp} HP").format(entity=desc, hp=healed)


def _perceive_action_surge(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityActorPayload)
    entity_id = payload.entity_id
    if entity_id == observer.id:
        return _("You surge with energy, gaining an extra action")
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} surges with energy, gaining an extra action").format(entity=desc)


def _perceive_lay_on_hands(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EntityLayOnHandsPayload)
    entity_id = payload.entity_id
    target_id = payload.target_id
    healed = payload.healed
    pool_before = payload.pool_before
    pool_after = payload.pool_after

    self_acting = entity_id == observer.id
    self_target = target_id == observer.id

    if healed == 0:
        if self_acting and self_target:
            return _("You lay hands on yourself, but you are already at full health")
        if self_acting:
            tdesc = _describe(observer, target_id, get_entity)
            return _("You lay hands on {target}, but they are already at full health").format(target=tdesc)
        edesc = _describe(observer, entity_id, get_entity)
        if self_target:
            return _("{entity} lays hands on you, but you are already at full health").format(entity=edesc)
        tdesc = _describe(observer, target_id, get_entity)
        return _("{entity} lays hands on {target}, but they are already at full health").format(
            entity=edesc, target=tdesc
        )
    if self_acting and self_target:
        return _("You lay hands on yourself, restoring {hp} HP (pool {before}→{after})").format(
            hp=healed, before=pool_before, after=pool_after
        )
    if self_acting:
        tdesc = _describe(observer, target_id, get_entity)
        return _("You lay hands on {target}, restoring {hp} HP (pool {before}→{after})").format(
            target=tdesc, hp=healed, before=pool_before, after=pool_after
        )
    edesc = _describe(observer, entity_id, get_entity)
    if self_target:
        return _("{entity} lays hands on you, restoring {hp} HP").format(entity=edesc, hp=healed)
    tdesc = _describe(observer, target_id, get_entity)
    return _("{entity} lays hands on {target}, restoring {hp} HP").format(entity=edesc, target=tdesc, hp=healed)


def _perceive_equip(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EquipmentPayload)
    entity_id = payload.entity_id
    item_name = _(payload.item_name)
    if entity_id == observer.id:
        return _("You equip {weapon}").format(weapon=item_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} equips {weapon}").format(entity=desc, weapon=item_name)


def _perceive_unequip(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, EquipmentPayload)
    entity_id = payload.entity_id
    item_name = _(payload.item_name)
    if entity_id == observer.id:
        return _("You put away {weapon}").format(weapon=item_name)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} puts away {weapon}").format(entity=desc, weapon=item_name)


def _perceive_buy(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, BuyPayload)
    buyer_id = payload.buyer_id
    merchant_id = payload.merchant_id
    item_name = _(payload.item_name)
    price = payload.price

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
    payload = event.payload
    assert isinstance(payload, SellPayload)
    seller_id = payload.seller_id
    merchant_id = payload.merchant_id
    item_name = _(payload.item_name)
    price = payload.price

    merchant = _describe(observer, merchant_id, get_entity)
    if seller_id == observer.id:
        return _("You sell {item} to {merchant} for {price} gold").format(
            item=item_name, merchant=merchant, price=price
        )
    seller = _describe(observer, seller_id, get_entity)
    return _("{seller} sells {item} to {merchant} for {price} gold").format(
        seller=seller, item=item_name, merchant=merchant, price=price
    )


def _perceive_take(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, TakePayload)
    actor_id = payload.actor_id
    target_id = payload.target_id
    item_names = list(payload.item_names)
    gold = payload.gold

    parts: list[str] = []
    if item_names:
        parts.append(", ".join(_(n) for n in item_names))
    if isinstance(gold, int) and gold > 0:
        parts.append(_("{gold} gold").format(gold=gold))
    loot = "; ".join(parts) if parts else _("nothing")

    target = _describe(observer, target_id, get_entity)
    if actor_id == observer.id:
        return _("You loot {target} ({loot})").format(target=target, loot=loot)
    actor = _describe(observer, actor_id, get_entity)
    return _("{actor} loots {target} ({loot})").format(actor=actor, target=target, loot=loot)


def _perceive_squad_materialized(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    d = event.payload
    assert isinstance(d, SquadMaterializedPayload)
    name = d.squad_name
    count = d.creature_count
    return _("{name} appears — {count} creatures materialize").format(name=name, count=count)


def _perceive_squad_dematerialized(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, SquadDematerializedPayload)
    name = payload.squad_name
    return _("{name} moves on, disappearing into the distance").format(name=name)


def _perceive_encounter_spawned(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    """Vague flavor for an encounter spawn. Deliberately hides the monster roster —
    danger-by-place is intentional, the player gets no advance roster."""
    return _("Something stirs nearby")


def _perceive_xp_gained(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, XpGainedPayload)
    entity_id = payload.entity_id
    amount = payload.amount
    source_id = payload.source_entity_id
    source = _describe(observer, source_id, get_entity)
    if entity_id == observer.id:
        return _("You gain {amount} XP for defeating {source}").format(amount=amount, source=source)
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity} gains {amount} XP for defeating {source}").format(entity=desc, amount=amount, source=source)


def _perceive_reputation_change(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    payload = event.payload
    assert isinstance(payload, ReputationChangedPayload)
    entity_id = payload.entity_id
    faction_name = payload.faction_name or payload.faction_id
    old_rep = payload.old_rep
    new_rep = payload.new_rep

    if entity_id == observer.id:
        return _("Your reputation with {faction} changed ({old} → {new})").format(
            faction=faction_name, old=old_rep, new=new_rep
        )
    desc = _describe(observer, entity_id, get_entity)
    return _("{entity}'s reputation with {faction} changed").format(entity=desc, faction=faction_name)


# ---------------------------------------------------------------------------
# Dispatch table: EventType → handler
# ---------------------------------------------------------------------------

_PerceiveHandler = Callable[[Event, Character, GetEntityFn], str]

_DISPATCH: dict[EventType, _PerceiveHandler] = {
    EventType.ENTITY_SAY: _perceive_say,
    EventType.ENTITY_ATTACK: _perceive_attack,
    EventType.COMBAT_ENDED: _perceive_combat_ended,
    EventType.ENTITY_DIED: _perceive_death,
    EventType.ENTITY_DISENGAGE: _perceive_disengage,
    EventType.OPPORTUNITY_ATTACK: _perceive_opportunity_attack,
    EventType.ENTITY_DODGE: _perceive_dodge,
    EventType.ENTITY_FLEE: _perceive_flee,
    EventType.ENTITY_MOVE: _perceive_move,
    EventType.ENTITY_DASH: _perceive_dash,
    EventType.ENTITY_USE_ITEM: _perceive_use_item,
    EventType.ENTITY_BLESS: _perceive_bless,
    EventType.ENTITY_SECOND_WIND: _perceive_second_wind,
    EventType.ENTITY_ACTION_SURGE: _perceive_action_surge,
    EventType.ENTITY_LAY_ON_HANDS: _perceive_lay_on_hands,
    EventType.ENTITY_EQUIP: _perceive_equip,
    EventType.ENTITY_UNEQUIP: _perceive_unequip,
    EventType.ENTITY_BUY: _perceive_buy,
    EventType.ENTITY_SELL: _perceive_sell,
    EventType.ENTITY_TAKE: _perceive_take,
    EventType.TURN_SKIPPED: _perceive_turn_skipped,
    EventType.SQUAD_MATERIALIZED: _perceive_squad_materialized,
    EventType.SQUAD_DEMATERIALIZED: _perceive_squad_dematerialized,
    EventType.ENCOUNTER_SPAWNED: _perceive_encounter_spawned,
    EventType.REPUTATION_CHANGED: _perceive_reputation_change,
    EventType.XP_GAINED: _perceive_xp_gained,
}
_DISPATCH.update(WORLD_DISPATCH)


def perceive_event(event: Event, observer: Character, get_entity: GetEntityFn) -> str:
    """Describe an event from the observer's point of view.

    Uses observer.perceive() to describe participants, so the same event
    looks different to different observers.
    """
    # CUSTOM with inspect_target is a sub-type — check before dispatch
    if (
        event.event_type == EventType.CUSTOM
        and isinstance(event.payload, InspectPayload)
        and event.payload.inspect_target
    ):
        return _perceive_inspect(event, observer, get_entity)

    handler = _DISPATCH.get(event.event_type)
    if handler is not None:
        return handler(event, observer, get_entity)

    return _("Something happened ({type})").format(type=event.event_type.value)
