"""RuleBrain — utility-scoring combat AI.

Lives in rules/ because it consumes rules/* (movement, weapons, resources, actions).
The Brain ABC stays in core/brain.py as the shared interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, ItemInfo, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.inner_self import Mood, RelationshipType
from dnd_simulator.core.models import EventType
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.rules.actions import collect_cost_overrides
from dnd_simulator.rules.flee import enemy_blocks_flee
from dnd_simulator.rules.movement import compute_reachable, grid_distance, path_cost, unbounded_budget
from dnd_simulator.rules.resources import get_available_spell_slots
from dnd_simulator.rules.weapons import get_weapon_attack

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.combat import BattleMap, Position

# --- RuleBrain threshold constants ---
FLEE_HP_THRESHOLD = 0.15
DODGE_HP_THRESHOLD = 0.25
POTION_HP_THRESHOLD = 0.50
SCARED_FLEE_HP_THRESHOLD = 0.25
SCARED_DODGE_HP_THRESHOLD = 0.35

# Map id of the deciding creature on the brain's reconstructed battle-map view.
_SELF_ID = "__self__"


@dataclass(frozen=True)
class _CombatContext:
    """Shared state for RuleBrain decision helpers within a single turn."""

    creature: Creature
    awareness: CombatAwareness
    hp_ratio: float
    primary_reach: int
    is_ranged: bool
    flee_threshold: float
    dodge_threshold: float
    target: CombatEntity | None


@dataclass(frozen=True)
class _Approach:
    """The cheapest walk to a free cell from which ``target`` is within primary reach."""

    target: CombatEntity
    path: list[Position]  # start inclusive; a single cell means the target is already in reach


class RuleBrain(Brain):
    """Utility-scoring combat AI. Peaceful mode = idle.

    Target selection scores each enemy by distance, wound level, and typed
    relationships. Scared creatures flee earlier.
    """

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        # If all budget resources are exhausted, end the turn.
        budget = awareness.turn_budget
        if budget is not None and budget.turn_over:
            return END_TURN

        if isinstance(awareness, CombatAwareness):
            return self._choose_combat_action(creature, awareness)
        return self._peaceful_action(creature, awareness, events)

    def choose_reaction(
        self,
        creature: Creature,
        trigger: ReactionTrigger,
        options: list[ReactionOption],
    ) -> Action:
        """Deterministic reaction: for LEAVING_REACH, always take OA if available."""
        from dnd_simulator.core.action import SKIP

        if trigger.trigger_type == TriggerType.LEAVING_REACH:
            for opt in options:
                if opt.action_type == ActionType.OPPORTUNITY_ATTACK:
                    return Action(name=opt.action_type, params=dict(opt.params))
        return SKIP

    def _peaceful_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        """Peaceful mode: attack hostile factions on sight, respond to speech.

        Returns end_turn instead of idle — in multi-action loop, idle would
        loop forever (it's free). end_turn signals the turn is done.
        A creature that has left the scene (a flee is a journey) has nothing to do here.
        """
        if not creature.active:
            return END_TURN
        hostile = next((n for n in awareness.nearby if n.is_hostile), None)
        if hostile is not None:
            return Action(name=ActionType.ATTACK, params={"target_id": hostile.id})

        response = creature.get_canned_response(awareness.hour)
        if response is None:
            return END_TURN

        heard_speech = any(e.event_type == EventType.ENTITY_SAY and e.actor_id != creature.id for e in events)
        if not heard_speech:
            return END_TURN

        return Action(name=ActionType.SAY, params={"text": response})

    def _choose_combat_action(self, creature: Creature, awareness: CombatAwareness) -> Action:
        if not awareness.nearby:
            return Action(name=ActionType.IDLE)

        ctx = self._build_context(creature, awareness)

        rules = [
            self._try_equip,
            self._try_potion,
            self._try_retreat,
            self._try_flee,
            self._try_disengage,
            self._try_flee_fallback,
            self._try_attack,
            self._try_advance,
            self._try_dash,
            self._try_dodge,
        ]
        for rule in rules:
            result = rule(ctx)
            if result is not None:
                return result
        return END_TURN

    def _build_context(self, creature: Creature, awareness: CombatAwareness) -> _CombatContext:
        hp = awareness.self_hp
        max_hp = awareness.self_max_hp
        hp_ratio = hp / max_hp if max_hp > 0 else 0.0
        primary_reach = get_weapon_attack(creature).reach
        inner_self = creature.inner_self
        is_scared = inner_self is not None and inner_self.mood is Mood.SCARED
        hated_ids = list(inner_self.relation_targets(RelationshipType.HATES)) if inner_self else []
        feared_ids = list(inner_self.relation_targets(RelationshipType.FEARS)) if inner_self else []
        target = self._pick_target(awareness.nearby, primary_reach, hated_ids, feared_ids)

        return _CombatContext(
            creature=creature,
            awareness=awareness,
            hp_ratio=hp_ratio,
            primary_reach=primary_reach,
            is_ranged=primary_reach > 10,
            flee_threshold=SCARED_FLEE_HP_THRESHOLD if is_scared else FLEE_HP_THRESHOLD,
            dodge_threshold=SCARED_DODGE_HP_THRESHOLD if is_scared else DODGE_HP_THRESHOLD,
            target=target,
        )

    @staticmethod
    def _try_equip(ctx: _CombatContext) -> Action | None:
        awareness = ctx.awareness
        creature = ctx.creature
        if ActionType.EQUIP not in awareness.available_actions or creature.equipped_weapon is not None:
            return None
        from dnd_simulator.core.items import ItemType

        weapon = next((i for i in awareness.available_items if "weapon" in i.description.lower()), None)
        if weapon is None:
            weapon = next(
                (
                    ItemInfo(id=i.id, name=i.name, description=f"weapon: {i.name}", item_type=str(i.item_type))
                    for i in creature.inventory
                    if i.item_type == ItemType.WEAPON
                ),
                None,
            )
        if weapon is None:
            return None
        return Action(name=ActionType.EQUIP, params={"weapon_id": weapon.id})

    @staticmethod
    def _try_potion(ctx: _CombatContext) -> Action | None:
        budget = ctx.awareness.turn_budget
        if (budget.actions if budget else 0) <= 0:
            return None
        awareness = ctx.awareness
        if ctx.hp_ratio >= POTION_HP_THRESHOLD:
            return None
        if ActionType.USE_ITEM not in awareness.available_actions or not awareness.available_items:
            return None
        potion = next((i for i in awareness.available_items if "heal" in i.description.lower()), None)
        if potion is None:
            return None
        return Action(name=ActionType.USE_ITEM, params={"item_id": potion.id})

    def _try_retreat(self, ctx: _CombatContext) -> Action | None:
        creature = ctx.creature
        awareness = ctx.awareness
        budget = awareness.turn_budget
        if not creature.is_disengaging or (budget.movement_remaining if budget else 0) < 5:
            return None
        return self._move_away_from([e for e in awareness.nearby if e.is_hostile], awareness)

    @staticmethod
    def _flee_allowed(awareness: CombatAwareness) -> bool:
        """The shared flee rule (``rules.flee``): never choose a flee the server would reject."""
        if awareness.flee is not None:
            return awareness.flee.allowed
        return not any(e.is_hostile and enemy_blocks_flee(e.distance_ft) for e in awareness.nearby)

    def _try_flee(self, ctx: _CombatContext) -> Action | None:
        budget = ctx.awareness.turn_budget
        if ctx.hp_ratio >= ctx.flee_threshold:
            return None
        if self._flee_allowed(ctx.awareness):
            if (budget.actions if budget else 0) <= 0:
                return None
            return Action(name=ActionType.FLEE)
        # Pinned by enemies within flee range but none in reach: back off first
        # (no opportunity attack), so a later turn can flee.
        hostiles = [e for e in ctx.awareness.nearby if e.is_hostile]
        if not hostiles or (budget.movement_remaining if budget else 0) < 5:
            return None
        nearest = min(hostiles, key=lambda e: e.distance_ft)
        if nearest.distance_ft <= ctx.primary_reach or not enemy_blocks_flee(nearest.distance_ft):
            return None
        return self._move_away_from(hostiles, ctx.awareness)

    @staticmethod
    def _try_disengage(ctx: _CombatContext) -> Action | None:
        budget = ctx.awareness.turn_budget
        has_actions = (budget.actions if budget else 0) > 0
        nearest_dist = min(e.distance_ft for e in ctx.awareness.nearby)
        if ctx.hp_ratio < ctx.dodge_threshold and nearest_dist <= ctx.primary_reach and has_actions:
            return Action(name=ActionType.DISENGAGE)
        return None

    def _try_flee_fallback(self, ctx: _CombatContext) -> Action | None:
        budget = ctx.awareness.turn_budget
        if (budget.actions if budget else 0) <= 0:
            return None
        if ctx.hp_ratio < ctx.flee_threshold and self._flee_allowed(ctx.awareness):
            return Action(name=ActionType.FLEE)
        return None

    def _try_attack(self, ctx: _CombatContext) -> Action | None:
        budget = ctx.awareness.turn_budget
        if (budget.actions if budget else 0) <= 0:
            return None
        if ctx.target is None:
            return None
        if ctx.target.distance_ft <= ctx.primary_reach:
            return self._attack(ctx, ctx.target)
        return None

    def _attack(self, ctx: _CombatContext, target: CombatEntity) -> Action:
        params: dict[str, object] = {"target_id": target.id}
        # Divine Smite: always smite in melee when spell slots available.
        if not ctx.is_ranged:
            smite_level = self._pick_smite_level(ctx.creature)
            if smite_level is not None:
                params["smite_slot_level"] = smite_level
        return Action(name=ActionType.ATTACK, params=params)

    @staticmethod
    def _pick_smite_level(creature: Creature) -> int | None:
        """Return lowest available spell slot level for Divine Smite, or None."""
        from dnd_simulator.core.character import Character, CharClass

        if not isinstance(creature, Character) or creature.char_class != CharClass.PALADIN:
            return None
        slots = get_available_spell_slots(creature)
        if not slots:
            return None
        return min(slots)

    def _try_advance(self, ctx: _CombatContext) -> Action | None:
        """Walk toward a free attack cell along a real path, as far as this turn's movement allows.

        An enemy that is already in reach but is not the chosen target (the target has no path) is attacked.
        """
        if ctx.target is None or ctx.target.distance_ft <= ctx.primary_reach:
            return None
        approach = self._plan_approach(ctx)
        if approach is None:
            return None
        budget = ctx.awareness.turn_budget
        if len(approach.path) == 1:
            if approach.target is not ctx.target and (budget.actions if budget else 0) > 0:
                return self._attack(ctx, approach.target)
            return None
        view = self._map_view(ctx.awareness)
        assert view is not None  # an approach was planned on it
        movement_left = budget.movement_remaining if budget else 0
        affordable = compute_reachable(approach.path[0], movement_left, view, _SELF_ID)
        goal = next((cell for cell in reversed(approach.path[1:]) if cell in affordable), None)
        if goal is None:
            return None
        return Action(name=ActionType.MOVE_TO, params={"x": goal.x, "y": goal.y})

    def _try_dash(self, ctx: _CombatContext) -> Action | None:
        """Dash only when an attack cell has a path but this turn's movement cannot finish it."""
        approach = self._plan_approach(ctx)
        if approach is None or len(approach.path) == 1:
            return None
        budget = ctx.awareness.turn_budget
        dash_params = self._dash_params(ctx.creature)
        if dash_params.get("cost_mode") == "bonus_action":
            has_bonus = (budget.bonus_actions if budget else 0) > 0
            if has_bonus:
                return Action(name=ActionType.DASH, params=dash_params)
        has_actions = (budget.actions if budget else 0) > 0
        if has_actions:
            return Action(name=ActionType.DASH)
        return None

    def _try_dodge(self, ctx: _CombatContext) -> Action | None:
        """No path leads to any enemy's attack cell: defend instead of issuing moves that fail."""
        budget = ctx.awareness.turn_budget
        if ctx.target is None or (budget.actions if budget else 0) <= 0:
            return None
        if self._plan_approach(ctx) is not None:
            return None
        return Action(name=ActionType.DODGE)

    @staticmethod
    def _map_view(awareness: CombatAwareness) -> BattleMap | None:
        """The battle map as the brain knows it: bounds, walls, and every other combatant's cell."""
        from dnd_simulator.core.combat import BattleMap, Position, Wall

        if awareness.battle_map_width <= 0 or awareness.battle_map_height <= 0:
            return None
        positions = {f"occupied_{x}_{y}": Position(x, y) for x, y in awareness.occupied_cells}
        positions[_SELF_ID] = Position(awareness.self_x, awareness.self_y)
        return BattleMap(
            width=awareness.battle_map_width,
            height=awareness.battle_map_height,
            positions=positions,
            walls=[Wall(**wall) for wall in awareness.battle_map_walls],
        )

    def _plan_approach(self, ctx: _CombatContext) -> _Approach | None:
        """Cheapest path to an attack cell of the chosen target, else of the nearest other reachable enemy."""
        from dnd_simulator.core.combat import Position

        view = self._map_view(ctx.awareness)
        if ctx.target is None or view is None:
            return None
        start = Position(ctx.awareness.self_x, ctx.awareness.self_y)
        paths = compute_reachable(start, unbounded_budget(view), view, _SELF_ID)
        others = sorted(
            (e for e in ctx.awareness.nearby if e.is_hostile and e.id != ctx.target.id), key=lambda e: e.distance_ft
        )
        for target in [ctx.target, *others]:
            target_pos = Position(target.x, target.y)
            reach = ctx.primary_reach
            attack_paths = [path for cell, path in paths.items() if grid_distance(cell, target_pos) <= reach]
            if attack_paths:
                # Equal cost: prefer the cell squarest to the target, then a fixed order for determinism.
                best = min(
                    attack_paths,
                    key=lambda path: (
                        path_cost(path),
                        (path[-1].x - target_pos.x) ** 2 + (path[-1].y - target_pos.y) ** 2,
                        path[-1].x,
                        path[-1].y,
                    ),
                )
                return _Approach(target=target, path=best)
        return None

    def _move_away_from(self, threats: list[CombatEntity], awareness: CombatAwareness) -> Action | None:
        """Move to the affordable free cell farthest from the nearest threat; None when no cell gains distance."""
        from dnd_simulator.core.combat import Position

        view = self._map_view(awareness)
        budget = awareness.turn_budget
        if view is None or not threats or budget is None:
            return None
        threat_cells = [Position(t.x, t.y) for t in threats]

        def clearance(cell: Position) -> int:
            return min(grid_distance(cell, threat) for threat in threat_cells)

        start = Position(awareness.self_x, awareness.self_y)
        affordable = compute_reachable(start, budget.movement_remaining, view, _SELF_ID)
        goal = max(affordable, key=lambda cell: (clearance(cell), -path_cost(affordable[cell]), -cell.x, -cell.y))
        if clearance(goal) <= clearance(start):
            return None
        return Action(name=ActionType.MOVE_TO, params={"x": goal.x, "y": goal.y})

    @staticmethod
    def _dash_params(creature: Creature) -> dict[str, object]:
        """Build params for Dash — use bonus_action cost_mode if creature has the override."""
        for ov in collect_cost_overrides(creature):
            if ov.action_type == ActionType.DASH:
                return {"cost_mode": ov.cost_type.value}
        return {}

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

            if score > best_score:
                best_score = score
                best = enemy

        return best if best is not None else hostile_nearby[0]
