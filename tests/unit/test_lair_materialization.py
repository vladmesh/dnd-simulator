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
from dnd_simulator.core.models import ActionResult, Answer, FactionRelation, GameDateTime, Query, TimeDelta
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


def _lair(
    location: str = "warren",
    core: str | None = "goblin_chieftain",
    respawn_interval: int = 3600,
) -> Lair:
    return Lair(
        id="goblin_warren",
        name="Goblin Warren",
        faction_id="goblin_tribe",
        location_id=location,
        members=["goblin", "goblin", "goblin"],
        core=core,
        respawn_interval=respawn_interval,
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
    lairs: list[Lair] | None = None,
    entities: list[object] | None = None,
    relation: FactionRelation = FactionRelation.HOSTILE,
    ecology: EcologyLayer | None = None,
) -> tuple[EcologyLayer, EntitiesLayer, object, object]:
    ecology = ecology if ecology is not None else EcologyLayer(lairs=lairs or [])
    entities_layer = EntitiesLayer(entities=entities or [], monster_templates=_templates())  # type: ignore[arg-type]
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


# T0 = leave time; T_SOON = +30 min (< 3600s interval); T_LATER = +2 h (>= interval)
T0 = GameDateTime(year=1490, month=6, day=1, hour=10)
T_SOON = GameDateTime(year=1490, month=6, day=1, hour=10, minute=30)
T_LATER = GameDateTime(year=1490, month=6, day=1, hour=12)
_HOUR = TimeDelta(seconds=3600)


def _goblins(entities: EntitiesLayer) -> list[Creature]:
    return [c for c in _lair_creatures(entities) if c.name == "Goblin"]


class TestLairRespawn:
    def _enter_kill_leave(self) -> tuple[EcologyLayer, PlayerCharacter, object, object]:
        """Enter the lair, kill 2 of 3 goblins, leave. Returns the ecology + reusable player/fns."""
        player = _player()
        eco, entities, qfn, efn = _make_layers([_lair()], entities=[player], relation=FactionRelation.NEUTRAL)
        entities.update_activation(T0, query_fn=qfn, emit_fn=efn)
        goblins = _goblins(entities)
        assert len(goblins) == 3
        goblins[0].current_hp = 0
        goblins[1].current_hp = 0
        player.location_id = "elsewhere"
        entities.update_activation(T0, query_fn=qfn, emit_fn=efn)
        return eco, player, qfn, efn

    def _reenter(self, eco: EcologyLayer, time: GameDateTime) -> EntitiesLayer:
        """Bring a fresh player into the lair against the given ecology, return entities layer."""
        _eco, entities, qfn, efn = _make_layers(entities=[_player()], relation=FactionRelation.NEUTRAL, ecology=eco)
        entities.update_activation(time, query_fn=qfn, emit_fn=efn)
        return entities

    def test_losses_persist_without_respawn_before_interval(self) -> None:
        eco, _player_obj, qfn, efn = self._enter_kill_leave()
        eco.tick(_HOUR, T_SOON, qfn, efn)  # +30 min < interval → no respawn
        entities = self._reenter(eco, T_SOON)
        assert len(_goblins(entities)) == 1

    def test_minions_respawn_to_full_after_interval(self) -> None:
        eco, _player_obj, qfn, efn = self._enter_kill_leave()
        eco.tick(_HOUR, T_LATER, qfn, efn)  # +2 h >= interval → respawn
        entities = self._reenter(eco, T_LATER)
        assert len(_goblins(entities)) == 3

    def test_respawn_does_not_overflow_roster(self) -> None:
        eco, _player_obj, qfn, efn = self._enter_kill_leave()
        # Tick several intervals — population must cap at the full roster, never grow past it.
        eco.tick(_HOUR, T_LATER, qfn, efn)
        eco.tick(_HOUR, GameDateTime(year=1490, month=6, day=1, hour=14), qfn, efn)
        entities = self._reenter(eco, GameDateTime(year=1490, month=6, day=1, hour=14))
        assert len(_goblins(entities)) == 3

    def test_losses_survive_save_load(self) -> None:
        eco, _player_obj, _qfn, _efn = self._enter_kill_leave()
        saved = eco.get_state()

        eco2 = EcologyLayer(lairs=[_lair()])
        eco2.load_state(saved)
        # Re-enter before any respawn tick → the two dead goblins are still gone.
        entities = self._reenter(eco2, T0)
        assert len(_goblins(entities)) == 1
