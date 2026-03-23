"""Brain ABC, rule-based AI, and player brain for creatures."""

from __future__ import annotations

import logging
import queue
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from dnd_simulator.core.action import END_TURN, Action
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.models import EventType
from dnd_simulator.core.tags import NpcTag, find_tags, has_tag

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature

logger = logging.getLogger("dnd_simulator.brain")

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
        return Action(name="move", params={"direction": direction, "ft": ft})

    @staticmethod
    def move_away_from_target(target: CombatEntity, awareness: CombatAwareness, ft: int = 5) -> Action:
        """Calculate a concrete move action away from a combat target."""
        from dnd_simulator.core.combat import Position
        from dnd_simulator.rules.movement import calculate_away_direction

        origin = Position(awareness.self_x, awareness.self_y)
        dest = Position(target.x, target.y)
        direction = calculate_away_direction(origin, dest)
        return Action(name="move", params={"direction": direction, "ft": ft})


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
        """Peaceful mode: respond with canned line if someone spoke nearby.

        Returns end_turn instead of idle — in multi-action loop, idle would
        loop forever (it's free). end_turn signals the turn is done.
        """
        response = creature.get_canned_response(awareness.hour)
        if response is None:
            return END_TURN

        heard_speech = any(e.event_type == EventType.ENTITY_SAY and e.actor_id != creature.id for e in events)
        if not heard_speech:
            return END_TURN

        logger.info("[RuleBrain:%s] → say (canned: %s)", creature.name, response)
        return Action(name="say", params={"text": response})

    def _get_tags(self, creature: Creature) -> list[str]:
        """Get NPC tags if available, empty list otherwise."""
        return creature.memory_tags

    def _choose_combat_action(self, creature: Creature, awareness: CombatAwareness) -> Action:
        nearby = awareness.nearby
        if not nearby:
            return Action(name="idle")

        hp = awareness.self_hp
        max_hp = awareness.self_max_hp
        hp_ratio = hp / max_hp if max_hp > 0 else 0.0

        primary_reach = creature.attacks[0].reach if creature.attacks else 5
        is_ranged = primary_reach > 10
        budget = awareness.turn_budget

        tags = self._get_tags(creature)

        # Debug: log turn state
        conditions_str = ", ".join(c.value for c in awareness.self_conditions) if awareness.self_conditions else "none"
        logger.debug(
            "[RuleBrain:%s] turn start: HP=%d/%d (%.0f%%), speed=%d, conditions=[%s], "
            "budget=[actions=%d, move=%dft], enemies=%d",
            creature.name,
            hp,
            max_hp,
            hp_ratio * 100,
            awareness.self_speed,
            conditions_str,
            budget.actions if budget else 0,
            budget.movement_remaining if budget else 0,
            len(nearby),
        )

        # Tag-adjusted thresholds
        flee_threshold = 0.25 if has_tag(tags, NpcTag.SCARED) else 0.15
        dodge_threshold = 0.35 if has_tag(tags, NpcTag.SCARED) else 0.25

        # --- Target selection: score each enemy, tag-aware ---
        hated_ids = find_tags(tags, NpcTag.HATES)
        feared_ids = find_tags(tags, NpcTag.FEARS)
        target = self._pick_target(nearby, primary_reach, hated_ids, feared_ids)
        target_id = target.id
        dist = target.distance_ft
        logger.debug("[RuleBrain:%s] target=%s dist=%dft", creature.name, target_id, dist)

        # 1. Flee if critically wounded (scared NPCs flee earlier)
        if hp_ratio < flee_threshold:
            logger.info("[RuleBrain:%s] → flee (HP %.0f%%)", creature.name, hp_ratio * 100)
            return Action(name="flee")

        # 2. Dodge if badly hurt and enemy in melee reach
        nearest_dist = min(e.distance_ft for e in nearby)
        if hp_ratio < dodge_threshold and nearest_dist <= 5:
            logger.info("[RuleBrain:%s] → dodge (HP %.0f%%)", creature.name, hp_ratio * 100)
            return Action(name="dodge")

        # 3. Ranged attacker: shoot if target in range, move closer if not
        if is_ranged and dist <= primary_reach:
            logger.info("[RuleBrain:%s] → attack %s (ranged, dist %d ft)", creature.name, target_id, dist)
            return Action(name="attack", params={"target_id": target_id})

        # 4. Melee: attack if in weapon reach
        if dist <= primary_reach:
            logger.info("[RuleBrain:%s] → attack %s (dist %d ft)", creature.name, target_id, dist)
            return Action(name="attack", params={"target_id": target_id})

        # 5. Move toward if have movement remaining
        movement_left = budget.movement_remaining if budget else 0
        if movement_left > 0:
            logger.info("[RuleBrain:%s] → move toward %s (dist %d ft)", creature.name, target_id, dist)
            return self.move_toward_target(target, awareness)

        # 6. Dash to get more movement (if have actions)
        has_actions = (budget.actions if budget else 0) > 0
        if has_actions:
            logger.info("[RuleBrain:%s] → dash (dist %d ft)", creature.name, dist)
            return Action(name="dash")

        logger.debug(
            "[RuleBrain:%s] → end_turn (no budget: actions=%d, move=%dft)",
            creature.name,
            budget.actions if budget else 0,
            movement_left,
        )
        return END_TURN

    def _pick_target(
        self,
        nearby: list[CombatEntity],
        reach: int,
        hated_ids: list[str] | None = None,
        feared_ids: list[str] | None = None,
    ) -> CombatEntity:
        """Score enemies and pick best target."""
        best: CombatEntity | None = None
        best_score = -999.0
        _hated = set(hated_ids or [])
        _feared = set(feared_ids or [])

        for enemy in nearby:
            dist = enemy.distance_ft
            eid = enemy.id

            score = 0.0
            if eid in _hated:
                score += 60.0
            if eid in _feared:
                score += 25.0
            if enemy.is_wounded:
                score += 50.0
            if dist <= reach:
                score += 30.0
            score += max(0.0, 20.0 - dist * 0.2)

            conds = ", ".join(sorted(c.value for c in enemy.conditions)) if enemy.conditions else ""
            logger.debug(
                "  target %s: dist=%dft wounded=%s conds=[%s] score=%.0f",
                eid,
                dist,
                enemy.is_wounded,
                conds,
                score,
            )

            if score > best_score:
                best_score = score
                best = enemy

        return best if best is not None else nearby[0]


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
