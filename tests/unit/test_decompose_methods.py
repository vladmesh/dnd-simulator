"""Tests for decomposed resolve_attack and query dispatch — lock in behavior before refactor."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    CharClass,
    DamageComponent,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _faction_query_fn(layer: str, query: Query) -> Answer:
    """Query function that resolves FACTION_RELATION: same faction = friendly."""
    if query.question is QueryType.FACTION_RELATION:
        a, b = str(query.params["a"]), str(query.params["b"])
        return Answer(value=FactionRelation.FRIENDLY if a == b else FactionRelation.HOSTILE)
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _dagger() -> Attack:
    return Attack(
        name="dagger",
        ability=Ability.DEX,
        damage=(DamageComponent("1d4", DamageType.PIERCING),),
        is_finesse=True,
    )


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _attack_event(attacker_id: str = "rogue", target_id: str = "target") -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK,
        source_layer="entities",
        data={"attacker_id": attacker_id, "target_id": target_id},
    )


class TestSneakAttackWithAllyAdjacency:
    """Rogue sneak attack fires when ally is within 5ft of target on battle map."""

    def test_sneak_attack_adds_extra_damage_with_ally_adjacent(self) -> None:
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            ability_scores=_scores(DEX=18),
            attacks=(_dagger(),),
            race=Race.HUMAN,
            char_class=CharClass.ROGUE,
            class_features=[RogueFeatures(sneak_attack_dice=2)],
            faction_id="party",
        )
        target = Character(
            id="target", name="Goblin", location_id="arena", max_hp=50, current_hp=50, ac=5, faction_id="goblins"
        )
        ally = Character(
            id="ally",
            name="Fighter",
            location_id="arena",
            ability_scores=_scores(STR=16),
            attacks=(_sword(),),
            faction_id="party",
        )

        bm = BattleMap(width=20, height=20)
        layer = EntitiesLayer([rogue, target, ally], battle_map_configs={"arena": bm})
        layer._combat.start_combat("arena")

        combat = layer.get_combat("arena")
        assert combat is not None
        # Place: rogue far, target center, ally within 5ft of target
        combat.battle_map.set_position("rogue", Position(5, 5))
        combat.battle_map.set_position("target", Position(10, 10))
        combat.battle_map.set_position("ally", Position(10, 15))  # 5ft from target

        # Run attacks until one hits — check for sneak attack in event data
        found_sneak = False
        for _ in range(30):
            target.current_hp = 50
            result = layer.handle_event(_attack_event(), _faction_query_fn, _noop_emit_fn)
            if result.success:
                log = layer._location_log["arena"]
                attack_events = [e for e in log if e.event_type == EventType.ENTITY_ATTACK and e.data.get("hit")]
                for ae in attack_events:
                    damage_components = ae.data.get("damage_components", [])
                    if any(dc.get("source") == "sneak_attack" for dc in damage_components):
                        found_sneak = True
                        break
                if found_sneak:
                    break

        assert found_sneak, "Sneak attack never triggered with ally adjacent in 30 tries"


class TestAttackWithBlessDiceBonus:
    """Blessed attacker should have bless d4 in attack roll components."""

    def test_bless_d4_appears_in_attack_roll_components(self) -> None:
        scores = AbilityScores()
        scores[Ability.STR] = 18
        attacker = Character(
            id="attacker", name="Paladin", location_id="arena", ability_scores=scores, attacks=(_sword(),)
        )
        attacker.conditions[Condition.BLESSED] = 3
        target = Character(id="target", name="Goblin", location_id="arena", max_hp=50, current_hp=50, ac=5)

        bm = BattleMap(width=20, height=20)
        layer = EntitiesLayer([attacker, target], battle_map_configs={"arena": bm})
        layer._combat.start_combat("arena")
        combat = layer.get_combat("arena")
        assert combat is not None
        combat.battle_map.set_position("attacker", Position(10, 10))
        combat.battle_map.set_position("target", Position(15, 10))

        # Attack and find bless in roll components
        found_bless = False
        for _ in range(20):
            target.current_hp = 50
            layer.handle_event(_attack_event("attacker", "target"), _noop_query_fn, _noop_emit_fn)
            log = layer._location_log["arena"]
            for ev in log:
                if ev.event_type == EventType.ENTITY_ATTACK:
                    roll_data = ev.data.get("attack_roll")
                    if roll_data is not None:
                        for component in roll_data.components:
                            if component.source == "blessed" and component.dice == "1d4":
                                found_bless = True
            if found_bless:
                break

        assert found_bless, "Bless d4 never appeared in attack roll components"


class TestAttackDeathCombatEnd:
    """Killing a target produces death event and combat end in correct order."""

    def test_kill_triggers_death_then_combat_end(self) -> None:
        attacker = Character(
            id="attacker",
            name="Fighter",
            location_id="arena",
            ability_scores=_scores(STR=18),
            attacks=(_sword(),),
        )
        target = Character(id="target", name="Goblin", location_id="arena", max_hp=1, current_hp=1, ac=1)

        bm = BattleMap(width=20, height=20)
        layer = EntitiesLayer([attacker, target], battle_map_configs={"arena": bm})
        layer._combat.start_combat("arena")
        combat = layer.get_combat("arena")
        assert combat is not None
        combat.battle_map.set_position("attacker", Position(10, 10))
        combat.battle_map.set_position("target", Position(15, 10))

        # Attack until kill
        killed = False
        for _ in range(30):
            target.current_hp = 1
            target.in_combat = True
            result = layer.handle_event(_attack_event("attacker", "target"), _noop_query_fn, _noop_emit_fn)
            if result.events:
                death_events = [e for e in result.events if e.event_type == EventType.ENTITY_DIED]
                if death_events:
                    killed = True
                    break

        assert killed, "Never killed target in 30 tries"
        assert not target.is_alive

        # Check event order in location log: attack → death → combat_ended
        log = layer._location_log["arena"]
        types = [e.event_type for e in log]
        # Find last attack, death must follow, then combat_ended
        last_attack_idx = max(i for i, t in enumerate(types) if t == EventType.ENTITY_ATTACK)
        assert EventType.ENTITY_DIED in types[last_attack_idx:]
        assert EventType.COMBAT_ENDED in types[last_attack_idx:]
        death_idx = types.index(EventType.ENTITY_DIED, last_attack_idx)
        combat_end_idx = types.index(EventType.COMBAT_ENDED, last_attack_idx)
        assert death_idx < combat_end_idx, "Death should come before combat end"


class TestQueryDispatch:
    """Query dispatch returns correct data for various query types."""

    def test_entities_at_location_filters_by_location(self) -> None:
        c1 = Character(id="c1", name="Alice", location_id="tavern")
        c2 = Character(id="c2", name="Bob", location_id="market")
        layer = EntitiesLayer([c1, c2])

        result = layer.query(
            Query(question=QueryType.ENTITIES_AT_LOCATION, params={"location_id": "tavern", "hour": 12})
        )
        assert len(result.value) == 1
        assert result.value[0]["name"] == "Alice"

    def test_all_creatures_with_type_filter(self) -> None:
        player = PlayerCharacter(id="p1", name="Hero", location_id="tavern")
        npc = Npc(id="n1", name="Guard", location_id="tavern", role=NpcRole.GUARD, settlement_id="town")
        layer = EntitiesLayer([player, npc])

        result = layer.query(Query(question=QueryType.ALL_CREATURES, params={"entity_type": "npc"}))
        assert len(result.value) == 1
        assert result.value[0]["id"] == "n1"

    def test_combat_info_returns_none_without_combat(self) -> None:
        c = Character(id="c1", name="Hero", location_id="tavern")
        layer = EntitiesLayer([c])

        result = layer.query(Query(question=QueryType.COMBAT_INFO, params={"location_id": "tavern"}))
        assert result.value is None

    def test_combat_info_returns_data_with_active_combat(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="arena", ability_scores=_scores(STR=16))
        c2 = Character(id="c2", name="Rogue", location_id="arena", ability_scores=_scores(DEX=16))
        bm = BattleMap(width=20, height=20)
        layer = EntitiesLayer([c1, c2], battle_map_configs={"arena": bm})
        layer._combat.start_combat("arena")

        result = layer.query(Query(question=QueryType.COMBAT_INFO, params={"location_id": "arena"}))
        info = result.value
        assert isinstance(info, dict)
        assert "round_number" in info
        assert "turn_order" in info
        assert len(info["turn_order"]) == 2

    def test_unknown_query_raises(self) -> None:
        import pytest

        c = Character(id="c1", name="Hero", location_id="tavern")
        layer = EntitiesLayer([c])

        with pytest.raises(ValueError, match="Unknown entities query"):
            layer.query(Query(question=QueryType.WEATHER, params={}))
