from __future__ import annotations

import contextlib
import contextvars
import os
import random
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from dnd_simulator.storage.save_schema import SaveGame

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.creature_host import CreatureHost
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.queries import query_player, query_players
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.i18n import language_context
from dnd_simulator.round import Round
from dnd_simulator.service.action_dispatcher import create_dispatcher
from dnd_simulator.service.transport_payloads import (
    _budget_to_dict,
    _reaction_to_dict,
    build_round_state,
    build_turn_state,
)

logger = structlog.get_logger(domain="session")

# Grace window before an emptied session is stopped + evicted. A disconnect+reconnect
# inside this window (StrictMode remount, network blip) cancels the evict. Configurable
# for ops/tests; overridable per-session via ``GameSession._evict_grace_seconds``.
_DEFAULT_EVICT_GRACE_SECONDS = float(os.getenv("DND_EVICT_GRACE_SECONDS", "1.5"))
_DEFAULT_ROUND_STOP_TIMEOUT_SECONDS = float(os.getenv("DND_ROUND_STOP_TIMEOUT_SECONDS", "5"))


class RoundStopTimeoutError(RuntimeError):
    """The session's round thread did not stop within its lifecycle deadline."""


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
    def on_reaction(self, msg: dict[str, Any]) -> None: ...
    def on_game_over(self) -> None: ...


# ---------------------------------------------------------------------------
# Move abstraction resolver (game logic, not transport)
# ---------------------------------------------------------------------------


def resolve_abstract_move(action: Action, player: Creature, creature_host: CreatureHost) -> Action:
    """Translate toward/away_from into a concrete direction + ft (host-aware compat wrapper).

    The resolution rule lives in ``rules.movement``; this wrapper looks up the player's
    active combat from the host and delegates.
    """
    from dnd_simulator.rules.movement import resolve_abstract_move as _resolve

    return _resolve(action, player, creature_host.get_combat(player.location_id))


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
    default_player_faction: str = ""
    dice_rng: random.Random = field(default_factory=random.Random, repr=False)

    # Round lifecycle (managed, not serialized)
    _round: Round | None = field(default=None, init=False, repr=False)
    _round_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _player_brain: PlayerBrain | None = field(default=None, init=False, repr=False)
    _listeners: list[SessionEventListener] = field(default_factory=list, init=False, repr=False)
    # Read-only observers (DM/admin/future spectators). Receive the broadcast, never drive
    # the round and never count toward the "session empty" lifecycle decision.
    _spectators: list[SessionEventListener] = field(default_factory=list, init=False, repr=False)
    _last_turn_msg: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _round_transition_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _world_state_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _on_empty: Callable[[GameSession], None] | None = field(default=None, init=False, repr=False)
    _evict_timer: threading.Timer | None = field(default=None, init=False, repr=False)
    _evict_grace_seconds: float = field(default=_DEFAULT_EVICT_GRACE_SECONDS, init=False, repr=False)
    _round_stop_timeout_seconds: float = field(default=_DEFAULT_ROUND_STOP_TIMEOUT_SECONDS, init=False, repr=False)

    # ---------------------------------------------------------------------------
    # Player queries
    # ---------------------------------------------------------------------------

    @contextlib.contextmanager
    def read_world(self) -> Iterator[None]:
        """Hold the session gate while reading a consistent world snapshot."""
        with self._world_state_lock:
            yield

    @contextlib.contextmanager
    def mutate_world(self) -> Iterator[None]:
        """Hold the re-entrant session gate while mutating world state."""
        with self._world_state_lock:
            yield

    def build_save_game(self) -> SaveGame:
        """Build an immutable save snapshot under the world-state gate."""
        from dnd_simulator.layers.common.rng_state import dump_rng_state
        from dnd_simulator.storage.save_schema import SCHEMA_VERSION, SaveGame, SaveMeta

        with self.read_world():
            world_data = self.world.save()
            world_data["dice_rng_state"] = dump_rng_state(self.dice_rng)
            return SaveGame.model_validate(
                {
                    "schema_version": SCHEMA_VERSION,
                    "meta": SaveMeta(
                        session_id=self.session_id,
                        world_name=self.world_name,
                        lang=self.lang,
                        default_player_faction=self.default_player_faction,
                    ).model_dump(mode="json"),
                    "world": world_data,
                }
            )

    def get_players(self) -> list[PlayerCharacter]:
        return query_players(self.world.query_layer)

    def get_player(self, player_id: str | None = None) -> PlayerCharacter | None:
        if player_id:
            return query_player(self.world.query_layer, player_id)
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

    def _bind_session_context(self) -> None:
        """Ensure session_id is bound in contextvars for all log calls."""
        structlog.contextvars.bind_contextvars(session_id=self.session_id)

    def has_player_listeners(self) -> bool:
        """Whether any player (round-driving) listener is connected.

        Single source of truth for the "session empty" decision: spectators are
        excluded, so a session watched only by spectators counts as empty. Lock-free
        read (atomic under the GIL); callers needing a consistent snapshot hold ``_lock``.
        """
        return bool(self._listeners)

    def add_listener(self, listener: SessionEventListener) -> None:
        self._bind_session_context()
        with self._round_transition_lock, self._lock:
            # Serialize listener arrival with disconnect-driven stop_round. Otherwise an
            # old connection can observe an empty listener list, a reconnect can start a
            # new round, and the old connection can then stop that new round.
            self._cancel_evict_check()
            self._listeners.append(listener)
            count = len(self._listeners)
        logger.info("add_listener", listener_count=count)

    def add_spectator(self, listener: SessionEventListener) -> None:
        """Register a read-only observer. Receives the broadcast; never drives lifecycle."""
        self._bind_session_context()
        with self._lock:
            self._spectators.append(listener)
            count = len(self._spectators)
        logger.info("add_spectator", spectator_count=count)

    def remove_spectator(self, listener: SessionEventListener) -> None:
        """Remove a read-only observer. Never stops the round, never fires ``_on_empty``."""
        self._bind_session_context()
        with self._lock:
            with contextlib.suppress(ValueError):
                self._spectators.remove(listener)
            count = len(self._spectators)
        logger.info("remove_spectator", spectator_count=count)

    def get_last_turn_msg(self) -> dict[str, Any] | None:
        """Return the last turn message for replay by the caller."""
        return self._last_turn_msg

    def remove_listener(self, listener: SessionEventListener) -> None:
        self._bind_session_context()
        player_empty = False
        with self._round_transition_lock:
            with self._lock:
                try:
                    self._listeners.remove(listener)
                except ValueError:
                    logger.info("remove_listener_ignored", listener_count=len(self._listeners))
                    return
                count = len(self._listeners)
                player_empty = not self.has_player_listeners()
                stop_round = player_empty and self._round is not None
            logger.info("remove_listener", listener_count=count, player_empty=player_empty, stop_round=stop_round)
            if stop_round:
                # Pause before a reconnect can enter add_listener/start_round.
                try:
                    self._stop_round()
                except RoundStopTimeoutError:
                    logger.exception("disconnect_stop_failed", session_id=self.session_id)
            if player_empty:
                # Arm eviction before allowing add_listener to enter; a reconnect then
                # cancels this exact timer while it starts the next round.
                with self._lock:
                    self._schedule_evict_check()

    def _schedule_evict_check(self) -> None:
        """Arm the deferred empty-session check. Caller holds ``_lock``."""
        if self._evict_timer is not None:
            self._evict_timer.cancel()
        timer = threading.Timer(self._evict_grace_seconds, self._run_evict_check)
        timer.daemon = True
        self._evict_timer = timer
        timer.start()

    def _cancel_evict_check(self) -> None:
        """Cancel any pending deferred evict. Caller holds ``_lock``."""
        if self._evict_timer is not None:
            self._evict_timer.cancel()
            self._evict_timer = None

    def _run_evict_check(self) -> None:
        """Timer callback: stop the round and fire ``_on_empty`` only if still player-empty.

        Runs on a Timer thread after the grace window. A reconnect inside the window
        adds a player and cancels this timer, so emptiness is re-verified under the lock.
        """
        self._bind_session_context()
        stop_round = False
        with self._lock:
            self._evict_timer = None
            if self.has_player_listeners():
                logger.info("evict_check_skipped_reconnected")
                return
            if self._round is not None:
                stop_round = True
        logger.info("evict_check_firing", stop_round=stop_round)
        if stop_round:
            try:
                self.stop_round()
            except RoundStopTimeoutError:
                logger.exception("evict_stop_failed", session_id=self.session_id)
                with self._lock:
                    if not self.has_player_listeners():
                        self._schedule_evict_check()
                return
        if self._on_empty is not None:
            self._on_empty(self)

    def _fire(self, method: str, *args: object) -> None:
        """Call a method on all listeners and spectators, swallowing individual errors."""
        with self._lock:
            listeners = self._listeners + self._spectators
        for listener in listeners:
            try:
                getattr(listener, method)(*args)
            except Exception:
                logger.exception("listener_error", listener=type(listener).__name__, method=method)

    # ---------------------------------------------------------------------------
    # Round lifecycle
    # ---------------------------------------------------------------------------

    def start_round(self, player: PlayerCharacter) -> Round:
        """Start or return the round while excluding load/stop transitions."""
        with self._round_transition_lock:
            return self._start_round(player)

    def _start_round(self, player: PlayerCharacter) -> Round:
        """Start the round loop if not already running. Idempotent.

        Wires PlayerBrain, creates Round, starts background thread.
        Returns the Round (existing or new).
        """
        self._bind_session_context()
        with self._lock:
            if self._round is not None and self._round_thread is not None and self._round_thread.is_alive():
                logger.info("start_round_already_running")
                return self._round
            logger.info("start_round_creating")

            brain = PlayerBrain()
            self._player_brain = brain

            creature_host = self.world.creature_host

            # Wire on_turn: fires when Round calls brain.choose_action for the player
            # Uses awareness from Round, which includes merchants and other live context.
            def on_turn(
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> None:
                with language_context(self.lang):
                    msg = build_turn_state(player, awareness, events, self.world)
                self._last_turn_msg = msg
                self._fire("on_turn", msg)

            brain.set_on_turn(on_turn)

            # Wire on_reaction: fires when Round calls brain.choose_reaction for the player
            def on_reaction(
                creature: Creature,
                trigger: ReactionTrigger,
                options: list[ReactionOption],
            ) -> None:
                msg = _reaction_to_dict(trigger, options)
                self._fire("on_reaction", msg)

            brain.set_on_reaction(on_reaction)
            player.brain = brain

            dispatcher = create_dispatcher(self.world)
            game_round = Round(
                self.world,
                creature_host,
                dispatcher=dispatcher,
                rng=self.dice_rng,
                mutation_scope=self.mutate_world,
            )

            # Wire on_action: fires after each action by any creature
            def on_action(creature: Creature, action: Action, budget: TurnBudget | None, error: str) -> None:
                self._last_turn_msg = None  # turn is being processed
                with language_context(self.lang):
                    msg = build_round_state("action_result", player, game_round, creature_host, self.world)
                msg["actor"] = creature.id
                msg["action"] = action.name
                if error:
                    msg["error"] = error
                if budget is not None and creature.id == player.id:
                    msg["budget"] = _budget_to_dict(budget)
                self._fire("on_action_result", msg)

            game_round.set_on_action(on_action)

            # Wire on_round_end: fires after each complete round
            def on_round_end(result: object) -> None:
                with language_context(self.lang):
                    msg = build_round_state("round_result", player, game_round, creature_host, self.world)
                self._fire("on_round_result", msg)

            game_round.set_on_round_end(on_round_end)

            self._round = game_round

            def run_round_loop() -> None:
                try:
                    game_round.run_loop()
                except Exception:
                    import traceback

                    logger.error("round_loop_error", traceback=traceback.format_exc())
                # Only signal game_over when the loop ended on its own (e.g. player death).
                # stop_round() sets the stop flag for administrative stops (last listener
                # disconnected); a transient disconnect+reconnect must not flash GAME OVER on
                # the reconnected client.
                if not game_round.is_stopped:
                    self._fire("on_game_over")

            # Copy contextvars (session_id etc.) into the round thread
            ctx = contextvars.copy_context()
            thread = threading.Thread(
                target=ctx.run, args=(run_round_loop,), daemon=True, name=f"round-{self.session_id}"
            )
            self._round_thread = thread
            thread.start()

            return game_round

    def stop_round(self, *, discard_events: bool = False) -> None:
        """Stop the round while excluding concurrent start/load transitions."""
        with self._round_transition_lock:
            self._stop_round(discard_events=discard_events)

    def _stop_round(self, *, discard_events: bool = False) -> None:
        """Stop the round loop within the deadline, then clean up its lifecycle snapshot."""
        self._bind_session_context()
        logger.info("stop_round")
        with self._lock:
            self._cancel_evict_check()
            game_round = self._round
            brain = self._player_brain
            thread = self._round_thread

        if game_round is not None:
            if discard_events:
                game_round.clear_callbacks()
            game_round.stop()
        if brain is not None:
            brain.submit_action(Action(name=ActionType.END_TURN))  # unblock queue
            brain.submit_reaction(Action(name=ActionType.SKIP))
        if thread is not None:
            thread.join(timeout=self._round_stop_timeout_seconds)
            if thread.is_alive():
                logger.error(
                    "stop_round_timeout",
                    session_id=self.session_id,
                    timeout_seconds=self._round_stop_timeout_seconds,
                    thread_name=thread.name,
                )
                raise RoundStopTimeoutError(
                    f"Round thread for session {self.session_id!r} did not stop within "
                    f"{self._round_stop_timeout_seconds:g} seconds"
                )

        with self._lock:
            if self._round is game_round:
                self._round = None
            if self._player_brain is brain:
                self._player_brain = None
            if self._round_thread is thread:
                self._round_thread = None

    def clear_cached_turn(self) -> None:
        """Discard transport state tied to the world that was just replaced."""
        self._last_turn_msg = None

    def replace_world_state(self, loader: Callable[[], None]) -> None:
        """Pause the round and atomically replace state before another start can win."""
        with self._round_transition_lock:
            self._stop_round(discard_events=True)
            self.clear_cached_turn()
            with self.mutate_world():
                loader()

    def submit_player_action(self, action: Action) -> None:
        """Submit a player action to the brain queue.

        Raises RuntimeError if round is not running.
        """
        brain = self._player_brain
        if brain is None:
            raise RuntimeError("Round not running — cannot submit action")

        # Resolve abstract move (toward/away_from) to concrete direction
        if action.name == ActionType.MOVE and ("toward" in action.params or "away_from" in action.params):
            player = self.get_player()
            if player is not None:
                creature_host = self.world.creature_host
                action = resolve_abstract_move(action, player, creature_host)

        brain.submit_action(action)

    def submit_player_reaction(self, action: Action) -> None:
        """Submit a player reaction to the brain queue.

        Raises RuntimeError if round is not running.
        """
        brain = self._player_brain
        if brain is None:
            raise RuntimeError("Round not running — cannot submit reaction")
        brain.submit_reaction(action)
