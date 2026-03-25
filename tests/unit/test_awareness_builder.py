"""Tests for AwarenessBuilder extracted from EntitiesLayer."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
    Entity,
)
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import Answer, GameDateTime, Query, QueryType
from dnd_simulator.layers.entities.layer import EntitiesLayer

_TIME = GameDateTime(year=1490, month=6, day=15, hour=14)

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


class TestPeacefulAwarenessLocationContext:
    """Peaceful awareness includes location context — region, settlement, weather, time, nearby."""

    def test_awareness_has_region_weather_time_and_nearby(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="village_square",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )
        npc = Character(
            id="n1",
            name="Tanya",
            location_id="village_square",
        )

        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="northern_region")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value={"name": "Northern Region", "terrain": "forest"})
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value={"condition": "rainy", "temperature": 10})
            if target == "settlements" and query.question == QueryType.REGION_SETTLEMENTS:
                return Answer(value=[{"name": "Greendale", "population": 200}])
            if target == "politics" and query.question == QueryType.REGION_OWNER:
                return Answer(value="kingdom_a")
            if target == "politics" and query.question == QueryType.NATION_INFO:
                return Answer(value={"name": "Kingdom A", "government": "monarchy"})
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)

        # It's peaceful (not in combat)
        from dnd_simulator.core.awareness import PeacefulAwareness

        assert isinstance(awareness, PeacefulAwareness)
        assert awareness.hour == 14
        assert awareness.day == 15
        assert awareness.month == 6
        assert awareness.year == 1490
        assert awareness.weather["condition"] == "rainy"
        assert awareness.weather["temperature"] == 10
        assert awareness.region_name == "Northern Region"
        assert awareness.settlements is not None
        assert len(awareness.settlements) == 1
        assert awareness.territory_owner == "kingdom_a"
        assert awareness.nation_info is not None
        assert awareness.nation_info["name"] == "Kingdom A"
        # NPC Tanya should be nearby (same location at hour 14 — innkeeper is at inn)
        assert len(awareness.nearby) >= 1
        nearby_ids = [n.id for n in awareness.nearby]
        assert "n1" in nearby_ids


class TestCombatAwarenessBattleMapState:
    """Combat awareness includes battle map state — HP, AC, weapon, positions, distances."""

    def test_combat_awareness_has_positions_and_distances(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            max_hp=30,
            current_hp=25,
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
            in_combat=True,
        )
        enemy = Character(
            id="e1",
            name="Goblin",
            location_id="arena",
            max_hp=10,
            current_hp=10,
            in_combat=True,
        )

        layer = EntitiesLayer([player, enemy])
        # Set up combat with battle map
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position(player.id, Position(10, 15))
        battle_map.set_position(enemy.id, Position(25, 15))
        combat = CombatState(
            location_id="arena",
            turn_order=[player.id, enemy.id],
            battle_map=battle_map,
        )
        layer._combat._combats["arena"] = combat

        from dnd_simulator.core.awareness import CombatAwareness

        awareness = layer.build_combat_awareness(player)

        assert isinstance(awareness, CombatAwareness)
        assert awareness.self_hp == 25
        assert awareness.self_max_hp == 30
        assert awareness.self_weapon == "longsword"
        assert awareness.self_weapon_damage == "1d8"
        assert awareness.self_x == 10
        assert awareness.self_y == 15
        assert awareness.round_number == 1
        assert awareness.battle_map_ascii != ""
        # Enemy should be nearby with correct distance (15ft apart on x-axis = 3 squares * 5ft)
        assert len(awareness.nearby) == 1
        assert awareness.nearby[0].id == "e1"
        assert awareness.nearby[0].distance_ft == 15


class TestNearbyEntitiesHostility:
    """Nearby entities list respects faction hostility."""

    def test_hostile_factions_marked_hostile(self) -> None:
        creature_a = Character(
            id="a",
            name="Knight",
            location_id="road",
            faction_id="kingdom",
        )
        creature_b = Character(
            id="b",
            name="Orc",
            location_id="road",
            faction_id="horde",
        )

        layer = EntitiesLayer([creature_a, creature_b])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value="hostile")
            return Answer(value=None)

        nearby = layer.build_nearby_entities(creature_a, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].id == "b"
        assert nearby[0].is_hostile is True

    def test_same_faction_not_hostile(self) -> None:
        creature_a = Character(
            id="a",
            name="Knight",
            location_id="road",
            faction_id="kingdom",
        )
        creature_b = Character(
            id="b",
            name="Squire",
            location_id="road",
            faction_id="kingdom",
        )

        layer = EntitiesLayer([creature_a, creature_b])

        def query_fn(target: str, query: Query) -> Answer:
            # Same faction — should never even be queried
            raise AssertionError("Should not query faction relation for same faction")

        nearby = layer.build_nearby_entities(creature_a, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].id == "b"
        assert nearby[0].is_hostile is False


class TestFactionHostilityDelegatesToPoliticsQuery:
    """_check_faction_hostility delegates to politics query_fn."""

    def test_queries_politics_layer(self) -> None:
        observer = Entity(id="o1", name="Obs", location_id="road", faction_id="elves")
        other = Entity(id="o2", name="Other", location_id="road", faction_id="dwarves")

        layer = EntitiesLayer([observer, other])

        calls: list[Query] = []

        def query_fn(target: str, query: Query) -> Answer:
            calls.append(query)
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value="hostile")
            return Answer(value=None)

        result = layer._awareness.check_faction_hostility(observer, other, query_fn)
        assert result is True
        assert len(calls) == 1
        assert calls[0].question == QueryType.FACTION_RELATION
        assert calls[0].params["a"] == "elves"
        assert calls[0].params["b"] == "dwarves"

    def test_neutral_faction_returns_false(self) -> None:
        observer = Entity(id="o1", name="Obs", location_id="road", faction_id="elves")
        other = Entity(id="o2", name="Other", location_id="road", faction_id="humans")

        layer = EntitiesLayer([observer, other])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value="neutral")
            return Answer(value=None)

        result = layer._awareness.check_faction_hostility(observer, other, query_fn)
        assert result is False

    def test_no_faction_returns_false(self) -> None:
        observer = Entity(id="o1", name="Obs", location_id="road")
        other = Entity(id="o2", name="Other", location_id="road")

        layer = EntitiesLayer([observer, other])

        def query_fn(target: str, query: Query) -> Answer:
            raise AssertionError("Should not query for entities without factions")

        result = layer._awareness.check_faction_hostility(observer, other, query_fn)
        assert result is False
