"""Lair treasury tests (Sprint 018 phase 2 task 4).

A lair with a `treasure` block spawns one persistent Container at materialization,
populated from content, optionally locked behind the core. The container persists
across leave/return and save/load, so looted treasure never refills. Reuses the
`Container` (task 2) and `take` (task 3) machinery — no new loot logic here.

Product-level: drives the real activation pipeline (EcologyLayer query →
ActivationManager → Container spawn/gate) and the real loot path.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.container import Container
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.lair import Lair
from dnd_simulator.core.models import ActionResult, Answer, Event, FactionRelation, GameDateTime, Query
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.handlers import handle_take
from dnd_simulator.rules.validation import ActionContext, validate_action

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)
TREASURY_ID = "goblin_warren_treasury"
_WORLD = cast(World, MagicMock(spec=World))


def _ability() -> AbilityScores:
    return AbilityScores.from_dict({"str": 10, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})


def _template(tid: str, hp: int) -> MonsterTemplate:
    return MonsterTemplate(
        id=tid,
        name=tid.replace("_", " ").title(),
        hp=hp,
        ac=13,
        speed=30,
        ability_scores=_ability(),
        attacks=(Attack(name="scimitar", ability=Ability.DEX, damage=(DamageComponent("1d6", DamageType.SLASHING),)),),
        cr=0.25,
        faction_id="goblin_tribe",
    )


def _templates() -> dict[str, MonsterTemplate]:
    return {"goblin": _template("goblin", hp=7), "goblin_chieftain": _template("goblin_chieftain", hp=21)}


def _sword() -> Item:
    return Item(id="flaming_longsword_0", name="Flaming Longsword", item_type=ItemType.WEAPON)


def _potion(i: int) -> Item:
    return Item(id=f"health_potion_{i}", name="Health Potion", item_type=ItemType.POTION, params={"heal_dice": "2d4+2"})


def _lair(
    *,
    core: str | None = "goblin_chieftain",
    treasure_items: list[Item] | None = None,
    treasure_gold: int = 100,
    behind_core: bool = True,
) -> Lair:
    return Lair(
        id="goblin_warren",
        name="Goblin Warren",
        faction_id="goblin_tribe",
        location_id="warren",
        members=["goblin", "goblin"],
        core=core,
        treasure_items=[_sword()] if treasure_items is None else treasure_items,
        treasure_gold=treasure_gold,
        treasure_behind_core=behind_core,
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
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
    )
    p.faction_id = "townsfolk"
    return p


def _make_layers(
    lair: Lair,
    player: PlayerCharacter,
    *,
    ecology: EcologyLayer | None = None,
) -> tuple[EcologyLayer, EntitiesLayer, object, object]:
    """Wire ecology + entities with a NEUTRAL politics relation (no auto-combat → peaceful looting)."""
    ecology = ecology if ecology is not None else EcologyLayer(lairs=[lair])
    entities_layer = EntitiesLayer(entities=[player], monster_templates=_templates())
    layers = {"ecology": ecology, "entities": entities_layer}

    def query_fn(layer_name: str, query: Query) -> Answer:
        if layer_name == "politics":
            return Answer(value=FactionRelation.NEUTRAL)
        return layers[layer_name].query(query)

    def emit_fn(event: object) -> ActionResult:
        assert isinstance(event, Event)
        ecology.handle_event(event, query_fn, emit_fn)  # type: ignore[arg-type]
        return ActionResult()

    return ecology, entities_layer, query_fn, emit_fn


def _treasury(entities: EntitiesLayer) -> Container | None:
    ent = entities.get_entity(TREASURY_ID)
    return ent if isinstance(ent, Container) else None


def _kill_core(entities: EntitiesLayer) -> None:
    for e in entities._entities.values():
        if isinstance(e, Creature) and e.name == "Goblin Chieftain":
            e.current_hp = 0


def _take(entities: EntitiesLayer, player: PlayerCharacter) -> ActionResult:
    ctx = ActionContext(is_combat=False, current_turn_entity_id=player.id, get_entity=entities.get_entity)
    action = Action(name=ActionType.TAKE, params={"target_id": TREASURY_ID})
    return handle_take(player, action, lambda _e: ActionResult(), ctx, _WORLD)  # type: ignore[arg-type]


# ── Spawn & contents ─────────────────────────────────────────────────


class TestTreasurySpawn:
    def test_treasury_spawns_with_contents(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        chest = _treasury(entities)
        assert chest is not None
        assert chest.location_id == "warren"
        assert chest.temporary is False
        assert chest.gold == 100
        assert [i.name for i in chest.inventory] == ["Flaming Longsword"]

    def test_no_treasure_block_no_container(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(treasure_items=[], treasure_gold=0), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        assert _treasury(entities) is None


# ── Gating behind core ───────────────────────────────────────────────


class TestTreasuryGate:
    def test_closed_while_core_alive(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(behind_core=True), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        chest = _treasury(entities)
        assert chest is not None
        assert chest.is_open is False
        # take rejected: a closed container is not lootable
        ctx = ActionContext(is_combat=False, current_turn_entity_id=player.id, get_entity=entities.get_entity)
        error = validate_action(player, Action(name=ActionType.TAKE, params={"target_id": TREASURY_ID}), ctx)
        assert error is not None
        assert error.code == "TARGET_NOT_LOOTABLE"

    def test_open_treasury_lootable_from_first_visit(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(behind_core=False), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        chest = _treasury(entities)
        assert chest is not None and chest.is_open is True

        result = _take(entities, player)
        assert result.success
        assert player.gold == 100
        assert any(i.name == "Flaming Longsword" for i in player.inventory)
        assert _treasury(entities).inventory == []  # type: ignore[union-attr]

    def test_core_death_unlocks_treasury_same_visit(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(behind_core=True), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        assert _treasury(entities).is_open is False  # type: ignore[union-attr]

        _kill_core(entities)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)  # next pass recomputes the gate

        chest = _treasury(entities)
        assert chest is not None and chest.is_open is True
        result = _take(entities, player)
        assert result.success
        assert player.gold == 100


# ── Persistence: no refill, dematerialize, save/load ─────────────────


class TestTreasuryPersistence:
    def test_persists_through_dematerialize(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(behind_core=False), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        assert _treasury(entities) is not None

        player.location_id = "elsewhere"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Roster gone, but the treasury container stays in the world.
        roster = [e for e in entities._entities.values() if isinstance(e, Creature) and e.id != "player_1"]
        assert roster == []
        assert _treasury(entities) is not None

    def test_no_refill_on_return(self) -> None:
        player = _player()
        _eco, entities, qfn, efn = _make_layers(_lair(behind_core=False), player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        _take(entities, player)
        assert _treasury(entities).inventory == []  # type: ignore[union-attr]

        player.location_id = "elsewhere"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)
        player.location_id = "warren"
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        chest = _treasury(entities)
        assert chest is not None
        assert chest.inventory == []  # nothing respawned
        assert chest.gold == 0

    def test_looted_state_survives_save_load(self) -> None:
        player = _player()
        lair = _lair(behind_core=False, treasure_items=[_potion(0), _potion(1)])
        _eco, entities, qfn, efn = _make_layers(lair, player)
        entities.update_activation(TIME, query_fn=qfn, emit_fn=efn)

        # Loot half: remove one potion via a take of a single-potion container is out of scope,
        # so simulate a partial loot by emptying one slot directly, then round-trip.
        chest = _treasury(entities)
        assert chest is not None
        chest.inventory.pop()  # one potion looted, one remains
        chest.gold = 0

        saved = entities.get_state()
        restored = EntitiesLayer(entities=[_player()], monster_templates=_templates())
        restored.load_state(saved)

        chest2 = _treasury(restored)
        assert chest2 is not None
        assert [i.name for i in chest2.inventory] == ["Health Potion"]
        assert chest2.gold == 0


# ── Content parsing ──────────────────────────────────────────────────


class TestTreasuryContentParse:
    def _catalog(self) -> dict[str, object]:
        from dnd_simulator.content_loader.schemas import ItemContent

        return {
            "flaming_longsword": ItemContent(name="Flaming Longsword", type=ItemType.WEAPON, is_magic=True),
            "health_potion": ItemContent(name="Health Potion", type=ItemType.POTION, heal_dice="2d4+2"),
        }

    def test_treasure_refs_resolve_against_catalog(self) -> None:
        from dnd_simulator.content_loader.monsters import parse_lairs

        data = {
            "goblin_warren": {
                "name": {"en": "Goblin Warren"},
                "faction": "goblins",
                "location": "cave",
                "core": "goblin",
                "members": ["goblin"],
                "treasure": {
                    "gold": 100,
                    "behind_core": True,
                    "items": [{"ref": "flaming_longsword"}],
                },
            }
        }
        lairs = parse_lairs(data, known_templates={"goblin"}, item_catalog=self._catalog())  # type: ignore[arg-type]
        lair = lairs["goblin_warren"]
        assert lair.treasure_gold == 100
        assert lair.treasure_behind_core is True
        assert [i.name for i in lair.treasure_items] == ["Flaming Longsword"]

    def test_unknown_treasure_ref_fails_fast(self) -> None:
        from dnd_simulator.content_loader.monsters import parse_lairs

        data = {
            "goblin_warren": {
                "name": {"en": "Goblin Warren"},
                "faction": "goblins",
                "location": "cave",
                "members": ["goblin"],
                "treasure": {"items": [{"ref": "no_such_item"}]},
            }
        }
        with pytest.raises(RuntimeError, match="no_such_item"):
            parse_lairs(data, known_templates={"goblin"}, item_catalog=self._catalog())  # type: ignore[arg-type]
