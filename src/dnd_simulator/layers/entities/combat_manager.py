"""Combat lifecycle and action resolution for the entities layer."""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _
from dnd_simulator.rules.combat import resolve_attack, roll_initiative
from dnd_simulator.rules.conditions import (
    attacker_has_disadvantage,
    attacks_against_have_advantage,
    attacks_against_have_disadvantage,
    is_auto_crit,
)
from dnd_simulator.rules.movement import grid_distance, move_direction


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
        self._battle_map_configs: dict[str, BattleMap] = battle_map_configs or {}

    # -- Combat queries --

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return list(self._combats)

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combats.get(location_id)

    # -- Combat lifecycle --

    def start_combat(self, location_id: str) -> CombatState:
        """Roll initiative, create battle map, and start combat at a location."""
        creatures = self._active_creatures_at_location(location_id)
        ordered = roll_initiative(creatures)

        # Use pre-configured battle map (with walls etc.) if available, otherwise default
        if location_id in self._battle_map_configs:
            template = self._battle_map_configs[location_id]
            battle_map = BattleMap(width=template.width, height=template.height, walls=list(template._inner_walls))
        else:
            battle_map = BattleMap(width=60, height=60)
        battle_map.place_randomly([c.id for c in creatures])

        combat = CombatState(
            location_id=location_id,
            turn_order=[c.id for c in ordered],
            battle_map=battle_map,
        )
        self._combats[location_id] = combat
        self._attack_this_round[location_id] = False
        for c in creatures:
            c.in_combat = True

        # Log combat start with initiative order
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
        combat.round_number += 1

        if combat.rounds_without_attack >= 2:
            self._end_combat(location_id)

    def _end_combat(self, location_id: str) -> None:
        """End combat at a location: clear in_combat and dodge flags, remove state."""
        for c in self._active_creatures_at_location(location_id):
            c.in_combat = False
            c.is_dodging = False
        self._combats.pop(location_id, None)
        self._attack_this_round.pop(location_id, None)

        self._location_log[location_id].append(
            Event(
                event_type=EventType.COMBAT_ENDED,
                source_layer="entities",
                data={"location_id": location_id},
            )
        )

    def _remove_from_combat(self, location_id: str, entity_id: str) -> None:
        """Remove an entity from combat turn order and map. End combat if ≤1 left."""
        combat = self._combats.get(location_id)
        if not combat:
            return
        if entity_id in combat.turn_order:
            combat.turn_order.remove(entity_id)
        combat.battle_map.remove(entity_id)
        if len(combat.turn_order) <= 1:
            self._end_combat(location_id)

    # -- Action resolution --

    def resolve_dodge(self, event: Event) -> ActionResult:
        """Resolve a dodge action: set is_dodging until next turn."""
        entity_id = str(event.data.get("entity_id", ""))
        entity = self._entities.get(entity_id)
        if isinstance(entity, Creature):
            entity.is_dodging = True
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
        """Resolve an atomic move: single step in a compass direction.

        The brain has already resolved any 'toward/away' into a concrete direction.
        Returns success=False if blocked (wall, occupied cell, off-map).
        """
        entity_id = str(event.data.get("entity_id", ""))
        entity = self._entities.get(entity_id)
        if not isinstance(entity, Creature):
            return ActionResult(success=False, error=_("Creature '{id}' not found.").format(id=entity_id))

        combat = self._combats.get(entity.location_id)
        if not combat:
            return ActionResult(success=False, error=_("No active combat for movement."))

        bm = combat.battle_map
        cur_pos = bm.get_position(entity_id)
        if cur_pos is None:
            return ActionResult(success=False, error=_("Creature not on the battle map."))

        direction = str(event.data.get("direction", ""))
        ft = int(event.data.get("ft", 5))
        new_pos = move_direction(cur_pos, direction, ft, bm, entity_id)

        if new_pos == cur_pos:
            return ActionResult(success=False, error=_("Cannot move there — blocked."))

        bm.set_position(entity_id, new_pos)
        moved_ft = grid_distance(cur_pos, new_pos)

        log_event = Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data={
                "entity_id": entity_id,
                "from_x": cur_pos.x,
                "from_y": cur_pos.y,
                "to_x": new_pos.x,
                "to_y": new_pos.y,
                "distance_ft": moved_ft,
            },
        )
        self._location_log[entity.location_id].append(log_event)
        return ActionResult(success=True)

    def resolve_attack(self, event: Event) -> ActionResult:
        """Validate and resolve an attack: check constraints, roll dice, apply damage, log."""
        attacker_id = str(event.data.get("attacker_id", ""))
        target_id = str(event.data.get("target_id", ""))

        # --- Validation ---
        attacker = self._entities.get(attacker_id)
        if not isinstance(attacker, Creature):
            return ActionResult(success=False, error=_("Attacker '{id}' not found.").format(id=attacker_id))

        target = self._entities.get(target_id)
        if not isinstance(target, Creature):
            return ActionResult(success=False, error=_("Target '{id}' not found.").format(id=target_id))

        if not attacker.is_alive:
            return ActionResult(success=False, error=_("You are dead and cannot attack."))

        if not target.is_alive:
            return ActionResult(success=False, error=_("Target '{id}' is already dead.").format(id=target_id))

        if attacker.location_id != target.location_id:
            return ActionResult(success=False, error=_("Target '{id}' is not in this region.").format(id=target_id))

        # --- Enter combat for all creatures at the location ---
        if attacker.location_id not in self._combats:
            self.start_combat(attacker.location_id)
        self._attack_this_round[attacker.location_id] = True

        # Use equipped (first) attack, or unarmed strike
        if attacker.attacks:
            attack = attacker.attacks[0]
        else:
            attack = Attack(name=_("fist"), ability=Ability.STR, damage=(DamageComponent("1", DamageType.BLUDGEONING),))

        # --- Reach check ---
        combat = self._combats.get(attacker.location_id)
        if combat:
            a_pos = combat.battle_map.get_position(attacker_id)
            t_pos = combat.battle_map.get_position(target_id)
            if a_pos is not None and t_pos is not None:
                dist = grid_distance(a_pos, t_pos)
                if dist > attack.reach:
                    return ActionResult(
                        success=False,
                        error=_("Target too far ({dist} ft, reach {reach} ft).").format(dist=dist, reach=attack.reach),
                    )

        # --- Resolution: compute advantage/disadvantage from conditions ---
        is_melee = attack.reach <= 10
        advantage = attacks_against_have_advantage(target.conditions, melee=is_melee)
        disadvantage = (
            target.is_dodging
            or attacker_has_disadvantage(attacker.conditions)
            or attacks_against_have_disadvantage(target.conditions, melee=is_melee)
        )

        modifier = attacker.ability_scores.modifier(attack.ability)
        result = resolve_attack(
            modifier=modifier,
            ac=target.ac,
            attack=attack,
            advantage=advantage,
            disadvantage=disadvantage,
            force_crit=is_auto_crit(target.conditions, melee=is_melee) if is_melee else False,
        )

        # Build enriched event for the log (with damage info + dice details)
        log_data: dict[str, Any] = {
            "attacker_id": attacker_id,
            "target_id": target_id,
            "weapon": attack.name,
            "hit": result.hit,
            "critical": result.critical,
            "roll": result.attack_check.roll,
            "total": result.attack_check.total,
            "modifier": modifier,
            "ac": target.ac,
            "advantage": advantage,
            "disadvantage": disadvantage,
        }

        result_events: list[Event] = []

        if result.hit:
            actual_damage = target.take_damage(result.total_damage)
            log_data["damage"] = actual_damage
            log_data["damage_types"] = [d.type.value for d in result.damage]
            log_data["damage_detail"] = [{"amount": dr.amount, "type": dr.type.value} for dr in result.damage]

        # Log the attack BEFORE death/combat-end so event order is natural
        attack_log_event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=log_data,
        )
        self._location_log[attacker.location_id].append(attack_log_event)

        if result.hit and not target.is_alive:
            target.in_combat = False
            death_event = Event(
                event_type=EventType.ENTITY_DIED,
                source_layer="entities",
                data={"entity_id": target_id},
            )
            result_events.append(death_event)
            self._location_log[target.location_id].append(death_event)
            # _remove_from_combat may trigger _end_combat → COMBAT_ENDED last
            self._remove_from_combat(target.location_id, target_id)

        return ActionResult(success=True, events=result_events)

    # -- Helpers --

    def _active_creatures_at_location(self, location_id: str, exclude_id: str = "") -> list[Creature]:
        """Get active creatures at a location."""
        return [
            e
            for e in self._entities.values()
            if isinstance(e, Creature) and e.active and e.location_id == location_id and e.id != exclude_id
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
