"""Brain ABC and rule-based AI for creatures."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.action import Action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.world import World

logger = logging.getLogger("dnd_simulator.brain")


class Brain(ABC):
    """Strategy for choosing actions. Injected into Creature."""

    @abstractmethod
    def choose_action(self, creature: Creature, world: World) -> Action:
        """Decide what to do this turn. Must return a valid Action."""


class RuleBrain(Brain):
    """Utility-scoring combat AI. Peaceful mode = idle.

    Target selection scores each enemy by distance, wound level, and NPC tags
    (hates/fears). Scared NPCs flee earlier. Tag-aware targeting prefers
    hated enemies and avoids loved ones.
    """

    def choose_action(self, creature: Creature, world: World) -> Action:
        if not creature.in_combat:
            return self._peaceful_action(creature, world)

        from dnd_simulator.core.character import Character, build_combat_awareness

        if not isinstance(creature, Character):
            return Action(name="idle")

        awareness = build_combat_awareness(world, creature)
        return self._choose_combat_action(creature, awareness)

    def _peaceful_action(self, creature: Creature, world: World) -> Action:
        """Peaceful mode: respond with canned line if someone spoke nearby."""
        from dnd_simulator.core.models import Query
        from dnd_simulator.layers.entities.models import Npc, canned_line

        if not isinstance(creature, Npc):
            return Action(name="idle")

        # Check for new speech events in the location log (raw events, not perceived strings)
        answer = world.query_layer("entities", Query(question="new_raw_events", params={"entity_id": creature.id}))
        if not answer.value:
            return Action(name="idle")
        from dnd_simulator.core.models import EventType

        heard_speech = any(
            e.event_type == EventType.ENTITY_SAY and e.data.get("entity_id") != creature.id for e in answer.value
        )
        if not heard_speech:
            return Action(name="idle")

        hour = world.time.hour
        activity = creature.scheduled_activity(hour)
        line = canned_line(creature.role, activity, creature.memory.tags)
        logger.info("[RuleBrain:%s] → say (canned: %s)", creature.name, line)
        return Action(name="say", params={"text": line})

    def _get_tags(self, creature: Creature) -> list[str]:
        """Get NPC tags if available, empty list otherwise."""
        from dnd_simulator.layers.entities.models import Npc

        if isinstance(creature, Npc):
            return creature.memory.tags
        return []

    def _choose_combat_action(self, creature: Creature, awareness: dict[str, Any]) -> Action:
        from dnd_simulator.layers.entities.models import NpcTag, find_tags, has_tag

        nearby = awareness["nearby"]
        if not nearby:
            return Action(name="idle")

        hp: int = awareness["self_hp"]
        max_hp: int = awareness["self_max_hp"]
        speed: int = awareness["self_speed"]
        hp_ratio = hp / max_hp if max_hp > 0 else 0.0

        primary_reach = creature.attacks[0].reach if creature.attacks else 5
        is_ranged = primary_reach > 10

        tags = self._get_tags(creature)

        # Tag-adjusted thresholds
        flee_threshold = 0.25 if has_tag(tags, NpcTag.SCARED) else 0.15
        dodge_threshold = 0.35 if has_tag(tags, NpcTag.SCARED) else 0.25

        # --- Target selection: score each enemy, tag-aware ---
        hated_ids = find_tags(tags, NpcTag.HATES)
        feared_ids = find_tags(tags, NpcTag.FEARS)
        target = self._pick_target(nearby, primary_reach, hated_ids, feared_ids)
        target_id = str(target["id"])
        dist = int(str(target.get("distance_ft", 999)))

        # 1. Flee if critically wounded (scared NPCs flee earlier)
        if hp_ratio < flee_threshold:
            logger.info("[RuleBrain:%s] → flee (HP %.0f%%)", creature.name, hp_ratio * 100)
            return Action(name="flee")

        # 2. Dodge if badly hurt and enemy in melee reach
        nearest_dist = min(int(str(e.get("distance_ft", 999))) for e in nearby)
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

        # 5. Move toward if within one move + reach
        if dist <= speed + primary_reach:
            logger.info("[RuleBrain:%s] → move toward %s (dist %d ft)", creature.name, target_id, dist)
            return Action(name="move", params={"toward": target_id})

        # 6. Dash toward otherwise
        logger.info("[RuleBrain:%s] → dash toward %s (dist %d ft)", creature.name, target_id, dist)
        return Action(name="dash", params={"toward": target_id})

    def _pick_target(
        self,
        nearby: list[dict[str, object]],
        reach: int,
        hated_ids: list[str] | None = None,
        feared_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """Score enemies and pick best target.

        Scoring: prefer wounded targets, hated targets get a large bonus,
        feared targets get a smaller bonus (threat awareness),
        closer targets preferred. Enemies in weapon reach get a bonus.
        """
        best: dict[str, object] | None = None
        best_score = -999.0
        _hated = set(hated_ids or [])
        _feared = set(feared_ids or [])

        for enemy in nearby:
            dist = int(str(enemy.get("distance_ft", 999)))
            eid = str(enemy.get("id", ""))

            score = 0.0
            # Hated targets: strong priority
            if eid in _hated:
                score += 60.0
            # Feared targets: moderate priority (eliminate the threat)
            if eid in _feared:
                score += 25.0
            # Wounded targets are high priority (finish them off)
            if enemy.get("is_wounded", False):
                score += 50.0
            # Prefer enemies in weapon reach (can attack this turn)
            if dist <= reach:
                score += 30.0
            # Prefer closer targets (normalized: 0 at max range, 20 at melee)
            score += max(0.0, 20.0 - dist * 0.2)

            if score > best_score:
                best_score = score
                best = enemy

        return best if best is not None else nearby[0]
