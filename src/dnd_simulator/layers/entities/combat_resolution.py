"""Combat action resolution — the attack/move/dodge/flee/death half of the entities layer.

Split out of ``CombatManager``, which keeps the combat-state lifecycle (start/end/remove,
sides, serialization). These functions take the manager as their state owner and mutate the
shared entity / log / combat references it owns — the same relationship the layer submodules
have with their layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Character, Creature
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import ActionResult, Event, EventType, FactionRelation, QueryFn
from dnd_simulator.core.queries import query_faction_name, query_faction_relation
from dnd_simulator.i18n import _
from dnd_simulator.rules.combat import AttackResult
from dnd_simulator.rules.combat import resolve_attack as roll_resolve_attack
from dnd_simulator.rules.combat_sides import are_allies
from dnd_simulator.rules.divine_smite import build_smite_damage, validate_smite
from dnd_simulator.rules.handlers.attack_resolution import (
    build_attack_event,
    build_damage_components,
    resolve_combat_move,
    roll_attack_dice,
)
from dnd_simulator.rules.leveling import can_level_up
from dnd_simulator.rules.modifiers import attack_modifiers
from dnd_simulator.rules.reputation import (
    BASE_KILL_REPUTATION_DELTA,
    apply_reputation_drop,
    default_rep_for_faction,
    make_relation_fn,
)
from dnd_simulator.rules.resources import spell_slot_pool_id, use_resource
from dnd_simulator.rules.sneak_attack import check_sneak_attack, find_adjacent_ally
from dnd_simulator.rules.weapons import get_weapon_attack

if TYPE_CHECKING:
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="combat")


def resolve_dodge(mgr: CombatManager, event: Event) -> ActionResult:
    """Resolve a dodge action: set is_dodging until next turn."""
    entity_id = str(event.data.get("entity_id", ""))
    entity = mgr._entities.get(entity_id)
    if isinstance(entity, Creature):
        entity.is_dodging = True
        entity.conditions[Condition.DODGING] = 1
    location_id = mgr._event_location(event)
    if location_id:
        mgr._location_log[location_id].append(event)
    return ActionResult()


def resolve_flee(mgr: CombatManager, event: Event) -> ActionResult:
    """Resolve a flee attempt: mark the creature as out of combat."""
    entity_id = str(event.data.get("entity_id", ""))
    entity = mgr._entities.get(entity_id)
    if isinstance(entity, Creature):
        entity.in_combat = False
        mgr._remove_from_combat(entity.location_id, entity_id)
    location_id = mgr._event_location(event)
    if location_id:
        mgr._location_log[location_id].append(event)
    return ActionResult()


def resolve_move(mgr: CombatManager, event: Event) -> ActionResult:
    """Resolve an atomic move: single step in a compass direction."""
    entity_id = str(event.data.get("entity_id", ""))
    entity = mgr._entities.get(entity_id)
    if not isinstance(entity, Creature):
        return ActionResult(success=False, error=_("Creature '{id}' not found.").format(id=entity_id))
    combat = mgr._combats.get(entity.location_id)
    if not combat:
        return ActionResult(success=False, error=_("No active combat for movement."))
    return resolve_combat_move(entity, event, combat, mgr._location_log)


def is_faction_friendly(mgr: CombatManager, attacker: Creature, candidate_id: str, query_fn: QueryFn | None) -> bool:
    """Check if candidate is FRIENDLY to attacker via PoliticsLayer faction relation."""
    if query_fn is None:
        return False
    candidate = mgr._entities.get(candidate_id)
    if not isinstance(candidate, Creature):
        return False
    relation = query_faction_relation(query_fn, attacker.faction_id, candidate.faction_id)
    return relation is FactionRelation.FRIENDLY


def resolve_attack(mgr: CombatManager, event: Event, query_fn: QueryFn | None = None) -> ActionResult:
    """Resolve an attack: roll dice, apply damage, log."""
    attacker_id = str(event.data.get("attacker_id", ""))
    target_id = str(event.data.get("target_id", ""))

    attacker = mgr._entities.get(attacker_id)
    if not isinstance(attacker, Creature):
        return ActionResult(success=False, error=_("Attacker '{id}' not found.").format(id=attacker_id))

    target = mgr._entities.get(target_id)
    if not isinstance(target, Creature):
        return ActionResult(success=False, error=_("Target '{id}' not found.").format(id=target_id))

    if attacker.location_id not in mgr._combats:
        mgr.start_combat(
            attacker.location_id,
            query_fn,
            forced_opponents={(attacker_id, target_id)},
        )
    mgr._attack_this_round[attacker.location_id] = True

    attack = get_weapon_attack(attacker)
    atk_mods = attack_modifiers(attacker, target, melee=attack.reach <= 10)

    rolled_dice, dice_total = roll_attack_dice(atk_mods, rng=mgr._rng)
    modifier = atk_mods.modifier + dice_total

    ally_adjacent = False
    combat = mgr._combats.get(attacker.location_id)
    if combat:
        if combat.entity_to_side:
            is_ally_fn = lambda eid: are_allies(combat, attacker.id, eid)  # noqa: E731
        else:
            is_ally_fn = lambda eid: is_faction_friendly(mgr, attacker, eid, query_fn)  # noqa: E731
        ally_adjacent = find_adjacent_ally(
            attacker_id=attacker.id,
            target_id=target_id,
            battle_map=combat.battle_map,
            entities=mgr._entities,
            is_ally=is_ally_fn,
        )
    extra_damage = check_sneak_attack(
        attacker,
        attack,
        advantage=atk_mods.advantage,
        disadvantage=atk_mods.disadvantage,
        already_used=attacker.id in mgr._sneak_attack_used,
        ally_adjacent=ally_adjacent,
    )
    if extra_damage:
        sa = extra_damage[0]
        logger.info("sneak_attack", attacker=attacker.name, dice=sa.dice, reason=sa.reason)

    # Divine Smite: validate before attack, add damage, spend slot only on hit.
    smite_slot_level: int | None = None
    raw_smite = event.data.get("smite_slot_level")
    if raw_smite is not None:
        smite_slot_level = int(str(raw_smite))
        smite_error = validate_smite(attacker, smite_slot_level)
        if smite_error is not None:
            return ActionResult(success=False, error=smite_error)
        extra_damage = (*extra_damage, build_smite_damage(smite_slot_level))

    logger.info(
        "attack_roll",
        attacker=attacker.name,
        target=target.name,
        weapon=attack.name,
        modifier=modifier,
        target_ac=atk_mods.target_ac,
        advantage=atk_mods.advantage,
        disadvantage=atk_mods.disadvantage,
    )
    result = roll_resolve_attack(
        modifier=modifier,
        ac=atk_mods.target_ac,
        attack=attack,
        damage_bonus=atk_mods.damage_bonus,
        extra_damage=extra_damage,
        advantage=atk_mods.advantage,
        disadvantage=atk_mods.disadvantage,
        force_crit=atk_mods.force_crit,
        gwf_reroll=atk_mods.gwf_reroll,
        rng=mgr._rng,
    )
    logger.info(
        "attack_result",
        roll=result.attack_check.roll,
        total=result.attack_check.total,
        target_ac=atk_mods.target_ac,
        outcome="CRIT!" if result.critical else ("HIT" if result.hit else "MISS"),
        damage=result.total_damage if result.hit else 0,
    )

    log_data = build_attack_event(attacker_id, target_id, attack, result, atk_mods, rolled_dice)

    if result.hit:
        actual_damage = target.take_damage(result.total_damage)
        log_data["damage"] = actual_damage
        log_data["total_damage"] = result.total_damage
        log_data["damage_components"] = build_damage_components(result, atk_mods.damage_components)
        if extra_damage and attacker_id not in mgr._sneak_attack_used:
            for ed in extra_damage:
                if ed.source == "sneak_attack":
                    mgr._sneak_attack_used.add(attacker_id)
                    break
        if smite_slot_level is not None:
            use_resource(attacker, spell_slot_pool_id(smite_slot_level))

    mgr._location_log[attacker.location_id].append(
        Event(event_type=EventType.ENTITY_ATTACK, source_layer="entities", data=log_data)
    )

    return handle_death(mgr, attacker, target, target_id, result, query_fn)


def handle_death(
    mgr: CombatManager,
    attacker: Creature,
    target: Creature,
    target_id: str,
    result: AttackResult,
    query_fn: QueryFn | None = None,
) -> ActionResult:
    """Handle target death, reputation drop, and combat end."""
    if not result.hit or target.is_alive:
        return ActionResult(success=True)
    target.in_combat = False

    events: list[Event] = []

    death_event = Event(
        event_type=EventType.ENTITY_DIED,
        source_layer="entities",
        data={"entity_id": target_id},
    )
    mgr._location_log[target.location_id].append(death_event)
    events.append(death_event)

    # Build faction relation lookup for proper initial rep calculation
    get_faction_relation = make_relation_fn(query_fn) if query_fn is not None else None

    # Compute old rep before mutation
    if target.faction_id:
        if target.faction_id in attacker.reputation:
            old_rep = attacker.reputation[target.faction_id]
        elif get_faction_relation is not None:
            old_rep = default_rep_for_faction(attacker, target.faction_id, get_faction_relation)
        else:
            old_rep = 100
    else:
        old_rep = 0

    delta = apply_reputation_drop(attacker, target, BASE_KILL_REPUTATION_DELTA, get_faction_relation)
    if delta > 0:
        rep_data: dict[str, object] = {
            "entity_id": attacker.id,
            "faction_id": target.faction_id,
            "old_rep": old_rep,
            "new_rep": old_rep - delta,
            "delta": -delta,
            "reason": "kill",
        }
        if query_fn is not None and target.faction_id:
            faction_name = query_faction_name(query_fn, target.faction_id)
            if faction_name:
                rep_data["faction_name"] = faction_name
        rep_event = Event(
            event_type=EventType.REPUTATION_CHANGED,
            source_layer="entities",
            data=rep_data,
        )
        mgr._location_log[target.location_id].append(rep_event)
        events.append(rep_event)

    # XP grant on kill (Character attackers only, skip zero-value targets like other Characters)
    if isinstance(attacker, Character) and target.xp_value > 0:
        attacker.experience += target.xp_value
        attacker.level_up_available = can_level_up(attacker.experience, attacker.level)
        xp_event = Event(
            event_type=EventType.XP_GAINED,
            source_layer="entities",
            data={
                "entity_id": attacker.id,
                "amount": target.xp_value,
                "new_total": attacker.experience,
                "source_entity_id": target_id,
                "level_up_available": attacker.level_up_available,
            },
        )
        mgr._location_log[target.location_id].append(xp_event)
        events.append(xp_event)

    mgr._remove_from_combat(target.location_id, target_id)
    return ActionResult(success=True, events=events)
