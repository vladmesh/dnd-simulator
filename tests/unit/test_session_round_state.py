"""Tests for shared round callback payload builders."""

from __future__ import annotations

from dataclasses import fields
from typing import Any
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Ability, AbilityScores, Attack, Character, DamageComponent, DamageType
from dnd_simulator.core.models import Answer, GameDateTime, Query
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service.dto import PlayerStatusData
from dnd_simulator.service.transport_payloads import build_action_result, build_round_state

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


# Required fields for on_turn, on_action, and on_round_end messages
_COMMON_FIELDS = {"type", "mode", "awareness", "events", "player", "location"}


class _CapturingListener:
    """Listener that captures messages by type."""

    def __init__(self) -> None:
        self.turn_msgs: list[dict[str, Any]] = []
        self.action_msgs: list[dict[str, Any]] = []
        self.round_msgs: list[dict[str, Any]] = []
        self.reaction_msgs: list[dict[str, Any]] = []

    def on_turn(self, msg: dict[str, Any]) -> None:
        self.turn_msgs.append(msg)

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self.action_msgs.append(msg)

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self.round_msgs.append(msg)

    def on_reaction(self, msg: dict[str, Any]) -> None:
        self.reaction_msgs.append(msg)

    def on_game_over(self) -> None:
        pass


class TestBuildRoundState:
    """The payload builder produces the common dict used by all round callbacks."""

    def test_returns_common_fields(self) -> None:
        """The returned dict has all common fields: type, mode, awareness, events, player, location."""
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )

        entities_layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        time = GameDateTime(year=1490, month=6, day=15, hour=14)

        # Build a mock world + round just enough for build_round_state.
        world = MagicMock(spec=World)
        world.time = time
        world.make_query_fn.return_value = query_fn
        world.location_graph = MagicMock()
        world.location_graph.has.return_value = False

        game_round = MagicMock()
        game_round.get_perceived_events.return_value = []

        result = build_round_state("test_type", player, game_round, entities_layer, world)

        assert result["type"] == "test_type"
        assert result["mode"] in ("peaceful", "combat")
        assert "awareness" in result
        assert "events" in result
        assert "player" in result
        assert "location" in result

    def test_player_dict_matches_status_data(self) -> None:
        """The WS player payload has the same field set as PlayerStatusData, incl. appearance."""
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            appearance="a scarred veteran",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )

        entities_layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        world = MagicMock(spec=World)
        world.time = GameDateTime(year=1490, month=6, day=15, hour=14)
        world.make_query_fn.return_value = query_fn
        world.location_graph = MagicMock()
        world.location_graph.has.return_value = False

        game_round = MagicMock()
        game_round.get_perceived_events.return_value = []

        result = build_round_state("turn", player, game_round, entities_layer, world)

        expected_keys = {f.name for f in fields(PlayerStatusData)}
        assert set(result["player"].keys()) == expected_keys
        assert result["player"]["appearance"] == "a scarred veteran"


class TestCallbackFieldConsistency:
    """on_turn, on_action, and on_round_end messages all share the same base structure."""

    def test_action_result_has_common_fields(self) -> None:
        """on_action messages contain all common fields from _build_round_state."""
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )

        entities_layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        time = GameDateTime(year=1490, month=6, day=15, hour=14)

        world = MagicMock(spec=World)
        world.time = time
        world.make_query_fn.return_value = query_fn
        world.location_graph = MagicMock()
        world.location_graph.has.return_value = False

        game_round = MagicMock()
        game_round.get_perceived_events.return_value = []

        result = build_round_state("action_result", player, game_round, entities_layer, world)

        assert _COMMON_FIELDS.issubset(result.keys()), f"Missing fields: {_COMMON_FIELDS - result.keys()}"

    def test_round_result_has_common_fields(self) -> None:
        """on_round_end messages contain all common fields from _build_round_state."""
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )

        entities_layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        time = GameDateTime(year=1490, month=6, day=15, hour=14)

        world = MagicMock(spec=World)
        world.time = time
        world.make_query_fn.return_value = query_fn
        world.location_graph = MagicMock()
        world.location_graph.has.return_value = False

        game_round = MagicMock()
        game_round.get_perceived_events.return_value = []

        result = build_round_state("round_result", player, game_round, entities_layer, world)

        assert _COMMON_FIELDS.issubset(result.keys()), f"Missing fields: {_COMMON_FIELDS - result.keys()}"


class TestActionResultErrorGate:
    """build_action_result: actor/action broadcast for any creature; error and budget are player-only.

    Guards npc-action-errors-leak-to-log — a wolf's blocked-path refusal must never reach the
    player's combat log.
    """

    def _fixture(self) -> tuple[PlayerCharacter, Character, MagicMock, MagicMock, EntitiesLayer]:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="arena",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )
        wolf = Character(id="w1", name="Wolf", location_id="arena")
        entities_layer = EntitiesLayer([player, wolf])

        def query_fn(target: str, query: Query) -> Answer:
            return Answer(value=None)

        world = MagicMock(spec=World)
        world.time = GameDateTime(year=1490, month=6, day=15, hour=14)
        world.make_query_fn.return_value = query_fn
        world.location_graph = MagicMock()
        world.location_graph.has.return_value = False

        game_round = MagicMock()
        game_round.get_perceived_events.return_value = []

        return player, wolf, world, game_round, entities_layer

    def test_other_creature_error_is_not_leaked(self) -> None:
        """An NPC action with an error yields no `error` field in the player's message."""
        player, wolf, world, game_round, entities_layer = self._fixture()
        action = Action(name=ActionType.MOVE, params={"direction": "north", "ft": 5})

        msg = build_action_result(
            player, game_round, entities_layer, world, wolf, action, TurnBudget(), "Туда не пройти"
        )

        assert msg["actor"] == "w1"
        assert msg["action"] == action.name
        assert "error" not in msg
        assert "budget" not in msg

    def test_player_error_is_kept(self) -> None:
        """The player's own action error is preserved (the gate does not swallow player errors)."""
        player, _wolf, world, game_round, entities_layer = self._fixture()
        action = Action(name=ActionType.MOVE, params={"direction": "north", "ft": 5})

        msg = build_action_result(
            player, game_round, entities_layer, world, player, action, TurnBudget(), "Недостаточно ресурсов"
        )

        assert msg["actor"] == "p1"
        assert msg["error"] == "Недостаточно ресурсов"
        assert "budget" in msg
