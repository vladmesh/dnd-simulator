"""Combat lifecycle and action resolution for the entities layer."""

from __future__ import annotations

import structlog

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import ActionResult, Event, EventType, FactionRelation, Query, QueryFn, QueryType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.combat_serialization import deserialize_combats, serialize_combats
from dnd_simulator.rules.combat import AttackResult, resolve_attack, roll_initiative
from dnd_simulator.rules.combat_sides import are_allies, build_combat_sides
from dnd_simulator.rules.handlers.attack_resolution import (
    build_attack_event,
    build_damage_components,
    resolve_combat_move,
    roll_attack_dice,
)
from dnd_simulator.rules.modifiers import attack_modifiers
from dnd_simulator.rules.sneak_attack import check_sneak_attack, find_adjacent_ally
from dnd_simulator.rules.weapons import get_weapon_attack

logger = structlog.get_logger(domain="combat")
DEFAULT_BATTLE_MAP_SIZE = 60
IDLE_ROUNDS_TO_END_COMBAT = 2
INITIAL_REACTION_BUDGET = 1


class CombatManager:
    """Manages combat lifecycle and action resolution.

    Operates on shared entity and log references owned by EntitiesLayer.
    """

    def __init__(
        self,
        entities: dict[str, Entity],
        location_log: dict[str, list[Event]],
        battle_map_configs: dict[str, BattleMap] | None = None,
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combats: dict[str, CombatState] = {}
        self._attack_this_round: dict[str, bool] = {}
        self._sneak_attack_used: set[str] = set()  # creature IDs that used SA this round
        self._battle_map_configs: dict[str, BattleMap] = battle_map_configs or {}

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return list(self._combats)

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combats.get(location_id)

    def start_combat(self, location_id: str, query_fn: QueryFn | None = None) -> CombatState | None:
        """Roll initiative, create battle map, build combat sides, and start combat at a location."""
        creatures = self._active_creatures_at_location(location_id)
        if len(creatures) < 2:
            return None
        ordered = roll_initiative(creatures)

        if location_id in self._battle_map_configs:
            template = self._battle_map_configs[location_id]
            battle_map = BattleMap(width=template.width, height=template.height, walls=list(template._inner_walls))
        else:
            battle_map = BattleMap(width=DEFAULT_BATTLE_MAP_SIZE, height=DEFAULT_BATTLE_MAP_SIZE)
        fixed_ids: set[str] = set()
        for c in creatures:
            if c.combat_position is not None:
                battle_map.set_position(c.id, Position(c.combat_position[0], c.combat_position[1]))
                fixed_ids.add(c.id)
        remaining = [c.id for c in creatures if c.id not in fixed_ids]
        if remaining:
            battle_map.place_randomly(remaining)

        combat = CombatState(
            location_id=location_id,
            turn_order=[c.id for c in ordered],
            battle_map=battle_map,
        )
        if query_fn is not None:

            def get_relation(a: str, b: str) -> FactionRelation:
                answer = query_fn(
                    "politics",
                    Query(question=QueryType.FACTION_RELATION, params={"a": a, "b": b}),
                )
                assert isinstance(answer.value, FactionRelation)
                return answer.value

            combat.sides, combat.entity_to_side = build_combat_sides(creatures, get_relation)

        self._combats[location_id] = combat
        self._attack_this_round[location_id] = False
        for c in creatures:
            c.in_combat = True
            if c.turn_budget is None:  # reaction-only budget for OA before first turn
                c.turn_budget = TurnBudget(
                    actions=0, bonus_actions=0, movement_remaining=0, reaction=INITIAL_REACTION_BUDGET
                )

        logger.info(
            "combat_start",
            location_id=location_id,
            initiative=[(c.id, c.name) for c in ordered],
            map_size=f"{battle_map.width}x{battle_map.height}",
            positions={eid: (pos.x, pos.y) for eid, pos in battle_map.positions.items()},
        )
        self._location_log[location_id].append(
            Event(
                event_type=EventType.COMBAT_STARTED,
                source_layer="entities",
                data={
                    "location_id": location_id,
                    "turn_order": [c.id for c in ordered],
                    "turn_order_names": [c.name for c in ordered],
                },
            )
        )
        return combat

    def reset_turn_state(self, creature_id: str) -> None:
        """Reset per-turn combat state for a creature (sneak attack used, etc.)."""
        self._sneak_attack_used.discard(creature_id)

    def end_combat_round(self, location_id: str) -> None:
        """Called by game loop at end of each combat round."""
        combat = self._combats.get(location_id)
        if not combat:
            return

        if self._attack_this_round.get(location_id, False):
            combat.rounds_without_attack = 0
        else:
            combat.rounds_without_attack += 1
        self._attack_this_round[location_id] = False
        self._sneak_attack_used.clear()
        combat.round_number += 1

        if combat.rounds_without_attack >= IDLE_ROUNDS_TO_END_COMBAT:
            self._end_combat(location_id)

    def _end_combat(self, location_id: str) -> None:
        """End combat at a location: clear in_combat and dodge flags, remove state."""
        for c in self._active_creatures_at_location(location_id):
            c.in_combat = False
            c.is_dodging = False
        self._combats.pop(location_id, None)
        self._attack_this_round.pop(location_id, None)

        logger.info("combat_end", location_id=location_id)
        self._location_log[location_id].append(
            Event(
                event_type=EventType.COMBAT_ENDED,
                source_layer="entities",
                data={"location_id": location_id},
            )
        )

    def _remove_from_combat(self, location_id: str, entity_id: str) -> None:
        """Remove an entity from combat turn order, map, and sides. End combat if no hostility remains."""
        combat = self._combats.get(location_id)
        if not combat:
            return
        if entity_id in combat.turn_order:
            combat.turn_order.remove(entity_id)
        combat.battle_map.remove(entity_id)
        # Clean up sides tracking
        side = combat.entity_to_side.pop(entity_id, None)
        if side is not None and side in combat.sides:
            combat.sides[side].discard(entity_id)
        if len(combat.turn_order) <= 1 or not self._has_opposing_factions(combat):
            self._end_combat(location_id)

    def _has_opposing_factions(self, combat: CombatState) -> bool:
        """Check if alive creatures in combat could still be hostile to each other.

        Uses combat sides when available: counts sides that still have at least
        one alive member. Combat continues if 2+ sides are alive.
        Falls back to faction_id counting when sides are not built.
        """
        alive_ids = {
            eid for eid in combat.turn_order if isinstance((e := self._entities.get(eid)), Creature) and e.is_alive
        }

        if combat.sides:
            alive_sides = sum(1 for members in combat.sides.values() if members & alive_ids)
            return alive_sides >= 2

        # Fallback for combats started without query_fn (no sides built)
        alive = [self._entities[eid] for eid in alive_ids if isinstance(self._entities.get(eid), Creature)]
        if any(not c.faction_id for c in alive):
            return True
        return len({c.faction_id for c in alive}) > 1

    def resolve_dodge(self, event: Event) -> ActionResult:
        """Resolve a dodge action: set is_dodging until next turn."""
        entity_id = str(event.data.get("entity_id", ""))
        entity = self._entities.get(entity_id)
        if isinstance(entity, Creature):
            entity.is_dodging = True
            entity.conditions[Condition.DODGING] = 1
        location_id = self._event_location(event)
        if location_id:
            self._location_log[location_id].append(event)
        return ActionResult()

    def resolve_flee(self, event: Event) -> ActionResult:
        """Resolve a flee attempt: mark the creature as out of combat."""
        entity_id = str(event.data.get("entity_id", ""))
        entity = self._entities.get(entity_id)
        if isinstance(entity, Creature):
            entity.in_combat = False
            self._remove_from_combat(entity.location_id, entity_id)
        location_id = self._event_location(event)
        if location_id:
            self._location_log[location_id].append(event)
        return ActionResult()

    def resolve_move(self, event: Event) -> ActionResult:
        """Resolve an atomic move: single step in a compass direction."""
        entity_id = str(event.data.get("entity_id", ""))
        entity = self._entities.get(entity_id)
        if not isinstance(entity, Creature):
            return ActionResult(success=False, error=_("Creature '{id}' not found.").format(id=entity_id))
        combat = self._combats.get(entity.location_id)
        if not combat:
            return ActionResult(success=False, error=_("No active combat for movement."))
        return resolve_combat_move(entity, event, combat, self._location_log)

    def resolve_attack(self, event: Event, query_fn: QueryFn | None = None) -> ActionResult:
        """Resolve an attack: roll dice, apply damage, log."""
        attacker_id = str(event.data.get("attacker_id", ""))
        target_id = str(event.data.get("target_id", ""))

        attacker = self._entities.get(attacker_id)
        if not isinstance(attacker, Creature):
            return ActionResult(success=False, error=_("Attacker '{id}' not found.").format(id=attacker_id))

        target = self._entities.get(target_id)
        if not isinstance(target, Creature):
            return ActionResult(success=False, error=_("Target '{id}' not found.").format(id=target_id))

        if attacker.location_id not in self._combats:
            self.start_combat(attacker.location_id, query_fn)
        self._attack_this_round[attacker.location_id] = True

        attack = get_weapon_attack(attacker)
        atk_mods = attack_modifiers(attacker, target, melee=attack.reach <= 10)

        rolled_dice, dice_total = roll_attack_dice(atk_mods)
        modifier = atk_mods.modifier + dice_total

        ally_adjacent = False
        combat = self._combats.get(attacker.location_id)
        if combat:
            if combat.entity_to_side:
                is_ally_fn = lambda eid: are_allies(combat, attacker.id, eid)  # noqa: E731
            else:
                is_ally_fn = lambda eid: self._is_faction_friendly(attacker, eid, query_fn)  # noqa: E731
            ally_adjacent = find_adjacent_ally(
                attacker_id=attacker.id,
                target_id=target_id,
                battle_map=combat.battle_map,
                entities=self._entities,
                is_ally=is_ally_fn,
            )
        extra_damage = check_sneak_attack(
            attacker,
            attack,
            advantage=atk_mods.advantage,
            disadvantage=atk_mods.disadvantage,
            already_used=attacker.id in self._sneak_attack_used,
            ally_adjacent=ally_adjacent,
        )

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
        result = resolve_attack(
            modifier=modifier,
            ac=atk_mods.target_ac,
            attack=attack,
            damage_bonus=atk_mods.damage_bonus,
            extra_damage=extra_damage,
            advantage=atk_mods.advantage,
            disadvantage=atk_mods.disadvantage,
            force_crit=atk_mods.force_crit,
            gwf_reroll=atk_mods.gwf_reroll,
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
            if extra_damage and attacker_id not in self._sneak_attack_used:
                for ed in extra_damage:
                    if ed.source == "sneak_attack":
                        self._sneak_attack_used.add(attacker_id)
                        break

        self._location_log[attacker.location_id].append(
            Event(event_type=EventType.ENTITY_ATTACK, source_layer="entities", data=log_data)
        )

        return self._handle_death(target, target_id, result)

    def _is_faction_friendly(self, attacker: Creature, candidate_id: str, query_fn: QueryFn | None) -> bool:
        """Check if candidate is FRIENDLY to attacker via PoliticsLayer faction relation."""
        if query_fn is None:
            return False
        candidate = self._entities.get(candidate_id)
        if not isinstance(candidate, Creature):
            return False
        answer = query_fn(
            "politics",
            Query(question=QueryType.FACTION_RELATION, params={"a": attacker.faction_id, "b": candidate.faction_id}),
        )
        return answer.value == FactionRelation.FRIENDLY

    def _handle_death(self, target: Creature, target_id: str, result: AttackResult) -> ActionResult:
        """Handle target death and combat end if the attack killed the target."""
        if not result.hit or target.is_alive:
            return ActionResult(success=True)
        target.in_combat = False
        death_event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data={"entity_id": target_id},
        )
        self._location_log[target.location_id].append(death_event)
        self._remove_from_combat(target.location_id, target_id)
        return ActionResult(success=True, events=[death_event])

    def get_combats_state(self) -> dict[str, object]:
        """Serialize all active combats."""
        return serialize_combats(self._combats)

    def load_combats_state(self, data: dict[str, object]) -> None:
        """Restore active combats from saved data."""
        self._combats = deserialize_combats(data)

    def _active_creatures_at_location(self, location_id: str, exclude_id: str = "") -> list[Creature]:
        """Get active, alive creatures at a location."""
        return [
            e
            for e in self._entities.values()
            if isinstance(e, Creature)
            and e.active
            and e.is_alive
            and e.location_id == location_id
            and e.id != exclude_id
        ]

    def _event_location(self, event: Event) -> str | None:
        """Determine which location an event happened at."""
        for key in ("entity_id", "attacker_id"):
            eid = event.data.get(key)
            if isinstance(eid, str):
                entity = self._entities.get(eid)
                if entity:
                    return entity.location_id
        return None
