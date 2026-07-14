"""Tests for the `take` loot action — provider, validation, handler, awareness.

Product-level: drives the real validation chain, the real handler, and the real
ActionDispatcher pipeline. Mocks only the World boundary (handlers resolve targets
via ctx.get_entity, not via World).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.container import Container
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.rules.handlers import handle_take
from dnd_simulator.rules.validation import ActionContext, validate_action
from dnd_simulator.service.action_dispatcher import create_dispatcher
from dnd_simulator.service.contextual_providers import LootActionProvider

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity

CAVE = "cave"
OTHER = "cave_mouth"

# Stub world — handlers resolve targets through ctx.get_entity, not World.
_WORLD = cast(World, MagicMock(spec=World))


# ── Fixtures ─────────────────────────────────────────────────────────


def _longsword() -> Item:
    return Item(id="longsword_0", name="Longsword", item_type=ItemType.WEAPON, price=15)


def _potion(n: int) -> Item:
    return Item(id=f"potion_{n}", name="Health Potion", item_type=ItemType.POTION, price=50)


def _player(*, gold: int = 0, location: str = CAVE) -> PlayerCharacter:
    return PlayerCharacter(id="player_1", name="Hero", location_id=location, gold=gold)


def _corpse(*, location: str = CAVE, items: list[Item] | None = None, gold: int = 0) -> Creature:
    c = Creature(id="goblin_corpse", name="Goblin", location_id=location, max_hp=7, current_hp=0)
    c.inventory = items if items is not None else []
    c.gold = gold
    return c


def _living_goblin(*, location: str = CAVE, items: list[Item] | None = None) -> Creature:
    c = Creature(id="goblin_live", name="Goblin", location_id=location, max_hp=10, current_hp=10)
    c.inventory = items if items is not None else []
    return c


def _container(
    *, location: str = CAVE, items: list[Item] | None = None, gold: int = 0, is_open: bool = True
) -> Container:
    return Container(
        id="chest_1",
        name="Chest",
        location_id=location,
        inventory=items if items is not None else [],
        gold=gold,
        is_open=is_open,
    )


def _ctx(entities: dict[str, Entity], *, is_combat: bool = False) -> ActionContext:
    return ActionContext(
        is_combat=is_combat,
        current_turn_entity_id="player_1",
        get_entity=lambda eid: entities.get(eid),
    )


def _capture() -> tuple[list[Event], object]:
    events: list[Event] = []
    return events, events.append


# ── Take handler — corpse ────────────────────────────────────────────


class TestLootCorpse:
    def test_take_moves_all_items_and_gold_from_corpse(self) -> None:
        sword = _longsword()
        corpse = _corpse(items=[sword], gold=50)
        player = _player(gold=0)
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        ctx = _ctx(entities)
        _events, emit = _capture()

        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_corpse"})
        result = handle_take(player, action, emit, ctx, _WORLD)  # type: ignore[arg-type]

        assert result.success
        assert sword in player.inventory
        assert player.gold == 50
        assert corpse.inventory == []
        assert corpse.gold == 0

    def test_take_emits_entity_take_event(self) -> None:
        sword = _longsword()
        corpse = _corpse(items=[sword], gold=50)
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        ctx = _ctx(entities)
        events, emit = _capture()

        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_corpse"})
        handle_take(player, action, emit, ctx, _WORLD)  # type: ignore[arg-type]

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == EventType.ENTITY_TAKE
        assert ev.data.actor_id == "player_1"
        assert ev.data.target_id == "goblin_corpse"
        assert ev.data.item_names == ("Longsword",)
        assert ev.data.gold == 50


# ── Take handler — container ─────────────────────────────────────────


class TestLootContainer:
    def test_take_moves_all_items_from_open_container(self) -> None:
        p1, p2 = _potion(0), _potion(1)
        chest = _container(items=[p1, p2])
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "chest_1": chest}
        ctx = _ctx(entities)
        _events, emit = _capture()

        action = Action(name=ActionType.TAKE, params={"target_id": "chest_1"})
        result = handle_take(player, action, emit, ctx, _WORLD)  # type: ignore[arg-type]

        assert result.success
        assert p1 in player.inventory
        assert p2 in player.inventory
        assert chest.inventory == []


# ── Validation ───────────────────────────────────────────────────────


class TestTakeValidation:
    def test_living_creature_not_lootable(self) -> None:
        sword = _longsword()
        goblin = _living_goblin(items=[sword])
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_live": goblin}
        ctx = _ctx(entities)

        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_live"})
        error = validate_action(player, action, ctx)

        assert error is not None
        assert error.code == "TARGET_NOT_LOOTABLE"
        # Nothing moved
        assert sword in goblin.inventory

    def test_wrong_location_rejected(self) -> None:
        sword = _longsword()
        corpse = _corpse(location=OTHER, items=[sword], gold=10)
        player = _player(location=CAVE)
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        ctx = _ctx(entities)

        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_corpse"})
        error = validate_action(player, action, ctx)

        assert error is not None
        assert error.code == "TARGET_WRONG_LOCATION"
        assert sword in corpse.inventory
        assert corpse.gold == 10

    def test_closed_container_not_lootable(self) -> None:
        chest = _container(items=[_potion(0)], is_open=False)
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "chest_1": chest}
        ctx = _ctx(entities)

        action = Action(name=ActionType.TAKE, params={"target_id": "chest_1"})
        error = validate_action(player, action, ctx)

        assert error is not None
        assert error.code == "TARGET_NOT_LOOTABLE"

    def test_corpse_is_valid_target(self) -> None:
        corpse = _corpse(items=[_longsword()], gold=5)
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        ctx = _ctx(entities)

        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_corpse"})
        assert validate_action(player, action, ctx) is None


# ── Availability gating (provider) ───────────────────────────────────


class TestLootProvider:
    def _provider(self, entities: dict[str, Entity]) -> LootActionProvider:
        from dnd_simulator.rules.loot import is_lootable

        def get_nearby_lootables(location_id: str) -> list[Entity]:
            return [e for e in entities.values() if e.location_id == location_id and is_lootable(e)]

        return LootActionProvider(get_nearby_lootables)

    def test_take_offered_when_lootable_present(self) -> None:
        corpse = _corpse(items=[_longsword()])
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        provider = self._provider(entities)

        actions = provider.get_action_types(player, _ctx(entities))
        assert ActionType.TAKE in actions

    def test_take_absent_when_no_lootable(self) -> None:
        goblin = _living_goblin()  # alive → not lootable
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_live": goblin}
        provider = self._provider(entities)

        actions = provider.get_action_types(player, _ctx(entities))
        assert ActionType.TAKE not in actions

    def test_take_absent_in_combat(self) -> None:
        corpse = _corpse(items=[_longsword()])
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        provider = self._provider(entities)

        actions = provider.get_action_types(player, _ctx(entities, is_combat=True))
        assert ActionType.TAKE not in actions


# ── Full dispatch pipeline ───────────────────────────────────────────


class TestTakeDispatch:
    def test_dispatch_take_loots_corpse(self) -> None:
        sword = _longsword()
        corpse = _corpse(items=[sword], gold=50)
        player = _player(gold=0)
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        ctx = _ctx(entities)
        _events, emit = _capture()

        dispatcher = create_dispatcher(_WORLD)
        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_corpse"})
        result = dispatcher.dispatch(player, action, ctx, emit)  # type: ignore[arg-type]

        assert result.success
        assert sword in player.inventory
        assert player.gold == 50
        assert corpse.inventory == []

    def test_dispatch_take_living_creature_rejected(self) -> None:
        sword = _longsword()
        goblin = _living_goblin(items=[sword])
        player = _player()
        entities: dict[str, Entity] = {"player_1": player, "goblin_live": goblin}
        ctx = _ctx(entities)
        events, emit = _capture()

        dispatcher = create_dispatcher(_WORLD)
        action = Action(name=ActionType.TAKE, params={"target_id": "goblin_live"})
        result = dispatcher.dispatch(player, action, ctx, emit)  # type: ignore[arg-type]

        assert not result.success
        assert sword in goblin.inventory
        assert len(events) == 0
