"""Combat lifecycle and action resolution for the entities layer."""

from __future__ import annotations

import structlog

from dnd_simulator.core.character import Attack, Creature, DamageType, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.modifiers import AttackModifiers, RollComponent
from dnd_simulator.i18n import _
from dnd_simulator.rules.combat import AttackResult, ExtraDamage, resolve_attack, roll_initiative
from dnd_simulator.rules.modifiers import attack_modifiers
from dnd_simulator.rules.movement import grid_distance, move_direction
from dnd_simulator.rules.sneak_attack import is_sneak_attack_eligible, sneak_attack_dice
from dnd_simulator.rules.weapons import get_weapon_attack

logger = structlog.get_logger(domain="combat")


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

    # -- Combat queries --

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return list(self._combats)

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combats.get(location_id)

    # -- Combat lifecycle --

    def start_combat(self, location_id: str) -> CombatState | None:
        """Roll initiative, create battle map, and start combat at a location.

        Returns None if fewer than 2 alive creatures are present.
        """
        creatures = self._active_creatures_at_location(location_id)
        if len(creatures) < 2:
            return None
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

        initiative = [(c.id, c.name) for c in ordered]
        positions = {eid: (pos.x, pos.y) for eid, pos in battle_map.positions.items()}
        logger.info(
            "combat_start",
            location_id=location_id,
            initiative=initiative,
            map_size=f"{battle_map.width}x{battle_map.height}",
            positions=positions,
            battle_map="\n" + battle_map.render_ascii(),
        )

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
        self._sneak_attack_used.clear()
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

        logger.info("combat_end", location_id=location_id)

        self._location_log[location_id].append(
            Event(
                event_type=EventType.COMBAT_ENDED,
                source_layer="entities",
                data={"location_id": location_id},
            )
        )

    def _remove_from_combat(self, location_id: str, entity_id: str) -> None:
        """Remove an entity from combat turn order and map. End combat if no hostility remains."""
        combat = self._combats.get(location_id)
        if not combat:
            return
        if entity_id in combat.turn_order:
            combat.turn_order.remove(entity_id)
        combat.battle_map.remove(entity_id)
        if len(combat.turn_order) <= 1 or not self._has_opposing_factions(combat):
            self._end_combat(location_id)

    def _has_opposing_factions(self, combat: CombatState) -> bool:
        """Check if alive creatures in combat could still be hostile to each other.

        Returns True (keep fighting) if:
        - Any creature lacks a faction (unknown hostility — assume hostile)
        - Two or more different factions are present
        """
        alive: list[Creature] = []
        for eid in combat.turn_order:
            e = self._entities.get(eid)
            if isinstance(e, Creature) and e.is_alive:
                alive.append(e)
        if any(not c.faction_id for c in alive):
            return True  # unknown faction — can't prove they're allies
        factions = {c.faction_id for c in alive}
        return len(factions) > 1

    # -- Action resolution --

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
            logger.info(
                "move_blocked",
                entity_id=entity_id,
                pos=(cur_pos.x, cur_pos.y),
                direction=direction,
                battle_map="\n" + bm.render_ascii(),
            )
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
        """Resolve an attack: roll dice, apply damage, log.

        Preconditions (alive, target valid, same location, reach) are checked
        by the validator before dispatch. This method only does mechanics.
        """
        attacker_id = str(event.data.get("attacker_id", ""))
        target_id = str(event.data.get("target_id", ""))

        attacker = self._entities.get(attacker_id)
        if not isinstance(attacker, Creature):
            return ActionResult(success=False, error=_("Attacker '{id}' not found.").format(id=attacker_id))

        target = self._entities.get(target_id)
        if not isinstance(target, Creature):
            return ActionResult(success=False, error=_("Target '{id}' not found.").format(id=target_id))

        if attacker.location_id not in self._combats:
            self.start_combat(attacker.location_id)
        self._attack_this_round[attacker.location_id] = True

        attack = get_weapon_attack(attacker)
        atk_mods = attack_modifiers(attacker, target, melee=attack.reach <= 10)

        rolled_dice, dice_total = self._roll_attack_dice(attacker, attack, atk_mods)
        modifier = atk_mods.modifier + dice_total
        extra_damage = self._check_sneak_attack(attacker, attack, target_id, atk_mods.advantage, atk_mods.disadvantage)

        logger.info(
            "attack_roll",
            attacker=attacker.name,
            target=target.name,
            weapon=attack.name,
            modifier=modifier,
            base_mod=atk_mods.modifier,
            dice_bonus=dice_total,
            advantage=atk_mods.advantage,
            disadvantage=atk_mods.disadvantage,
            force_crit=atk_mods.force_crit,
            target_ac=atk_mods.target_ac,
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
        )

        hit_str = "CRIT!" if result.critical else ("HIT" if result.hit else "MISS")
        logger.info(
            "attack_result",
            roll=result.attack_check.roll,
            total=result.attack_check.total,
            target_ac=atk_mods.target_ac,
            outcome=hit_str,
            damage=result.total_damage if result.hit else 0,
        )

        log_data = self._build_attack_event(attacker_id, target_id, attack, result, atk_mods, rolled_dice)

        if result.hit:
            actual_damage = target.take_damage(result.total_damage)
            log_data["damage"] = actual_damage
            log_data["damage_components"] = self._build_damage_components(result, atk_mods)
            # Mark sneak attack as used only on hit (D&D 5e PHB p.96)
            if extra_damage and attacker_id not in self._sneak_attack_used:
                for ed in extra_damage:
                    if ed.source == "sneak_attack":
                        self._sneak_attack_used.add(attacker_id)
                        break

        self._location_log[attacker.location_id].append(
            Event(event_type=EventType.ENTITY_ATTACK, source_layer="entities", data=log_data)
        )

        return self._handle_death(target, target_id, result)

    def _roll_attack_dice(
        self,
        attacker: Creature,
        attack: Attack,
        atk_mods: AttackModifiers,
    ) -> tuple[list[RollComponent], int]:
        """Roll dice bonuses (Bless +1d4, etc.). Returns (rolled_components, total)."""
        rolled_dice: list[RollComponent] = []
        dice_total = 0
        if atk_mods.dice_bonuses:
            from dnd_simulator.rules.dice import roll as roll_dice_fn

            for rc in atk_mods.roll_components:
                if rc.dice:
                    rolled_value = roll_dice_fn(rc.dice)
                    rolled_dice.append(RollComponent(source=rc.source, value=rolled_value, dice=rc.dice))
                    dice_total += rolled_value
            logger.debug(
                "dice_bonuses",
                attacker=attacker.name,
                bonus=dice_total,
                dice=atk_mods.dice_bonuses,
                weapon=attack.name,
            )
        return rolled_dice, dice_total

    def _check_sneak_attack(
        self,
        attacker: Creature,
        attack: Attack,
        target_id: str,
        advantage: bool,
        disadvantage: bool,
    ) -> tuple[ExtraDamage, ...]:
        """Check sneak attack eligibility including ally adjacency on battle map."""
        sa_dice = sneak_attack_dice(attacker)
        if sa_dice == 0 or attacker.id in self._sneak_attack_used:
            return ()

        ally_adjacent = False
        combat = self._combats.get(attacker.location_id)
        if combat:
            target_pos = combat.battle_map.get_position(target_id)
            if target_pos:
                for eid, pos in combat.battle_map.positions.items():
                    if eid in (attacker.id, target_id):
                        continue
                    e = self._entities.get(eid)
                    if isinstance(e, Creature) and e.is_alive and grid_distance(target_pos, pos) <= 5:
                        ally_adjacent = True
                        break

        if is_sneak_attack_eligible(
            attacker,
            attack,
            has_advantage=advantage,
            has_disadvantage=disadvantage,
            ally_adjacent_to_target=ally_adjacent,
        ):
            sa_expr = f"{sa_dice}d6"
            # Don't mark as used here — only on hit (D&D 5e: "deal extra damage
            # to one creature you hit"). Marked in resolve_attack after hit check.
            logger.info(
                "sneak_attack",
                attacker=attacker.name,
                dice=sa_expr,
                reason="advantage" if advantage else "ally_adjacent",
            )
            return (ExtraDamage(dice=sa_expr, type=DamageType.PIERCING, source="sneak_attack"),)
        return ()

    def _build_attack_event(
        self,
        attacker_id: str,
        target_id: str,
        attack: Attack,
        result: AttackResult,
        atk_mods: AttackModifiers,
        rolled_dice: list[RollComponent],
    ) -> dict[str, object]:
        """Build structured attack event data from resolution result."""
        all_roll_components = [
            {"source": rc.source, "value": rc.value, "dice": rc.dice} for rc in atk_mods.roll_components if not rc.dice
        ] + [{"source": rc.source, "value": rc.value, "dice": rc.dice} for rc in rolled_dice]

        return {
            "attacker_id": attacker_id,
            "target_id": target_id,
            "weapon": attack.name,
            "hit": result.hit,
            "critical": result.critical,
            "ac": atk_mods.target_ac,
            "attack_roll": {
                "natural": result.attack_check.roll,
                "components": all_roll_components,
                "total": result.attack_check.total,
                "advantage": atk_mods.advantage,
                "disadvantage": atk_mods.disadvantage,
            },
        }

    @staticmethod
    def _build_damage_components(
        result: AttackResult,
        atk_mods: AttackModifiers,
    ) -> list[dict[str, object]]:
        """Build damage component list for event data."""
        components: list[dict[str, object]] = [
            {"source": dr.source, "dice": dr.dice, "amount": dr.amount, "type": dr.type.value} for dr in result.damage
        ]
        for dbc in atk_mods.damage_components:
            components.append(
                {"source": dbc.source, "dice": "", "amount": dbc.value, "type": result.damage[0].type.value}
            )
        return components

    def _handle_death(self, target: Creature, target_id: str, result: AttackResult) -> ActionResult:
        """Handle target death and combat end if the attack killed the target."""
        result_events: list[Event] = []
        if result.hit and not target.is_alive:
            target.in_combat = False
            death_event = Event(
                event_type=EventType.ENTITY_DIED,
                source_layer="entities",
                data={"entity_id": target_id},
            )
            result_events.append(death_event)
            self._location_log[target.location_id].append(death_event)
            self._remove_from_combat(target.location_id, target_id)
        return ActionResult(success=True, events=result_events)

    # -- Helpers --

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
