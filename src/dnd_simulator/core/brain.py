"""Brain ABC, rule-based AI, and player brain for creatures."""

from __future__ import annotations

import queue
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, ItemInfo, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.models import EventType
from dnd_simulator.core.tags import NpcTag, find_tags, has_tag

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature

logger = structlog.get_logger(domain="brain")

# Callback type: notified when it's the player's turn (awareness push).
OnTurnCallback = Callable[
    ["Creature", "PeacefulAwareness | CombatAwareness", "list[PerceivedEvent]"],
    None,
]


class Brain(ABC):
    """Strategy for choosing actions. Injected into Creature."""

    @abstractmethod
    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        """Decide what to do this turn. Must return a valid Action."""

    # -- Movement helpers (available to all brains) --

    @staticmethod
    def move_toward_target(target: CombatEntity, awareness: CombatAwareness, ft: int = 5) -> Action:
        """Calculate a concrete move action toward a combat target.

        Uses grid positions from awareness to determine compass direction.
        """
        from dnd_simulator.core.combat import Position
        from dnd_simulator.rules.movement import calculate_direction

        origin = Position(awareness.self_x, awareness.self_y)
        dest = Position(target.x, target.y)
        direction = calculate_direction(origin, dest)
        if not direction:
            return END_TURN  # already at target
        return Action(name=ActionType.MOVE, params={"direction": direction, "ft": ft})

    @staticmethod
    def move_away_from_target(target: CombatEntity, awareness: CombatAwareness, ft: int = 5) -> Action:
        """Calculate a concrete move action away from a combat target."""
        from dnd_simulator.core.combat import Position
        from dnd_simulator.rules.movement import calculate_away_direction

        origin = Position(awareness.self_x, awareness.self_y)
        dest = Position(target.x, target.y)
        direction = calculate_away_direction(origin, dest)
        return Action(name=ActionType.MOVE, params={"direction": direction, "ft": ft})


class RuleBrain(Brain):
    """Utility-scoring combat AI. Peaceful mode = idle.

    Target selection scores each enemy by distance, wound level, and NPC tags
    (hates/fears). Scared NPCs flee earlier. Tag-aware targeting prefers
    hated enemies and avoids loved ones.
    """

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        # If budget has no actions left, end the turn.
        budget = awareness.turn_budget
        if budget is not None and budget.actions <= 0:
            return END_TURN

        if isinstance(awareness, CombatAwareness):
            return self._choose_combat_action(creature, awareness)
        return self._peaceful_action(creature, awareness, events)

    def _peaceful_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        """Peaceful mode: attack hostile factions on sight, respond to speech.

        Returns end_turn instead of idle — in multi-action loop, idle would
        loop forever (it's free). end_turn signals the turn is done.
        """
        # Faction hostility: attack nearest hostile on sight
        hostile = next((n for n in awareness.nearby if n.is_hostile), None)
        if hostile is not None:
            logger.info(
                "rule_hostile_attack",
                creature=creature.id,
                creature_faction=creature.faction_id,
                target=hostile.id,
                target_desc=hostile.description,
            )
            return Action(name=ActionType.ATTACK, params={"target_id": hostile.id})

        response = creature.get_canned_response(awareness.hour)
        if response is None:
            return END_TURN

        heard_speech = any(e.event_type == EventType.ENTITY_SAY and e.actor_id != creature.id for e in events)
        if not heard_speech:
            return END_TURN

        logger.info("rule_say", response=response)
        return Action(name=ActionType.SAY, params={"text": response})

    def _get_tags(self, creature: Creature) -> list[str]:
        """Get NPC tags if available, empty list otherwise."""
        return creature.memory_tags

    def _choose_combat_action(self, creature: Creature, awareness: CombatAwareness) -> Action:
        nearby = awareness.nearby
        if not nearby:
            return Action(name=ActionType.IDLE)

        hp = awareness.self_hp
        max_hp = awareness.self_max_hp
        hp_ratio = hp / max_hp if max_hp > 0 else 0.0

        from dnd_simulator.rules.weapons import get_weapon_attack

        primary_reach = get_weapon_attack(creature).reach
        is_ranged = primary_reach > 10
        budget = awareness.turn_budget

        tags = self._get_tags(creature)

        # Debug: log turn state
        logger.debug(
            "rule_turn_start",
            hp=hp,
            max_hp=max_hp,
            hp_pct=round(hp_ratio * 100),
            speed=awareness.self_speed,
            conditions=[c.value for c in awareness.self_conditions],
            budget_actions=budget.actions if budget else 0,
            budget_move=budget.movement_remaining if budget else 0,
            enemies=len([e for e in nearby if e.is_hostile]),
        )

        # Tag-adjusted thresholds
        flee_threshold = 0.25 if has_tag(tags, NpcTag.SCARED) else 0.15
        dodge_threshold = 0.35 if has_tag(tags, NpcTag.SCARED) else 0.25

        # --- Equip weapon if unarmed and have one in inventory ---
        if ActionType.EQUIP in awareness.available_actions and creature.equipped_weapon is None:
            from dnd_simulator.core.items import ItemType

            weapon = next((i for i in awareness.available_items if "weapon" in i.description.lower()), None)
            if weapon is None:
                # Fallback: pick first item that looks like a weapon from inventory
                weapon = next(
                    (
                        ItemInfo(id=i.id, name=i.name, description=f"weapon: {i.name}", item_type=str(i.item_type))
                        for i in creature.inventory
                        if i.item_type == ItemType.WEAPON
                    ),
                    None,
                )
            if weapon:
                logger.info("rule_equip", weapon=weapon.name)
                return Action(name=ActionType.EQUIP, params={"weapon_id": weapon.id})

        # --- Use healing potion if wounded and available ---
        if hp_ratio < 0.5 and ActionType.USE_ITEM in awareness.available_actions and awareness.available_items:
            potion = next((i for i in awareness.available_items if "heal" in i.description.lower()), None)
            if potion:
                logger.info("rule_use_item", item=potion.name, hp_pct=round(hp_ratio * 100))
                return Action(name=ActionType.USE_ITEM, params={"item_id": potion.id})

        # --- Target selection: score each enemy, tag-aware ---
        hated_ids = find_tags(tags, NpcTag.HATES)
        feared_ids = find_tags(tags, NpcTag.FEARS)
        target = self._pick_target(nearby, primary_reach, hated_ids, feared_ids)
        if target is None:
            return END_TURN  # no hostile targets — nothing to fight
        target_id = target.id
        dist = target.distance_ft
        logger.debug("rule_target_selected", target=target_id, distance_ft=dist)

        # 1. Flee if critically wounded (scared NPCs flee earlier)
        if hp_ratio < flee_threshold:
            logger.info("rule_flee", hp_pct=round(hp_ratio * 100))
            return Action(name=ActionType.FLEE)

        # 2. Dodge if badly hurt and enemy in melee reach
        nearest_dist = min(e.distance_ft for e in nearby)
        if hp_ratio < dodge_threshold and nearest_dist <= 5:
            logger.info("rule_dodge", hp_pct=round(hp_ratio * 100))
            return Action(name=ActionType.DODGE)

        # 3. Ranged attacker: shoot if target in range, move closer if not
        if is_ranged and dist <= primary_reach:
            logger.info("rule_attack", target=target_id, ranged=True, distance_ft=dist)
            return Action(name=ActionType.ATTACK, params={"target_id": target_id})

        # 4. Melee: attack if in weapon reach
        if dist <= primary_reach:
            logger.info("rule_attack", target=target_id, distance_ft=dist)
            return Action(name=ActionType.ATTACK, params={"target_id": target_id})

        # 5. Move toward if have movement remaining
        movement_left = budget.movement_remaining if budget else 0
        if movement_left > 0:
            logger.info("rule_move_toward", target=target_id, distance_ft=dist)
            return self.move_toward_target(target, awareness)

        # 6. Dash to get more movement (if have actions)
        has_actions = (budget.actions if budget else 0) > 0
        if has_actions:
            logger.info("rule_dash", distance_ft=dist)
            return Action(name=ActionType.DASH)

        logger.debug(
            "rule_end_turn",
            budget_actions=budget.actions if budget else 0,
            budget_move=movement_left,
        )
        return END_TURN

    def _pick_target(
        self,
        nearby: list[CombatEntity],
        reach: int,
        hated_ids: list[str] | None = None,
        feared_ids: list[str] | None = None,
    ) -> CombatEntity | None:
        """Score hostile enemies and pick best target. Returns None if no hostile targets."""
        hostile_nearby = [e for e in nearby if e.is_hostile]
        if not hostile_nearby:
            return None

        best: CombatEntity | None = None
        best_score = -999.0
        _hated = set(hated_ids or [])
        _feared = set(feared_ids or [])

        for enemy in hostile_nearby:
            dist = enemy.distance_ft
            eid = enemy.id

            score = 0.0
            if eid in _hated:
                score += 60.0
            if eid in _feared:
                score += 25.0
            if enemy.is_hostile:
                score += 40.0
            if enemy.is_wounded:
                score += 50.0
            if dist <= reach:
                score += 30.0
            score += max(0.0, 20.0 - dist * 0.2)

            logger.debug(
                "rule_score_target",
                target=eid,
                distance_ft=dist,
                wounded=enemy.is_wounded,
                conditions=[c.value for c in enemy.conditions] if enemy.conditions else [],
                score=round(score),
            )

            if score > best_score:
                best_score = score
                best = enemy

        return best if best is not None else hostile_nearby[0]


class PlayerBrain(Brain):
    """Brain controlled by external input via queue + on_turn callback.

    When it's the player's turn, on_turn fires (so transport can send awareness).
    Then choose_action blocks on the queue until transport calls submit_action().
    """

    def __init__(self) -> None:
        self._action_queue: queue.Queue[Action] = queue.Queue()
        self._on_turn: OnTurnCallback | None = None

    def set_on_turn(self, callback: OnTurnCallback) -> None:
        """Transport sets this to receive awareness when it's the player's turn."""
        self._on_turn = callback

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        if self._on_turn:
            self._on_turn(creature, awareness, events)
        return self._action_queue.get()

    def submit_action(self, action: Action) -> None:
        """Called by transport to provide the player's chosen action."""
        self._action_queue.put(action)
