"""Lair materialization tests (Sprint 018 phase 1 task 1).

A lair is a fixed place with a persistent monster population. When a player enters
the lair's location, the full roster (core + minions) materializes as concrete
hostile creatures; leaving dematerializes them. Respawn and depletion are later tasks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.character import AbilityScores, Attack, Creature
from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import ActionResult, Answer, FactionRelation, GameDateTime, Query
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _ability() -> AbilityScores:
    return AbilityScores.from_dict({"str": 10, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})


def _template(tid: str, hp: int, faction: str = "goblin_tribe") -> MonsterTemplate:
    return MonsterTemplate(
        id=tid,
        name=tid.replace("_", " ").title(),
        hp=hp,
        ac=13,
        speed=30,
        ability_scores=_ability(),
        attacks=(Attack(name="scimitar", damage="1d6", ability="dexterity", reach=5),),
        cr=0.25,
        faction_id=faction,
    )


def _templates() -> dict[str, MonsterTemplate]:
    return {
        "goblin": _template("goblin", hp=7),
        "goblin_chieftain": _template("goblin_chieftain", hp=21),
    }


def _lair(location: str = "warren", core: str | None = "goblin_chieftain") -> Lair:
    return Lair(
        id="goblin_warren",
        name="Goblin Warren",
        faction_id="goblin_tribe",
        location_id=location,
        members=["goblin", "goblin", "goblin"],
        core=core,
    )


def _player(location: str = "warren") -> PlayerCharacter:
    p = PlayerCharacter(
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
    p.faction_id = "townsfolk"
    return p


def _make_layers(
    lairs: list[Lair],
    entities: list[object],
    relation: FactionRelation = FactionRelation.HOSTILE,
) -> tuple[EcologyLayer, EntitiesLayer, object, object]:
    ecology = EcologyLayer(lairs=lairs)
    entities_layer = EntitiesLayer(entities=entities, monster_templates=_templates())  # type: ignore[arg-type]
    layers = {"ecology": ecology, "entities": entities_layer}

    def query_fn(layer_name: str, query: Query) -> Answer:
        if layer_name == "politics":
            return Answer(value=relation)
        return layers[layer_name].query(query)

    def emit_fn(event: object) -> ActionResult:
        from dnd_simulator.core.models import Event

        assert isinstance(event, Event)
        ecology.handle_event(event, query_fn, emit_fn)  # type: ignore[arg-type]
        return ActionResult()

    return ecology, entities_layer, query_fn, emit_fn


def _lair_creatures(entities: EntitiesLayer) -> list[Creature]:
    return [e for e in entities._entities.values() if isinstance(e, Creature) and e.id != "player_1"]


class TestLairMaterialization:
    def test_full_roster_materializes_at_player_location(self) -> None:
        _eco, entities, qfn, efn = _make_layers([_lair()], entities=[_player()])

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        creatures = _lair_creatures(entities)
        # 1 chieftain + 3 goblins
        assert len(creatures) == 4
        names = sorted(c.name for c in creatures)
        assert names == ["Goblin", "Goblin", "Goblin", "Goblin Chieftain"]
        for c in creatures:
            assert c.temporary is True
            assert c.faction_id == "goblin_tribe"
            assert c.brain is not None

    def test_core_is_tougher_than_minions(self) -> None:
        _eco, entities, qfn, efn = _make_layers([_lair()], entities=[_player()])
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        chieftain = next(c for c in _lair_creatures(entities) if c.name == "Goblin Chieftain")
        goblin = next(c for c in _lair_creatures(entities) if c.name == "Goblin")
        assert chieftain.max_hp > goblin.max_hp

    def test_coreless_lair_materializes_only_minions(self) -> None:
        _eco, entities, qfn, efn = _make_layers([_lair(core=None)], entities=[_player()])
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        creatures = _lair_creatures(entities)
        assert len(creatures) == 3
        assert all(c.name == "Goblin" for c in creatures)

    def test_auto_combat_starts_when_hostile(self) -> None:
        _eco, entities, qfn, efn = _make_layers([_lair()], entities=[_player()])
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        assert "warren" in entities.get_combat_locations()

    def test_no_double_spawn_on_repeated_activation(self) -> None:
        _eco, entities, qfn, efn = _make_layers([_lair()], entities=[_player()])
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        assert len(_lair_creatures(entities)) == 4


class TestLairDematerialization:
    def test_lair_dematerializes_when_player_leaves(self) -> None:
        player = _player()
        # NEUTRAL relation → no auto-combat, so leaving cleanly dematerializes
        # (an in-combat lair is held in place, same as squads).
        _eco, entities, qfn, efn = _make_layers([_lair()], entities=[player], relation=FactionRelation.NEUTRAL)

        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        assert len(_lair_creatures(entities)) == 4

        player.location_id = "elsewhere"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        assert len(_lair_creatures(entities)) == 0


class TestLairContentLoading:
    def test_lair_loads_via_game_service(self, tmp_path: Path) -> None:
        svc = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=CONTENT_DIR)
        session = svc.start_game("test_vale")
        ecology = session.world.layers[3]
        lairs = ecology._lairs  # type: ignore[attr-defined]
        assert "goblin_warren" in lairs
        lair = lairs["goblin_warren"]
        assert lair.core == "goblin_chieftain"
        assert len(lair.members) == 3
        assert lair.state is LairState.ACTIVE

    def test_unknown_template_ref_raises(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader.monsters import load_lairs

        (tmp_path / "lairs.yaml").write_text(
            "bad_lair:\n"
            "  name: {en: Bad Lair}\n"
            "  faction: goblin_tribe\n"
            "  location: warren\n"
            "  core: ancient_dragon\n"
            "  members: [goblin]\n",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="ancient_dragon"):
            load_lairs(tmp_path, known_templates={"goblin"})
