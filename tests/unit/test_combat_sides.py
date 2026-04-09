"""Tests for combat sides — grouping creatures into allied sides from faction relations."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.combat_sides import are_allies, build_combat_sides


def _make_creature(id: str, faction_id: str = "") -> Creature:
    return Creature(id=id, name=id, location_id="loc", faction_id=faction_id)


def _relation_map(*pairs: tuple[str, str, FactionRelation]):
    """Build a relation lookup from explicit pairs. Unspecified = NEUTRAL."""
    lookup: dict[tuple[str, str], FactionRelation] = {}
    for a, b, rel in pairs:
        lookup[(a, b)] = rel
        lookup[(b, a)] = rel
    return lambda a, b: lookup.get((a, b), FactionRelation.NEUTRAL)


class TestBuildCombatSides:
    def test_same_faction_same_side(self) -> None:
        """Three goblins → all on one side."""
        creatures = [_make_creature(f"g{i}", "goblins") for i in range(3)]
        sides, entity_to_side = build_combat_sides(creatures, _relation_map())
        # All on the same side
        assert entity_to_side["g0"] == entity_to_side["g1"] == entity_to_side["g2"]
        side_id = entity_to_side["g0"]
        assert sides[side_id] == {"g0", "g1", "g2"}

    def test_hostile_factions_different_sides(self) -> None:
        """Two goblins + two guards (HOSTILE) → two distinct sides."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("g1", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("h1", "guards"),
        ]
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        assert entity_to_side["g0"] == entity_to_side["g1"]
        assert entity_to_side["h0"] == entity_to_side["h1"]
        assert entity_to_side["g0"] != entity_to_side["h0"]
        assert len(sides) == 2

    def test_three_factions_friendly_merge(self) -> None:
        """Goblins HOSTILE to guards, bandits FRIENDLY to goblins → goblins+bandits vs guards."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("b0", "bandits"),
            _make_creature("h0", "guards"),
        ]
        get_rel = _relation_map(
            ("goblins", "guards", FactionRelation.HOSTILE),
            ("bandits", "goblins", FactionRelation.FRIENDLY),
        )
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # Goblins and bandits merged
        assert entity_to_side["g0"] == entity_to_side["b0"]
        # Guards separate
        assert entity_to_side["g0"] != entity_to_side["h0"]
        assert len(sides) == 2

    def test_neutral_faction_own_side(self) -> None:
        """Merchants NEUTRAL to both → three distinct sides."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("m0", "merchants"),
        ]
        get_rel = _relation_map(
            ("goblins", "guards", FactionRelation.HOSTILE),
            # merchants NEUTRAL to both (default)
        )
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        assert entity_to_side["g0"] != entity_to_side["h0"]
        assert entity_to_side["m0"] != entity_to_side["g0"]
        assert entity_to_side["m0"] != entity_to_side["h0"]
        assert len(sides) == 3

    def test_no_faction_each_own_side(self) -> None:
        """Two creatures without faction_id → each on its own side."""
        creatures = [
            _make_creature("a", ""),
            _make_creature("b", ""),
        ]
        sides, entity_to_side = build_combat_sides(creatures, _relation_map())
        assert entity_to_side["a"] != entity_to_side["b"]
        assert len(sides) == 2

    def test_friend_of_both_same_faction_priority(self) -> None:
        """Mercenary with faction_id matching one side joins that side."""
        # Goblin merc has faction_id "goblins" and is in mercenary-like role
        # but faction_id == "goblins" means same faction → same side as goblins
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("merc", "goblins"),  # same faction_id as goblins
        ]
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        _sides, entity_to_side = build_combat_sides(creatures, get_rel)

        assert entity_to_side["merc"] == entity_to_side["g0"]
        assert entity_to_side["merc"] != entity_to_side["h0"]

    def test_friend_of_both_different_faction_joins_first(self) -> None:
        """Mercenary faction FRIENDLY to both warring sides → joins first-encountered FRIENDLY side."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("merc", "mercenaries"),
        ]
        get_rel = _relation_map(
            ("goblins", "guards", FactionRelation.HOSTILE),
            ("mercenaries", "goblins", FactionRelation.FRIENDLY),
            ("mercenaries", "guards", FactionRelation.FRIENDLY),
        )
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # Merc should join one of the existing sides (not create a third)
        assert len(sides) == 2
        merc_side = entity_to_side["merc"]
        assert merc_side in (entity_to_side["g0"], entity_to_side["h0"])

    def test_empty_creature_list(self) -> None:
        sides, entity_to_side = build_combat_sides([], _relation_map())
        assert sides == {}
        assert entity_to_side == {}

    def test_single_creature(self) -> None:
        creatures = [_make_creature("solo", "goblins")]
        sides, entity_to_side = build_combat_sides(creatures, _relation_map())
        assert len(sides) == 1
        assert entity_to_side["solo"] in sides


class TestAreAllies:
    def test_same_side_are_allies(self) -> None:
        combat = CombatState(
            location_id="loc",
            sides={0: {"a", "b"}, 1: {"c"}},
            entity_to_side={"a": 0, "b": 0, "c": 1},
        )
        assert are_allies(combat, "a", "b") is True

    def test_different_sides_not_allies(self) -> None:
        combat = CombatState(
            location_id="loc",
            sides={0: {"a"}, 1: {"b"}},
            entity_to_side={"a": 0, "b": 1},
        )
        assert are_allies(combat, "a", "b") is False

    def test_same_entity_is_ally_of_self(self) -> None:
        combat = CombatState(
            location_id="loc",
            sides={0: {"a"}},
            entity_to_side={"a": 0},
        )
        assert are_allies(combat, "a", "a") is True
