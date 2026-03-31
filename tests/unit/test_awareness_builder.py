"""Tests for AwarenessBuilder extracted from EntitiesLayer."""

from __future__ import annotations

from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
    Entity,
)
from dnd_simulator.core.combat import BattleMap, CombatState, Position, Wall
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import Answer, FactionRelation, GameDateTime, Query, QueryType
from dnd_simulator.core.world import LayerError
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc, NpcActivity, ScheduleEntry

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
                return Answer(value=FactionRelation.HOSTILE)
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
            if query.question == QueryType.FACTION_NAME:
                return Answer(value="Kingdom Forces")
            # Same faction — hostility should never be queried
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
                return Answer(value=FactionRelation.HOSTILE)
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
                return Answer(value=FactionRelation.NEUTRAL)
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


class TestPeacefulAwarenessQueryResilience:
    """Peaceful awareness degrades gracefully when layer queries fail."""

    def test_geography_region_query_raises_uses_fallback_defaults(self) -> None:
        player = Character(id="p1", name="Hero", location_id="dark_cave")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                raise LayerError("geography layer not found")
            raise AssertionError(f"Unexpected query: {target} {query.question}")

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert isinstance(awareness, PeacefulAwareness)
        # Falls back to location_id as region_name
        assert awareness.region_name == "dark_cave"
        # Falls back to default weather
        assert awareness.weather["condition"] == "clear"
        assert awareness.weather["temperature"] == 15

    def test_weather_query_fails_region_name_still_resolved(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="northern_region")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value={"name": "Northern Region", "terrain": "forest"})
            if target == "geography" and query.question == QueryType.WEATHER:
                raise KeyError("region_id")
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert isinstance(awareness, PeacefulAwareness)
        assert awareness.region_name == "Northern Region"
        assert awareness.weather["condition"] == "clear"
        assert awareness.weather["temperature"] == 15

    def test_settlements_query_returns_empty_list_not_none(self) -> None:
        player = Character(id="p1", name="Hero", location_id="wilderness")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="empty_region")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value={"name": "Empty Region"})
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value={"condition": "sunny", "temperature": 25})
            if target == "settlements" and query.question == QueryType.REGION_SETTLEMENTS:
                return Answer(value=[])
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert isinstance(awareness, PeacefulAwareness)
        assert awareness.settlements == []

    def test_politics_query_fails_territory_owner_is_none(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="contested_region")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value={"name": "Contested Region"})
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value={"condition": "stormy", "temperature": 5})
            if target == "settlements":
                return Answer(value=[])
            if target == "politics":
                raise LayerError("politics layer not found")
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert isinstance(awareness, PeacefulAwareness)
        assert awareness.territory_owner is None
        assert awareness.nation_info is None


class TestNpcScheduleLocation:
    """NPC schedule determines where they appear as nearby."""

    def test_npcs_at_different_schedule_locations_see_only_colocated(self) -> None:
        npc_tavern = Npc(
            id="bartender",
            name="Bartender",
            location_id="town_center",
            schedule=[
                ScheduleEntry(start_hour=8, end_hour=22, activity=NpcActivity.WORKING, location_id="tavern"),
            ],
        )
        npc_smithy = Npc(
            id="smith",
            name="Smith",
            location_id="town_center",
            schedule=[
                ScheduleEntry(start_hour=6, end_hour=18, activity=NpcActivity.WORKING, location_id="smithy"),
            ],
        )
        player = Character(id="p1", name="Hero", location_id="tavern")

        layer = EntitiesLayer([npc_tavern, npc_smithy, player])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        # At hour 12: bartender at tavern, smith at smithy, player at tavern
        nearby_player = layer.build_nearby_entities(player, hour=12, query_fn=query_fn)
        nearby_ids = [n.id for n in nearby_player]
        assert "bartender" in nearby_ids
        assert "smith" not in nearby_ids

        nearby_bartender = layer.build_nearby_entities(npc_tavern, hour=12, query_fn=query_fn)
        nearby_bartender_ids = [n.id for n in nearby_bartender]
        assert "p1" in nearby_bartender_ids
        assert "smith" not in nearby_bartender_ids

        nearby_smith = layer.build_nearby_entities(npc_smithy, hour=12, query_fn=query_fn)
        assert len(nearby_smith) == 0


class TestCombatAwarenessEntityFiltering:
    """Combat awareness filters dead, inactive, and off-location creatures."""

    def test_dead_creature_excluded_from_nearby(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=25,
            attacks=(_SWORD,),
        )
        dead_goblin = Character(
            id="dead1",
            name="Dead Goblin",
            location_id="arena",
            max_hp=10,
            current_hp=0,
            in_combat=True,
            active=True,
        )

        layer = EntitiesLayer([player, dead_goblin])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        battle_map.set_position("dead1", Position(15, 10))
        combat = CombatState(location_id="arena", turn_order=["p1", "dead1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.nearby) == 0

    def test_inactive_creature_excluded_from_nearby(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=25,
            attacks=(_SWORD,),
        )
        dormant = Character(
            id="dormant1",
            name="Sleeping Guard",
            location_id="arena",
            active=False,
        )

        layer = EntitiesLayer([player, dormant])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.nearby) == 0

    def test_creature_at_different_location_excluded(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=25,
            attacks=(_SWORD,),
        )
        far_enemy = Character(
            id="far1",
            name="Distant Orc",
            location_id="forest",
            in_combat=True,
            active=True,
        )

        layer = EntitiesLayer([player, far_enemy])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.nearby) == 0


class TestCombatAwarenessDetail:
    """Combat awareness includes conditions and wound state on nearby enemies."""

    def test_nearby_enemy_conditions_included(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )
        poisoned_enemy = Character(
            id="e1",
            name="Goblin",
            location_id="arena",
            in_combat=True,
            max_hp=20,
            current_hp=15,
            conditions={Condition.POISONED: 3, Condition.PRONE: None},
        )

        layer = EntitiesLayer([player, poisoned_enemy])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        battle_map.set_position("e1", Position(15, 10))
        combat = CombatState(location_id="arena", turn_order=["p1", "e1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.nearby) == 1
        assert Condition.POISONED in awareness.nearby[0].conditions
        assert Condition.PRONE in awareness.nearby[0].conditions

    def test_is_wounded_when_hp_below_half(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )
        wounded = Character(
            id="e1",
            name="Goblin",
            location_id="arena",
            in_combat=True,
            max_hp=20,
            current_hp=9,  # 9 < 20 // 2 = 10
        )

        layer = EntitiesLayer([player, wounded])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        battle_map.set_position("e1", Position(15, 10))
        combat = CombatState(location_id="arena", turn_order=["p1", "e1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert awareness.nearby[0].is_wounded is True

    def test_not_wounded_at_exactly_half_hp(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )
        half_hp = Character(
            id="e1",
            name="Goblin",
            location_id="arena",
            in_combat=True,
            max_hp=20,
            current_hp=10,  # 10 == 20 // 2, not wounded
        )

        layer = EntitiesLayer([player, half_hp])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 10))
        battle_map.set_position("e1", Position(15, 10))
        combat = CombatState(location_id="arena", turn_order=["p1", "e1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert awareness.nearby[0].is_wounded is False


class TestCombatAwarenessBattleMapWalls:
    """Combat awareness includes wall descriptions and handles missing combat."""

    def test_walls_on_battle_map_included(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])
        battle_map = BattleMap(
            width=60,
            height=60,
            walls=[Wall(x1=30, y1=0, x2=30, y2=30)],
        )
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.walls) > 0

    def test_no_combat_for_location_returns_defaults(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])

        awareness = layer.build_combat_awareness(player)
        assert isinstance(awareness, CombatAwareness)
        assert awareness.round_number == 1
        assert awareness.nearby == []
        assert awareness.walls == []
        assert awareness.battle_map_ascii == ""


class TestCombatAwarenessStructuredGrid:
    """Combat awareness includes structured grid data for frontend rendering."""

    def test_grid_dimensions_from_battle_map(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])
        battle_map = BattleMap(width=40, height=30)
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert awareness.battle_map_width == 40
        assert awareness.battle_map_height == 30

    def test_inner_walls_in_structured_data(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])
        battle_map = BattleMap(
            width=60,
            height=60,
            walls=[Wall(x1=30, y1=0, x2=30, y2=30)],
        )
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.battle_map_walls) == 1
        wall = awareness.battle_map_walls[0]
        assert wall == {"x1": 30, "y1": 0, "x2": 30, "y2": 30}

    def test_multiple_inner_walls(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])
        inner_walls = [
            Wall(x1=20, y1=0, x2=20, y2=20),
            Wall(x1=0, y1=30, x2=40, y2=30),
        ]
        battle_map = BattleMap(width=60, height=60, walls=inner_walls)
        battle_map.set_position("p1", Position(10, 10))
        combat = CombatState(location_id="arena", turn_order=["p1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert len(awareness.battle_map_walls) == 2

    def test_no_combat_returns_zero_grid_defaults(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )

        layer = EntitiesLayer([player])

        awareness = layer.build_combat_awareness(player)
        assert awareness.battle_map_width == 0
        assert awareness.battle_map_height == 0
        assert awareness.battle_map_walls == []

    def test_nearby_entities_have_grid_coordinates(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="arena",
            in_combat=True,
            max_hp=30,
            current_hp=30,
            attacks=(_SWORD,),
        )
        enemy = Character(
            id="e1",
            name="Goblin",
            location_id="arena",
            in_combat=True,
            max_hp=10,
            current_hp=10,
        )

        layer = EntitiesLayer([player, enemy])
        battle_map = BattleMap(width=60, height=60)
        battle_map.set_position("p1", Position(10, 15))
        battle_map.set_position("e1", Position(25, 35))
        combat = CombatState(location_id="arena", turn_order=["p1", "e1"], battle_map=battle_map)
        layer._combat._combats["arena"] = combat

        awareness = layer.build_combat_awareness(player)
        assert awareness.nearby[0].x == 25
        assert awareness.nearby[0].y == 35


class TestNearbyEntityFactionName:
    """Nearby entities include faction display name resolved via politics query."""

    def test_faction_name_populated_from_query(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="road",
            faction_id="kingdom",
        )
        npc = Character(
            id="n1",
            name="Guard",
            location_id="road",
            faction_id="kingdom",
        )

        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_NAME:
                return Answer(value="Kingdom Forces")
            return Answer(value=None)

        nearby = layer.build_nearby_entities(player, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].faction_id == "kingdom"
        assert nearby[0].faction_name == "Kingdom Forces"

    def test_faction_name_empty_when_no_faction(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="road",
        )
        npc = Character(
            id="n1",
            name="Wanderer",
            location_id="road",
        )

        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        nearby = layer.build_nearby_entities(player, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].faction_id == ""
        assert nearby[0].faction_name == ""

    def test_faction_name_falls_back_to_empty_when_query_returns_none(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="road",
            faction_id="kingdom",
        )
        npc = Character(
            id="n1",
            name="Guard",
            location_id="road",
            faction_id="unknown_faction",
        )

        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_NAME:
                return Answer(value=None)
            return Answer(value=None)

        nearby = layer.build_nearby_entities(player, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].faction_name == ""


class TestFactionHostilityEdgeCases:
    """Edge cases for faction hostility checks."""

    def test_both_no_faction_returns_false_no_query(self) -> None:
        observer = Character(id="a", name="Wanderer", location_id="road")
        other = Character(id="b", name="Traveler", location_id="road")

        layer = EntitiesLayer([observer, other])
        calls: list[str] = []

        def query_fn(target: str, query: Query) -> Answer:
            calls.append(target)
            return Answer(value=None)

        result = layer._awareness.check_faction_hostility(observer, other, query_fn)
        assert result is False
        assert len(calls) == 0

    def test_query_fn_none_returns_false(self) -> None:
        observer = Character(id="a", name="Elf", location_id="road", faction_id="elves")
        other = Character(id="b", name="Orc", location_id="road", faction_id="horde")

        layer = EntitiesLayer([observer, other])

        result = layer._awareness.check_faction_hostility(observer, other, None)
        assert result is False

    def test_politics_query_raises_returns_false(self) -> None:
        observer = Character(id="a", name="Elf", location_id="road", faction_id="elves")
        other = Character(id="b", name="Orc", location_id="road", faction_id="horde")

        layer = EntitiesLayer([observer, other])

        def query_fn(target: str, query: Query) -> Answer:
            raise LayerError("politics layer not found")

        result = layer._awareness.check_faction_hostility(observer, other, query_fn)
        assert result is False
