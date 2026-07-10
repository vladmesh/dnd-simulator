"""Combat lifecycle and action resolution for the entities layer."""

from __future__ import annotations

import random

import structlog

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import ActionResult, Event, EventType, FactionRelation, QueryFn
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities import combat_resolution
from dnd_simulator.layers.entities.combat_serialization import deserialize_combats, serialize_combats
from dnd_simulator.rules.combat import roll_initiative
from dnd_simulator.rules.combat_sides import build_combat_sides
from dnd_simulator.rules.reputation import (
    effective_relation,
    make_relation_fn,
)

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
        rng: random.Random | None = None,
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combats: dict[str, CombatState] = {}
        self._attack_this_round: dict[str, bool] = {}
        self._sneak_attack_used: set[str] = set()  # creature IDs that used SA this round
        self._battle_map_configs: dict[str, BattleMap] = battle_map_configs or {}
        self._rng = rng or random.Random()

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return list(self._combats)

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combats.get(location_id)

    def start_combat(
        self,
        location_id: str,
        query_fn: QueryFn | None = None,
        forced_opponents: set[tuple[str, str]] | None = None,
    ) -> CombatState | None:
        """Roll initiative, create battle map, build combat sides, and start combat at a location."""
        creatures = self._active_creatures_at_location(location_id)
        if len(creatures) < 2:
            return None
        ordered = roll_initiative(creatures, rng=self._rng)

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
            battle_map.place_randomly(remaining, rng=self._rng)

        combat = CombatState(
            location_id=location_id,
            turn_order=[c.id for c in ordered],
            battle_map=battle_map,
        )
        if query_fn is not None:
            get_faction_relation = make_relation_fn(query_fn)

            def get_creature_relation(a: Creature, b: Creature) -> FactionRelation:
                return effective_relation(a, b, get_faction_relation)

            combat.sides, combat.entity_to_side = build_combat_sides(
                creatures, get_creature_relation, forced_opponents=forced_opponents
            )

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
        return combat_resolution.resolve_dodge(self, event)

    def resolve_flee(self, event: Event) -> ActionResult:
        """Resolve a flee attempt: mark the creature as out of combat."""
        return combat_resolution.resolve_flee(self, event)

    def resolve_move(self, event: Event) -> ActionResult:
        """Resolve an atomic move: single step in a compass direction."""
        return combat_resolution.resolve_move(self, event)

    def resolve_attack(self, event: Event, query_fn: QueryFn | None = None) -> ActionResult:
        """Resolve an attack: roll dice, apply damage, log."""
        return combat_resolution.resolve_attack(self, event, query_fn)

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
