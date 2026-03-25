"""Tests for squad materialization and dematerialization."""

from __future__ import annotations

from dnd_simulator.core.character import AbilityScores, Attack, Creature
from dnd_simulator.core.models import ActionResult, Answer, GameDateTime, Query, QueryType
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _ability() -> AbilityScores:
    return AbilityScores.from_dict({"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})


def _attack() -> tuple[Attack, ...]:
    return (Attack(name="bite", damage="1d4", ability="strength", reach=5),)


def _template(tid: str = "wolf", cr: float = 0.25, faction: str = "wildlife") -> MonsterTemplate:
    return MonsterTemplate(
        id=tid,
        name=tid.capitalize(),
        hp=11,
        ac=13,
        speed=40,
        ability_scores=_ability(),
        attacks=_attack(),
        cr=cr,
        faction_id=faction,
    )


def _squad(
    squad_id: str = "wolf_pack",
    location: str = "forest",
    faction: str = "wildlife",
    strength: int = 6,
    max_strength: int = 6,
    members: list[str] | None = None,
) -> Squad:
    return Squad(
        id=squad_id,
        name=f"Squad {squad_id}",
        faction_id=faction,
        squad_type=SquadType.MONSTER_PACK,
        behavior=SquadBehavior.ROAM,
        current_location_id=location,
        route=[],
        territory=["forest", "road"],
        strength=strength,
        max_strength=max_strength,
        member_templates=members or ["wolf", "wolf", "wolf"],
        tick_interval=3600,
        member_crs=[0.25, 0.25, 0.25],
    )


def _player(location: str = "forest") -> PlayerCharacter:
    return PlayerCharacter(
        id="player_1",
        name="Hero",
        location_id=location,
        ability_scores=_ability(),
        max_hp=20,
        current_hp=20,
        ac=15,
        speed=30,
        race="human",
        char_class="fighter",
    )


def _make_ecology_and_entities(
    squads: list[Squad],
    templates: dict[str, MonsterTemplate] | None = None,
    entities: list | None = None,
) -> tuple[EcologyLayer, EntitiesLayer, object, object]:
    """Set up ecology + entities layers with query/emit fns wired together."""
    ecology = EcologyLayer(squads=squads)
    entities_layer = EntitiesLayer(
        entities=entities or [],
        monster_templates=templates or {"wolf": _template()},
    )

    layers = {"ecology": ecology, "entities": entities_layer}

    def query_fn(layer_name: str, query: Query) -> Answer:
        return layers[layer_name].query(query)

    def emit_fn(event: object) -> ActionResult:
        # Route events to ecology layer for strength updates
        from dnd_simulator.core.models import Event

        assert isinstance(event, Event)
        ecology.handle_event(event, query_fn, emit_fn)  # type: ignore[arg-type]
        return ActionResult()

    return ecology, entities_layer, query_fn, emit_fn


TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


class TestMaterialization:
    """Squad materializes when active character arrives at squad's location."""

    def test_squad_materializes_at_player_location(self) -> None:
        squad = _squad("wolves", location="forest")
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Should have spawned 3 wolf creatures + the player
        all_creatures = [e for e in entities._entities.values() if isinstance(e, Creature) and e.id != "player_1"]
        assert len(all_creatures) == 3
        for c in all_creatures:
            assert c.squad_id == "wolves"
            assert c.faction_id == "wildlife"
            assert c.temporary is True
            assert c.brain is not None

    def test_no_double_spawn_on_repeated_activation(self) -> None:
        squad = _squad("wolves", location="forest")
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Still only 3 wolves (no double-spawn)
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        assert len(wolves) == 3

    def test_strength_scales_creature_count(self) -> None:
        """Reduced strength squad spawns fewer creatures."""
        squad = _squad("wolves", location="forest", strength=2, max_strength=6)
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        # 3 templates * 2/6 = 1.0 → max(1, round(1.0)) = 1
        assert len(wolves) == 1


class TestDematerialization:
    """Squad dematerializes when active character leaves."""

    def test_squad_dematerializes_when_player_leaves(self) -> None:
        squad = _squad("wolves", location="forest")
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        # Materialize
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        assert len(wolves) == 3

        # Player moves away
        player.location_id = "town"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Wolves removed
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        assert len(wolves) == 0

    def test_dematerialization_updates_squad_strength(self) -> None:
        squad = _squad("wolves", location="forest", strength=6, max_strength=6)
        player = _player(location="forest")
        ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        # Materialize
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Kill one wolf
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        wolves[0].current_hp = 0

        # Player leaves → dematerialize
        player.location_id = "town"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Squad strength updated: 2/3 survived → strength = round(6 * 2/3) = 4
        info = ecology.query(Query(QueryType.SQUAD_INFO, params={"squad_id": "wolves"}))
        assert info.value["strength"] == 4

    def test_combat_prevents_dematerialization(self) -> None:
        squad = _squad("wolves", location="forest")
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities([squad], entities=[player])

        # Materialize
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Put wolves in combat
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        for w in wolves:
            w.in_combat = True

        # Player leaves
        player.location_id = "town"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Wolves still there (in combat)
        wolves = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        assert len(wolves) == 3


class TestMultipleSquads:
    """Multiple squads at same location materialize independently."""

    def test_two_squads_materialize_independently(self) -> None:
        wolves = _squad("wolves", location="forest", members=["wolf", "wolf"])
        bandits = _squad("bandits", location="forest", faction="bandits", members=["wolf"])
        player = _player(location="forest")
        _ecology, entities, qfn, efn = _make_ecology_and_entities(
            [wolves, bandits],
            entities=[player],
        )

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        wolf_creatures = [e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "wolves"]
        bandit_creatures = [
            e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id == "bandits"
        ]
        assert len(wolf_creatures) == 2
        assert len(bandit_creatures) == 1

        # Player leaves → both dematerialize
        player.location_id = "town"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        remaining = [
            e for e in entities._entities.values() if isinstance(e, Creature) and e.squad_id in ("wolves", "bandits")
        ]
        assert len(remaining) == 0
