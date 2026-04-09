"""Tests for wiring combat sides into combat lifecycle — OA fix + combat end.

Sprint 014, Phase 1, Task 2.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import CombatState, Position
from dnd_simulator.core.models import Event, FactionRelation, Query, QueryType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.rules.combat_sides import are_allies
from dnd_simulator.rules.reactions import find_oa_triggers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MELEE_ATTACK = (
    Attack(
        name="melee",
        ability=Ability.STR,
        damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
        reach=5,
    ),
)


def _creature(
    id: str,
    faction_id: str = "",
    *,
    hp: int = 20,
    location_id: str = "arena",
    reaction: int = 1,
) -> Creature:
    c = Creature(
        id=id,
        name=id.capitalize(),
        location_id=location_id,
        faction_id=faction_id,
        max_hp=hp,
        current_hp=hp,
        attacks=_MELEE_ATTACK,
    )
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=reaction)
    return c


def _make_query_fn(*relations: tuple[str, str, FactionRelation]):
    """Build a query_fn that answers FACTION_RELATION queries."""
    lookup: dict[tuple[str, str], FactionRelation] = {}
    for a, b, rel in relations:
        lookup[(a, b)] = rel
        lookup[(b, a)] = rel

    def query_fn(layer: str, query: Query):
        if query.question == QueryType.FACTION_RELATION:
            a = query.params["a"]
            b = query.params["b"]
            result = MagicMock()
            result.value = lookup.get((a, b), FactionRelation.NEUTRAL)
            return result
        raise ValueError(f"Unexpected query: {query}")

    return query_fn


def _make_combat_manager(*creatures: Creature) -> CombatManager:
    entities: dict[str, Creature] = {c.id: c for c in creatures}
    location_log: dict[str, list[Event]] = {}
    for c in creatures:
        location_log.setdefault(c.location_id, [])
    return CombatManager(entities, location_log)


# ---------------------------------------------------------------------------
# 1. OA bug fix — goblins don't OA each other
# ---------------------------------------------------------------------------


class TestOaBugFix:
    """Three goblins in combat with a guard. Goblin-to-goblin movement = no OA.
    Goblin leaving guard reach = OA triggered."""

    def test_goblin_moving_away_from_goblin_no_oa(self) -> None:
        """Goblin moves away from another goblin → no OA triggered (same side)."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        guard = _creature("guard", "guards")

        combat = CombatState(
            location_id="arena",
            turn_order=["g1", "g2", "guard"],
            sides={0: {"g1", "g2"}, 1: {"guard"}},
            entity_to_side={"g1": 0, "g2": 0, "guard": 1},
        )
        bm = combat.battle_map
        bm.set_position("g1", Position(10, 10))
        bm.set_position("g2", Position(10, 15))  # adjacent to g1
        bm.set_position("guard", Position(30, 30))  # far away

        # g1 moves away from g2 — should NOT trigger OA
        path = [Position(10, 10), Position(10, 5)]
        triggers = find_oa_triggers(path, g1, [g1, g2, guard], bm, combat)
        assert triggers == []

    def test_goblin_moving_away_from_guard_triggers_oa(self) -> None:
        """Goblin moves away from guard → OA triggered (different side)."""
        g1 = _creature("g1", "goblins")
        guard = _creature("guard", "guards")

        combat = CombatState(
            location_id="arena",
            turn_order=["g1", "guard"],
            sides={0: {"g1"}, 1: {"guard"}},
            entity_to_side={"g1": 0, "guard": 1},
        )
        bm = combat.battle_map
        bm.set_position("g1", Position(10, 10))
        bm.set_position("guard", Position(10, 15))  # adjacent

        path = [Position(10, 10), Position(10, 5)]
        triggers = find_oa_triggers(path, g1, [g1, guard], bm, combat)
        assert len(triggers) == 1
        _, reactors = triggers[0]
        assert guard in reactors


# ---------------------------------------------------------------------------
# 2. Mixed factions OA
# ---------------------------------------------------------------------------


class TestMixedFactionsOa:
    """Goblins + bandits (FRIENDLY) vs guards. Allied movement = no OA."""

    def test_bandit_moving_away_from_goblin_no_oa(self) -> None:
        """Bandit moves away from goblin (same side, FRIENDLY factions) → no OA."""
        bandit = _creature("bandit", "bandits")
        goblin = _creature("goblin", "goblins")
        guard = _creature("guard", "guards")

        combat = CombatState(
            location_id="arena",
            turn_order=["bandit", "goblin", "guard"],
            sides={0: {"bandit", "goblin"}, 1: {"guard"}},
            entity_to_side={"bandit": 0, "goblin": 0, "guard": 1},
        )
        bm = combat.battle_map
        bm.set_position("bandit", Position(10, 10))
        bm.set_position("goblin", Position(10, 15))
        bm.set_position("guard", Position(30, 30))

        path = [Position(10, 10), Position(10, 5)]
        triggers = find_oa_triggers(path, bandit, [bandit, goblin, guard], bm, combat)
        assert triggers == []

    def test_bandit_moving_away_from_guard_triggers_oa(self) -> None:
        """Bandit moves away from guard (different side) → OA triggered."""
        bandit = _creature("bandit", "bandits")
        guard = _creature("guard", "guards")

        combat = CombatState(
            location_id="arena",
            turn_order=["bandit", "guard"],
            sides={0: {"bandit"}, 1: {"guard"}},
            entity_to_side={"bandit": 0, "guard": 1},
        )
        bm = combat.battle_map
        bm.set_position("bandit", Position(10, 10))
        bm.set_position("guard", Position(10, 15))

        path = [Position(10, 10), Position(10, 5)]
        triggers = find_oa_triggers(path, bandit, [bandit, guard], bm, combat)
        assert len(triggers) == 1
        _, reactors = triggers[0]
        assert guard in reactors


# ---------------------------------------------------------------------------
# 3. Combat ends when one side eliminated
# ---------------------------------------------------------------------------


class TestCombatEndsSidesEliminated:
    """Combat ends when only one side has alive members."""

    def test_combat_ends_same_faction_survivors(self) -> None:
        """Two goblins vs two guards. Both guards die → combat ends."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        h1 = _creature("h1", "guards", hp=1)
        h2 = _creature("h2", "guards", hp=1)

        query_fn = _make_query_fn(("goblins", "guards", FactionRelation.HOSTILE))
        cm = _make_combat_manager(g1, g2, h1, h2)
        combat = cm.start_combat("arena", query_fn)
        assert combat is not None

        # Verify sides were built
        assert are_allies(combat, "g1", "g2")
        assert not are_allies(combat, "g1", "h1")

        # Kill both guards
        h1.current_hp = 0
        h2.current_hp = 0
        cm._remove_from_combat("arena", "h1")
        # After removing h1, h2 is still alive... wait, we set hp=0.
        # _has_opposing_factions checks is_alive, which checks current_hp > 0.
        # After removing h1, g1+g2 on side 0, h2 on side 1 but h2 is dead.
        cm._remove_from_combat("arena", "h2")

        # Combat should have ended
        assert cm.get_combat("arena") is None

    def test_combat_continues_multiple_sides_alive(self) -> None:
        """Three-way fight. Kill one side → combat continues with remaining 2 sides."""
        g = _creature("g", "goblins")
        h = _creature("h", "guards")
        m = _creature("m", "merchants")

        query_fn = _make_query_fn(
            ("goblins", "guards", FactionRelation.HOSTILE),
            ("goblins", "merchants", FactionRelation.HOSTILE),
            ("guards", "merchants", FactionRelation.HOSTILE),
        )
        cm = _make_combat_manager(g, h, m)
        combat = cm.start_combat("arena", query_fn)
        assert combat is not None
        assert len(combat.sides) == 3

        # Kill merchant
        m.current_hp = 0
        cm._remove_from_combat("arena", "m")

        # Combat continues — goblins vs guards still alive
        assert cm.get_combat("arena") is not None

        # Kill guard
        h.current_hp = 0
        cm._remove_from_combat("arena", "h")

        # Now combat ends — only goblins remain
        assert cm.get_combat("arena") is None


# ---------------------------------------------------------------------------
# 4. Creature removal updates sides
# ---------------------------------------------------------------------------


class TestCreatureRemovalUpdatesSides:
    """Remove a creature from combat → sides and entity_to_side updated."""

    def test_removal_cleans_sides(self) -> None:
        g = _creature("g", "goblins")
        h = _creature("h", "guards")
        h2 = _creature("h2", "guards")

        query_fn = _make_query_fn(("goblins", "guards", FactionRelation.HOSTILE))
        cm = _make_combat_manager(g, h, h2)
        combat = cm.start_combat("arena", query_fn)
        assert combat is not None
        assert "h" in combat.entity_to_side

        # Remove h from combat (fled, etc.)
        cm._remove_from_combat("arena", "h")

        # h should be gone from entity_to_side
        assert "h" not in combat.entity_to_side
        # h should be gone from its side's set
        guard_side = combat.entity_to_side["h2"]
        assert "h" not in combat.sides[guard_side]


# ---------------------------------------------------------------------------
# 5. start_combat builds sides
# ---------------------------------------------------------------------------


class TestStartCombatBuildsSides:
    """start_combat() calls build_combat_sides() and stores result on CombatState."""

    def test_sides_populated_on_start(self) -> None:
        g = _creature("g", "goblins")
        h = _creature("h", "guards")

        query_fn = _make_query_fn(("goblins", "guards", FactionRelation.HOSTILE))
        cm = _make_combat_manager(g, h)
        combat = cm.start_combat("arena", query_fn)
        assert combat is not None

        # sides should be populated
        assert len(combat.sides) == 2
        assert combat.entity_to_side["g"] != combat.entity_to_side["h"]
