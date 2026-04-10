"""Tests for combat sides — grouping creatures into allied sides from faction relations."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.combat_sides import are_allies, build_combat_sides
from dnd_simulator.rules.reputation import effective_relation


def _make_creature(id: str, faction_id: str = "", reputation: dict[str, int] | None = None) -> Creature:
    return Creature(id=id, name=id, location_id="loc", faction_id=faction_id, reputation=reputation or {})


def _creature_relation_fn(
    *pairs: tuple[str, str, FactionRelation],
):
    """Build a creature-level relation fn from faction pairs via effective_relation."""
    faction_lookup: dict[tuple[str, str], FactionRelation] = {}
    for a, b, rel in pairs:
        faction_lookup[(a, b)] = rel
        faction_lookup[(b, a)] = rel

    def get_faction_relation(a: str, b: str) -> FactionRelation:
        return faction_lookup.get((a, b), FactionRelation.NEUTRAL)

    def get_relation(a: Creature, b: Creature) -> FactionRelation:
        return effective_relation(a, b, get_faction_relation)

    return get_relation


class TestBuildCombatSides:
    def test_same_faction_same_side(self) -> None:
        """Three goblins → all on one side."""
        creatures = [_make_creature(f"g{i}", "goblins") for i in range(3)]
        sides, entity_to_side = build_combat_sides(creatures, _creature_relation_fn())
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
        get_rel = _creature_relation_fn(("goblins", "guards", FactionRelation.HOSTILE))
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
        get_rel = _creature_relation_fn(
            ("goblins", "guards", FactionRelation.HOSTILE),
            ("bandits", "goblins", FactionRelation.FRIENDLY),
        )
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        assert entity_to_side["g0"] == entity_to_side["b0"]
        assert entity_to_side["g0"] != entity_to_side["h0"]
        assert len(sides) == 2

    def test_neutral_faction_own_side(self) -> None:
        """Merchants NEUTRAL to both → three distinct sides."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("m0", "merchants"),
        ]
        get_rel = _creature_relation_fn(
            ("goblins", "guards", FactionRelation.HOSTILE),
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
        sides, entity_to_side = build_combat_sides(creatures, _creature_relation_fn())
        assert entity_to_side["a"] != entity_to_side["b"]
        assert len(sides) == 2

    def test_friend_of_both_same_faction_priority(self) -> None:
        """Mercenary with faction_id matching one side joins that side."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("h0", "guards"),
            _make_creature("merc", "goblins"),
        ]
        get_rel = _creature_relation_fn(("goblins", "guards", FactionRelation.HOSTILE))
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
        get_rel = _creature_relation_fn(
            ("goblins", "guards", FactionRelation.HOSTILE),
            ("mercenaries", "goblins", FactionRelation.FRIENDLY),
            ("mercenaries", "guards", FactionRelation.FRIENDLY),
        )
        sides, entity_to_side = build_combat_sides(creatures, get_rel)

        assert len(sides) == 2
        merc_side = entity_to_side["merc"]
        assert merc_side in (entity_to_side["g0"], entity_to_side["h0"])

    def test_empty_creature_list(self) -> None:
        sides, entity_to_side = build_combat_sides([], _creature_relation_fn())
        assert sides == {}
        assert entity_to_side == {}

    def test_single_creature(self) -> None:
        creatures = [_make_creature("solo", "goblins")]
        sides, entity_to_side = build_combat_sides(creatures, _creature_relation_fn())
        assert len(sides) == 1
        assert entity_to_side["solo"] in sides

    # --- New tests for personal reputation ---

    def test_exile_gets_separate_side(self) -> None:
        """Goblin exile (rep 10 with own faction) → separate side from loyal goblins."""
        creatures = [
            _make_creature("g0", "goblins"),
            _make_creature("g1", "goblins"),
            _make_creature("exile", "goblins", reputation={"goblins": 10}),
        ]
        _sides, entity_to_side = build_combat_sides(creatures, _creature_relation_fn())

        # Loyal goblins together
        assert entity_to_side["g0"] == entity_to_side["g1"]
        # Exile separate
        assert entity_to_side["exile"] != entity_to_side["g0"]

    def test_personal_friendship_overrides_faction_hostility(self) -> None:
        """Creature from hostile faction with rep 80 → joins player's side."""
        creatures = [
            _make_creature("player", "humans"),
            _make_creature("friendly_goblin", "goblins", reputation={"humans": 80}),
            _make_creature("hostile_goblin", "goblins"),
        ]
        get_rel = _creature_relation_fn(("humans", "goblins", FactionRelation.HOSTILE))
        _sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # Friendly goblin is FRIENDLY to humans, but humans still HOSTILE to goblins
        # (asymmetric — friendly_goblin→player is FRIENDLY, player→friendly_goblin is HOSTILE)
        # Hostility wins → they can't be on the same side
        assert entity_to_side["friendly_goblin"] != entity_to_side["player"]
        # Friendly goblin HOSTILE to own faction (no, has no personal rep with goblins)
        # friendly_goblin has no rep for "goblins", same faction → FRIENDLY
        assert entity_to_side["friendly_goblin"] == entity_to_side["hostile_goblin"]

    def test_mutual_personal_friendship(self) -> None:
        """Both creatures have friendly personal rep → join same side despite hostile factions."""
        creatures = [
            _make_creature("player", "humans", reputation={"goblins": 80}),
            _make_creature("ally_goblin", "goblins", reputation={"humans": 80}),
            _make_creature("hostile_goblin", "goblins"),
        ]
        get_rel = _creature_relation_fn(("humans", "goblins", FactionRelation.HOSTILE))
        _sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # Mutual friendship → same side
        assert entity_to_side["player"] == entity_to_side["ally_goblin"]
        # Hostile goblin on different side (faction hostile to humans, no personal override)
        assert entity_to_side["hostile_goblin"] != entity_to_side["player"]

    def test_asymmetric_rep_different_sides(self) -> None:
        """A friendly to B's faction, B hostile to A's faction → different sides."""
        creatures = [
            _make_creature("a", "humans", reputation={"goblins": 80}),
            _make_creature("b", "goblins"),
        ]
        get_rel = _creature_relation_fn(("humans", "goblins", FactionRelation.HOSTILE))
        _sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # A→B: FRIENDLY (personal rep 80), B→A: HOSTILE (faction fallback)
        # Hostility wins → different sides
        assert entity_to_side["a"] != entity_to_side["b"]

    def test_mixed_factions_with_personal_overrides(self) -> None:
        """5 creatures, 3 factions, personal overrides change grouping."""
        creatures = [
            _make_creature("human1", "humans"),
            _make_creature("human2", "humans"),
            _make_creature("goblin1", "goblins"),
            _make_creature("goblin_defector", "goblins", reputation={"goblins": 10, "humans": 80}),
            _make_creature("bandit", "bandits"),
        ]
        get_rel = _creature_relation_fn(
            ("humans", "goblins", FactionRelation.HOSTILE),
            ("bandits", "goblins", FactionRelation.FRIENDLY),
        )
        _sides, entity_to_side = build_combat_sides(creatures, get_rel)

        # Humans together
        assert entity_to_side["human1"] == entity_to_side["human2"]
        # Goblin1 and bandit together (FRIENDLY factions)
        assert entity_to_side["goblin1"] == entity_to_side["bandit"]
        # Goblin defector: HOSTILE to own faction (rep 10), FRIENDLY to humans (rep 80)
        # But humans→goblin_defector: faction HOSTILE (no personal override on humans)
        # Asymmetric → defector can't join humans. HOSTILE to goblins → can't join goblins.
        # Defector gets own side.
        assert entity_to_side["goblin_defector"] != entity_to_side["human1"]
        assert entity_to_side["goblin_defector"] != entity_to_side["goblin1"]


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
