from __future__ import annotations

import dataclasses
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from dnd_simulator.core.action import Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Ability, Creature
from dnd_simulator.core.models import Query
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round, get_entities_layer

logger = logging.getLogger("dnd_simulator.session")


# ---------------------------------------------------------------------------
# Listener protocol — transports implement this to receive game events
# ---------------------------------------------------------------------------


class SessionEventListener(Protocol):
    """Protocol for receiving game events from a session.

    Transport layers (WS, CLI) implement this to bridge events to clients.
    All methods are called from the Round thread — implementations must
    handle thread-safety (e.g. asyncio.run_coroutine_threadsafe for async).
    """

    def on_turn(self, msg: dict[str, Any]) -> None: ...
    def on_action_result(self, msg: dict[str, Any]) -> None: ...
    def on_round_result(self, msg: dict[str, Any]) -> None: ...
    def on_game_over(self) -> None: ...


# ---------------------------------------------------------------------------
# Serialization helpers (game-level, not transport-specific)
# ---------------------------------------------------------------------------


def _awareness_to_dict(awareness: PeacefulAwareness | CombatAwareness) -> dict[str, Any]:
    return dataclasses.asdict(awareness)


def _events_to_list(events: list[PerceivedEvent]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for e in events:
        d = dataclasses.asdict(e)
        d["event_type"] = e.event_type.value
        result.append(d)
    return result


def _budget_to_dict(budget: TurnBudget) -> dict[str, Any]:
    return dataclasses.asdict(budget)


def _player_to_dict(player: PlayerCharacter) -> dict[str, Any]:
    scores = player.ability_scores
    return {
        "player_id": player.id,
        "name": player.name,
        "race": player.race.value,
        "char_class": player.char_class.value,
        "level": player.level,
        "alignment": player.alignment.value,
        "hp": player.current_hp,
        "max_hp": player.max_hp,
        "ac": player.ac,
        "gold": player.gold,
        "location_id": player.location_id,
        "ability_scores": {
            "str": scores[Ability.STR],
            "dex": scores[Ability.DEX],
            "con": scores[Ability.CON],
            "int": scores[Ability.INT],
            "wis": scores[Ability.WIS],
            "cha": scores[Ability.CHA],
        },
    }


def _location_data(world: World, location_id: str) -> dict[str, Any]:
    graph = world.location_graph
    if not graph.has(location_id):
        return {"current_location": location_id, "paths": []}

    loc = graph.get(location_id)
    paths = []
    for edge in loc.edges:
        target = graph.get(edge.target_id) if graph.has(edge.target_id) else None
        paths.append(
            {
                "target_id": edge.target_id,
                "target_name": target.name if target else edge.target_id,
                "distance_m": edge.distance_m,
            }
        )

    return {
        "current_location": loc.name,
        "current_location_id": loc.id,
        "description": loc.description,
        "region_id": loc.region_id,
        "paths": paths,
    }


# ---------------------------------------------------------------------------
# Move abstraction resolver (game logic, not transport)
# ---------------------------------------------------------------------------


def resolve_abstract_move(action: Action, player: Creature, entities_layer: EntitiesLayer) -> Action:
    """Translate toward/away_from into concrete direction + ft for a move action."""
    from dnd_simulator.rules.movement import calculate_away_direction, calculate_direction

    combat = entities_layer._combat.get_combat(player.location_id)
    if not combat:
        return action

    bm = combat.battle_map
    my_pos = bm.get_position(player.id)
    if my_pos is None:
        return action

    toward = action.params.get("toward")
    away_from = action.params.get("away_from")
    target_id = str(toward or away_from or "")
    target_pos = bm.get_position(target_id)
    if target_pos is None:
        return action

    if toward:
        direction = calculate_direction(my_pos, target_pos)
    else:
        direction = calculate_away_direction(my_pos, target_pos)

    ft = int(action.params.get("ft", 5))
    return Action(name="move", params={"direction": direction, "ft": ft})


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------


@dataclass
class GameSession:
    """An active game session.

    Owns the Round lifecycle: brain, round, thread.
    Transport layers register as listeners to receive events.
    """

    session_id: str
    world: World
    lang: str = "en"
    world_name: str = ""

    # Round lifecycle (managed, not serialized)
    _round: Round | None = field(default=None, init=False, repr=False)
    _round_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _player_brain: PlayerBrain | None = field(default=None, init=False, repr=False)
    _listeners: list[SessionEventListener] = field(default_factory=list, init=False, repr=False)
    _last_turn_msg: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ---------------------------------------------------------------------------
    # Player queries
    # ---------------------------------------------------------------------------

    def get_players(self) -> list[PlayerCharacter]:
        answer = self.world.query_layer("entities", Query(question="players", params={}))
        result = answer.value
        if isinstance(result, list):
            return result
        return []

    def get_player(self, player_id: str | None = None) -> PlayerCharacter | None:
        if player_id:
            answer = self.world.query_layer(
                "entities", Query(question="player", params={"id": player_id})
            )
            result = answer.value
            return result if isinstance(result, PlayerCharacter) else None
        players = self.get_players()
        return players[0] if players else None

    @property
    def player_location(self) -> str:
        player = self.get_player()
        return player.location_id if player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        player = self.get_player()
        if player:
            player.location_id = value

    # ---------------------------------------------------------------------------
    # Listener management
    # ---------------------------------------------------------------------------

    def add_listener(self, listener: SessionEventListener) -> None:
        with self._lock:
            self._listeners.append(listener)
            count = len(self._listeners)
        logger.info("[Session %s] add_listener: %d listeners", self.session_id, count)

    def get_last_turn_msg(self) -> dict[str, Any] | None:
        """Return the last turn message for replay by the caller."""
        return self._last_turn_msg

    def remove_listener(self, listener: SessionEventListener) -> None:
        stop_round = False
        with self._lock:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass
            count = len(self._listeners)
            if not self._listeners and self._round is not None:
                stop_round = True
        logger.info("[Session %s] remove_listener: %d listeners, stop_round=%s", self.session_id, count, stop_round)
        if stop_round:
            self.stop_round()

    def _fire(self, method: str, *args: Any) -> None:
        """Call a method on all listeners, swallowing individual errors."""
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                getattr(listener, method)(*args)
            except Exception:
                logger.exception("Listener %s.%s failed", type(listener).__name__, method)

    # ---------------------------------------------------------------------------
    # Round lifecycle
    # ---------------------------------------------------------------------------

    def start_round(self, player: PlayerCharacter) -> Round:
        """Start the round loop if not already running. Idempotent.

        Wires PlayerBrain, creates Round, starts background thread.
        Returns the Round (existing or new).
        """
        with self._lock:
            if self._round is not None and self._round_thread is not None and self._round_thread.is_alive():
                logger.info("[Session %s] start_round: round already running", self.session_id)
                return self._round
            logger.info("[Session %s] start_round: creating new round", self.session_id)

            brain = PlayerBrain()
            self._player_brain = brain

            entities_layer = get_entities_layer(self.world)

            # Wire on_turn: fires when Round calls brain.choose_action for the player
            def on_turn(
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> None:
                msg: dict[str, Any] = {
                    "type": "turn",
                    "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
                    "awareness": _awareness_to_dict(awareness),
                    "events": _events_to_list(events),
                    "player": _player_to_dict(player),
                    "location": _location_data(self.world, player.location_id),
                }
                if awareness.turn_budget is not None:
                    msg["budget"] = _budget_to_dict(awareness.turn_budget)
                self._last_turn_msg = msg
                self._fire("on_turn", msg)

            brain.set_on_turn(on_turn)
            player.brain = brain

            game_round = Round(self.world, entities_layer)

            # Wire on_action: fires after each action by any creature
            def on_action(creature: Creature, action: Action, budget: TurnBudget | None, error: str) -> None:
                self._last_turn_msg = None  # turn is being processed
                perceived = game_round.get_perceived_events(player)
                query_fn = self.world._make_query_fn("entities")
                awareness = entities_layer.build_awareness(player, self.world.time, query_fn)
                msg: dict[str, Any] = {
                    "type": "action_result",
                    "actor": creature.id,
                    "action": action.name,
                    "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
                    "awareness": _awareness_to_dict(awareness),
                    "events": _events_to_list(perceived),
                    "player": _player_to_dict(player),
                    "location": _location_data(self.world, player.location_id),
                }
                if error:
                    msg["error"] = error
                if budget is not None and creature.id == player.id:
                    msg["budget"] = _budget_to_dict(budget)
                self._fire("on_action_result", msg)

            game_round.set_on_action(on_action)

            # Wire on_round_end: fires after each complete round
            def on_round_end(result: object) -> None:
                perceived = game_round.get_perceived_events(player)
                query_fn = self.world._make_query_fn("entities")
                awareness = entities_layer.build_awareness(player, self.world.time, query_fn)
                msg: dict[str, Any] = {
                    "type": "round_result",
                    "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
                    "awareness": _awareness_to_dict(awareness),
                    "events": _events_to_list(perceived),
                    "player": _player_to_dict(player),
                    "location": _location_data(self.world, player.location_id),
                }
                self._fire("on_round_result", msg)

            game_round.set_on_round_end(on_round_end)

            self._round = game_round

            def run_round_loop() -> None:
                try:
                    game_round.run_loop()
                except Exception:
                    logger.exception("Round loop error in session %s", self.session_id)
                self._fire("on_game_over")

            thread = threading.Thread(
                target=run_round_loop, daemon=True, name=f"round-{self.session_id}"
            )
            self._round_thread = thread
            thread.start()

            return game_round

    def stop_round(self) -> None:
        """Stop the round loop and clean up."""
        logger.info("[Session %s] stop_round called", self.session_id)
        with self._lock:
            game_round = self._round
            brain = self._player_brain
            thread = self._round_thread
            self._round = None
            self._player_brain = None
            self._round_thread = None

        if game_round is not None:
            game_round.stop()
        if brain is not None:
            brain.submit_action(Action(name="end_turn"))  # unblock queue
        if thread is not None:
            thread.join(timeout=5)

    def submit_player_action(self, action: Action) -> None:
        """Submit a player action to the brain queue.

        Raises RuntimeError if round is not running.
        """
        brain = self._player_brain
        if brain is None:
            raise RuntimeError("Round not running — cannot submit action")

        # Resolve abstract move (toward/away_from) to concrete direction
        if action.name == "move" and ("toward" in action.params or "away_from" in action.params):
            player = self.get_player()
            if player is not None:
                entities_layer = get_entities_layer(self.world)
                action = resolve_abstract_move(action, player, entities_layer)

        brain.submit_action(action)

    @property
    def round_running(self) -> bool:
        return self._round_thread is not None and self._round_thread.is_alive()
