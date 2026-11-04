"""Awareness fallbacks and faction relations for non-creature entities."""

from __future__ import annotations

import random

import pytest

from dnd_simulator.core.character import Ability, Attack, Character, Creature, DamageComponent, DamageType, Entity
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import Answer, FactionRelation, GameDateTime, Query, QueryType
from dnd_simulator.core.queries import LeaderInfo, NationInfo, RegionInfo, WeatherInfo
from dnd_simulator.core.world import LayerError
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder, format_weapon_damage
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _builder(*entities: Entity) -> AwarenessBuilder:
    return EntitiesLayer(list(entities), seed=0, dice_rng=random.Random(0))._awareness


@pytest.mark.parametrize(
    ("damage", "expected"),
    [
        ((), "1"),
        ((DamageComponent(dice="1d8", type=DamageType.SLASHING),), "1d8 slashing"),
        (
            (
                DamageComponent(dice="1d8+2", type=DamageType.SLASHING),
                DamageComponent(dice="1d6", type=DamageType.FIRE),
            ),
            "1d8+2 slashing + 1d6 fire",
        ),
    ],
)
def test_weapon_damage_summary(damage: tuple[DamageComponent, ...], expected: str) -> None:
    attack = Attack(name="Sword", ability=Ability.STR, damage=damage)

    assert format_weapon_damage(attack) == expected


@pytest.mark.parametrize("failed_query", [QueryType.REGION_INFO, QueryType.WEATHER, QueryType.REGION_SETTLEMENTS])
@pytest.mark.parametrize("error_type", [KeyError, ValueError, LayerError])
def test_region_query_failure_preserves_remaining_awareness(
    failed_query: QueryType, error_type: type[Exception]
) -> None:
    observer = Character(id="observer", name="Observer", location_id="road")
    answers: dict[tuple[str, QueryType], object] = {
        ("geography", QueryType.LOCATION_REGION): "valley",
        ("geography", QueryType.REGION_INFO): RegionInfo(
            id="valley",
            name="Green Valley",
            latitude=10,
            longitude=20,
            elevation=30,
            terrain="plains",
            water_proximity=0.5,
            weather="rain",
            temperature=8,
        ),
        ("geography", QueryType.WEATHER): WeatherInfo(condition="rain", temperature=8),
        ("settlements", QueryType.REGION_SETTLEMENTS): [],
        ("politics", QueryType.REGION_OWNER): "kingdom",
        ("politics", QueryType.NATION_INFO): NationInfo(
            id="kingdom",
            name="Valley Kingdom",
            regions=("valley",),
            wealth=100,
            military=20,
            stability=0.8,
            leader=LeaderInfo(name="Regent", age=40, trait="wise"),
        ),
    }

    def query_fn(target: str, query: Query) -> Answer:
        if query.question == failed_query:
            raise error_type("Region data unavailable")
        key = (target, query.question)
        if key not in answers:
            raise AssertionError(f"Unexpected query: {key}")
        return Answer(value=answers[key])

    awareness = _builder(observer).build_peaceful_awareness(observer, GameDateTime(hour=10), query_fn)

    expected_weather = {"condition": "rain", "temperature": 8}
    if failed_query == QueryType.WEATHER:
        expected_weather = {"condition": "clear", "temperature": 15}
    assert awareness.weather == expected_weather
    assert awareness.location_name == "road"
    assert awareness.region_name == ("road" if failed_query == QueryType.REGION_INFO else "Green Valley")
    assert awareness.settlements == (None if failed_query == QueryType.REGION_SETTLEMENTS else [])
    assert awareness.territory_owner == "kingdom"
    assert awareness.nation_info == {
        "id": "kingdom",
        "name": "Valley Kingdom",
        "regions": ("valley",),
        "wealth": 100,
        "military": 20,
        "stability": 0.8,
        "leader": {"name": "Regent", "age": 40, "trait": "wise"},
    }


@pytest.mark.parametrize(
    ("other_faction", "query_relation", "expected_relation", "expected_hostile"),
    [
        ("kingdom", FactionRelation.HOSTILE, "friendly", False),
        ("rivals", FactionRelation.FRIENDLY, "friendly", False),
        ("rivals", FactionRelation.NEUTRAL, "neutral", False),
        ("rivals", FactionRelation.HOSTILE, "hostile", True),
    ],
)
def test_plain_entity_uses_faction_relation(
    other_faction: str,
    query_relation: FactionRelation,
    expected_relation: str,
    expected_hostile: bool,
) -> None:
    observer = Character(id="observer", name="Observer", location_id="road", faction_id="kingdom")
    other = Entity(id="banner", name="Banner", location_id="road", faction_id=other_faction)

    def query_fn(target: str, query: Query) -> Answer:
        if target == "politics" and query.question == QueryType.FACTION_RELATION:
            return Answer(value=query_relation)
        if target == "politics" and query.question == QueryType.FACTION_NAME:
            return Answer(value="Banner Faction")
        raise AssertionError(f"Unexpected query: {target} {query.question}")

    nearby = _builder(observer, other).build_nearby_entities(observer, hour=10, query_fn=query_fn)

    assert len(nearby) == 1
    assert nearby[0].id == other.id
    assert nearby[0].relation == expected_relation
    assert nearby[0].is_hostile is expected_hostile
    assert nearby[0].faction_name == "Banner Faction"
    assert nearby[0].lootable is False


@pytest.mark.parametrize("error_type", [KeyError, ValueError, LayerError])
def test_failed_faction_relation_keeps_plain_entity_visible_and_neutral(error_type: type[Exception]) -> None:
    observer = Character(id="observer", name="Observer", location_id="road", faction_id="kingdom")
    other = Entity(id="banner", name="Banner", location_id="road", faction_id="rivals")

    def query_fn(target: str, query: Query) -> Answer:
        if target == "politics" and query.question == QueryType.FACTION_RELATION:
            raise error_type("Relations unavailable")
        if target == "politics" and query.question == QueryType.FACTION_NAME:
            return Answer(value="Rivals")
        raise AssertionError(f"Unexpected query: {target} {query.question}")

    nearby = _builder(observer, other).build_nearby_entities(observer, hour=10, query_fn=query_fn)

    assert len(nearby) == 1
    assert nearby[0].id == other.id
    assert nearby[0].relation == "neutral"
    assert nearby[0].is_hostile is False
    assert nearby[0].faction_name == "Rivals"


def test_faction_relations_are_neutral_without_query_callback() -> None:
    observer = Character(id="observer", name="Observer", location_id="road", faction_id="kingdom")
    other = Entity(id="banner", name="Banner", location_id="road", faction_id="rivals")

    nearby = _builder(observer, other).build_nearby_entities(observer, hour=10)

    assert len(nearby) == 1
    assert nearby[0].id == other.id
    assert nearby[0].relation == "neutral"
    assert nearby[0].is_hostile is False
    assert nearby[0].faction_name == ""


@pytest.mark.parametrize(("current_hp", "active"), [(4, True), (4, False), (0, True), (0, False)])
def test_inactive_living_creatures_are_hidden_but_corpses_remain_lootable(current_hp: int, active: bool) -> None:
    observer = Creature(id="observer", name="Observer", location_id="road")
    potion = Item(id="potion", name="Healing Potion", item_type=ItemType.POTION, params={"heal_dice": "1d4"})
    other = Creature(
        id="other",
        name="Other",
        location_id="road",
        current_hp=current_hp,
        active=active,
        inventory=[potion],
        gold=7,
    )

    nearby = _builder(observer, other).build_nearby_entities(observer, hour=10)

    if current_hp > 0 and not active:
        assert nearby == []
        return
    assert len(nearby) == 1
    visible = nearby[0]
    assert visible.id == other.id
    assert visible.name == "Other"
    assert visible.is_dead is (current_hp == 0)
    assert visible.lootable is (current_hp == 0)
    assert visible.is_hostile is False
    if current_hp == 0:
        assert [item.id for item in visible.loot_items] == [potion.id]
        assert visible.loot_items[0].description == "Healing Potion (heals 1d4 HP)"
        assert visible.loot_gold == 7
    else:
        assert visible.loot_items == []
        assert visible.loot_gold == 0
