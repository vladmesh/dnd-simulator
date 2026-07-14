"""Tests for auto-hostility: attacking outside combat starts combat with correct sides.

Sprint 014, Phase 3, Task 2.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.events import AttackRequestedPayload
from dnd_simulator.core.models import Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.rules.combat_sides import are_allies, build_combat_sides
from dnd_simulator.rules.reputation import effective_relation

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
    reputation: dict[str, int] | None = None,
) -> Creature:
    c = Creature(
        id=id,
        name=id.capitalize(),
        location_id=location_id,
        faction_id=faction_id,
        max_hp=hp,
        current_hp=hp,
        attacks=_MELEE_ATTACK,
        reputation=reputation or {},
    )
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=1)
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


def _attack_event(attacker_id: str, target_id: str) -> Event:

    return Event(
        event_type=EventType.ENTITY_ATTACK_REQUESTED,
        source_layer="entities",
        data=AttackRequestedPayload(attacker_id, target_id),
    )


def _creature_relation_fn(*pairs: tuple[str, str, FactionRelation]):
    """Build creature-level relation fn from faction pairs via effective_relation."""
    faction_lookup: dict[tuple[str, str], FactionRelation] = {}
    for a, b, rel in pairs:
        faction_lookup[(a, b)] = rel
        faction_lookup[(b, a)] = rel

    def get_faction_relation(a: str, b: str) -> FactionRelation:
        return faction_lookup.get((a, b), FactionRelation.NEUTRAL)

    def get_relation(a: Creature, b: Creature) -> FactionRelation:
        return effective_relation(a, b, get_faction_relation)

    return get_relation


# ---------------------------------------------------------------------------
# 1. build_combat_sides with forced_opponents (pure function tests)
# ---------------------------------------------------------------------------


class TestBuildCombatSidesForcedOpponents:
    def test_forced_opponents_same_faction_split(self) -> None:
        """Two goblins forced apart — end up on different sides despite same faction."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        get_rel = _creature_relation_fn()

        _sides, ets = build_combat_sides([g1, g2], get_rel, forced_opponents={("g1", "g2")})
        assert ets["g1"] != ets["g2"]

    def test_forced_opponents_allies_join_correct_sides(self) -> None:
        """Forced opponents split; their allies cluster around them."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        g3 = _creature("g3", "goblins")
        get_rel = _creature_relation_fn()

        _sides, ets = build_combat_sides([g1, g2, g3], get_rel, forced_opponents={("g1", "g2")})
        assert ets["g1"] != ets["g2"]
        # g3 joins one of the two sides (whichever is first — g1's side)
        assert ets["g3"] == ets["g1"]

    def test_forced_opponents_with_factionless(self) -> None:
        """Factionless attacker vs factionless target — forced onto different sides."""
        a = _creature("attacker", "")
        b = _creature("target", "")
        get_rel = _creature_relation_fn()

        # Without forced_opponents, factionless creatures already get own sides,
        # but let's verify forced_opponents doesn't break anything
        _sides, ets = build_combat_sides([a, b], get_rel, forced_opponents={("attacker", "target")})
        assert ets["attacker"] != ets["target"]

    def test_no_forced_opponents_preserves_behavior(self) -> None:
        """Without forced_opponents, same-faction creatures still merge."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        get_rel = _creature_relation_fn()

        _sides, ets = build_combat_sides([g1, g2], get_rel)
        assert ets["g1"] == ets["g2"]

    def test_bystander_same_faction_as_target_joins_target(self) -> None:
        """Bodyguard same faction as target, NEUTRAL to attacker → joins target's side."""
        attacker = _creature("attacker", "kingdom")
        target = _creature("target", "guild")
        bodyguard = _creature("bodyguard", "guild")

        get_rel = _creature_relation_fn()  # all NEUTRAL
        _sides, ets = build_combat_sides(
            [attacker, target, bodyguard],
            get_rel,
            forced_opponents={("attacker", "target")},
        )
        # Attacker forced apart from target
        assert ets["attacker"] != ets["target"]
        # Bodyguard same faction as target → joins target
        assert ets["bodyguard"] == ets["target"]

    def test_bystander_neutral_to_both_gets_own_side(self) -> None:
        """Third-faction creature NEUTRAL to both sides → own side."""
        attacker = _creature("attacker", "kingdom")
        target = _creature("target", "guild")
        bystander = _creature("bystander", "monks")

        get_rel = _creature_relation_fn()
        _sides, ets = build_combat_sides(
            [attacker, target, bystander],
            get_rel,
            forced_opponents={("attacker", "target")},
        )
        assert ets["attacker"] != ets["target"]
        assert ets["bystander"] != ets["attacker"]
        assert ets["bystander"] != ets["target"]

    def test_bystander_friendly_to_target_hostile_to_attacker(self) -> None:
        """Bystander hostile to attacker faction, friendly to target → joins target side."""
        attacker = _creature("attacker", "kingdom")
        target = _creature("target", "guild")
        bystander = _creature("bystander", "guild_allies")

        get_rel = _creature_relation_fn(
            ("guild_allies", "guild", FactionRelation.FRIENDLY),
            ("guild_allies", "kingdom", FactionRelation.HOSTILE),
        )
        _sides, ets = build_combat_sides(
            [attacker, target, bystander],
            get_rel,
            forced_opponents={("attacker", "target")},
        )
        assert ets["bystander"] == ets["target"]
        assert ets["bystander"] != ets["attacker"]


# ---------------------------------------------------------------------------
# 2. CombatManager integration: resolve_attack triggers combat
# ---------------------------------------------------------------------------


class TestAutoHostilityCombatManager:
    def test_attack_neutral_npc_starts_combat_opposing_sides(self) -> None:
        """Player (kingdom) attacks neutral merchant (guild) → combat starts, opposing sides."""
        player = _creature("player", "kingdom")
        merchant = _creature("merchant", "guild")

        query_fn = _make_query_fn()  # all NEUTRAL
        cm = _make_combat_manager(player, merchant)
        cm.resolve_attack(_attack_event("player", "merchant"), query_fn)

        combat = cm.get_combat("arena")
        assert combat is not None
        assert combat.entity_to_side["player"] != combat.entity_to_side["merchant"]

    def test_attack_same_faction_starts_combat_opposing_sides(self) -> None:
        """Player attacks own faction member → forced onto opposing sides."""
        player = _creature("player", "kingdom")
        ally = _creature("ally", "kingdom")

        query_fn = _make_query_fn()
        cm = _make_combat_manager(player, ally)
        cm.resolve_attack(_attack_event("player", "ally"), query_fn)

        combat = cm.get_combat("arena")
        assert combat is not None
        assert combat.entity_to_side["player"] != combat.entity_to_side["ally"]

    def test_allies_join_correct_sides_on_auto_hostility(self) -> None:
        """Player + 2 guards (kingdom) attack merchant + bodyguard (guild).
        Guards join player, bodyguard joins merchant."""
        player = _creature("player", "kingdom")
        guard1 = _creature("guard1", "kingdom")
        guard2 = _creature("guard2", "kingdom")
        merchant = _creature("merchant", "guild")
        bodyguard = _creature("bodyguard", "guild")

        query_fn = _make_query_fn()  # all NEUTRAL — sides determined by forced + same-faction
        cm = _make_combat_manager(player, guard1, guard2, merchant, bodyguard)
        cm.resolve_attack(_attack_event("player", "merchant"), query_fn)

        combat = cm.get_combat("arena")
        assert combat is not None
        # Player side
        assert are_allies(combat, "player", "guard1")
        assert are_allies(combat, "player", "guard2")
        # Merchant side
        assert are_allies(combat, "merchant", "bodyguard")
        # Opposing
        assert not are_allies(combat, "player", "merchant")
        assert not are_allies(combat, "guard1", "bodyguard")

    def test_already_in_combat_no_side_rebuild(self) -> None:
        """If combat already exists, resolve_attack does not re-trigger start_combat."""
        g1 = _creature("g1", "goblins")
        g2 = _creature("g2", "goblins")
        guard = _creature("guard", "guards")

        query_fn = _make_query_fn(("goblins", "guards", FactionRelation.HOSTILE))
        cm = _make_combat_manager(g1, g2, guard)

        # Start combat normally — g1 and g2 on same side
        combat = cm.start_combat("arena", query_fn)
        assert combat is not None
        assert are_allies(combat, "g1", "g2")
        original_sides = dict(combat.entity_to_side)

        # g1 attacks g2 — combat already exists, no rebuild
        cm.resolve_attack(_attack_event("g1", "g2"), query_fn)
        assert combat.entity_to_side == original_sides

    def test_factionless_attacker_vs_factionless_target(self) -> None:
        """Both factionless → each on their own side."""
        attacker = _creature("attacker", "")
        target = _creature("target", "")

        query_fn = _make_query_fn()
        cm = _make_combat_manager(attacker, target)
        cm.resolve_attack(_attack_event("attacker", "target"), query_fn)

        combat = cm.get_combat("arena")
        assert combat is not None
        assert combat.entity_to_side["attacker"] != combat.entity_to_side["target"]
