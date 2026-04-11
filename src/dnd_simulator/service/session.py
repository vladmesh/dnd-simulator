from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import get_action_def
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Ability, Creature
from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round, get_entities_layer
from dnd_simulator.rules.actions import collect_cost_overrides
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.service.action_dispatcher import create_dispatcher

logger = structlog.get_logger(domain="session")


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
# Serialization helpers (game-level, not transport-specific)
# ---------------------------------------------------------------------------


def _awareness_to_dict(
    awareness: PeacefulAwareness | CombatAwareness,
    creature: Creature | None = None,
) -> dict[str, Any]:
    d = dataclasses.asdict(awareness)
    # frozenset[Condition] → sorted list of strings for JSON serialization
    # frozenset[tuple[int, int]] → sorted list of [x, y] pairs for JSON serialization
    d["reachable"] = sorted([x, y] for x, y in awareness.reachable)

    if isinstance(awareness, CombatAwareness):
        d["self_conditions"] = sorted(c.value for c in awareness.self_conditions)
        for i, nearby_entry in enumerate(awareness.nearby):
            d["nearby"][i]["conditions"] = sorted(c.value for c in nearby_entry.conditions)
        # tuple[ResourcePoolInfo, ...] → list[dict] for JSON serialization
        d["self_resource_pools"] = [
            {"id": p.id, "max_uses": p.max_uses, "current_uses": p.current_uses} for p in awareness.self_resource_pools
        ]

    # Build structured action info with descriptions, params, and cost options
    overrides = collect_cost_overrides(creature) if creature else []
    actions_out: list[dict[str, Any]] = []
    for a in awareness.available_actions:
        ad = get_action_def(a)
        if ad.internal:
            continue
        action_info: dict[str, Any] = {
            "name": str(a),
            "description": _(ad.description),
            "cost_type": ad.cost_type.value,
            "params": [{"name": p.name, "type": p.param_type, "required": p.required} for p in ad.params],
        }
        # Include cost options if creature has overrides for this action
        action_overrides = [ov for ov in overrides if ov.action_type == a]
        if action_overrides:
            action_info["cost_options"] = [
                {"cost_type": ad.cost_type.value, "source": "default"},
                *[{"cost_type": ov.cost_type.value, "source": ov.source} for ov in action_overrides],
            ]
        actions_out.append(action_info)
    d["available_actions"] = actions_out
    return d


def _events_to_list(events: list[PerceivedEvent]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for e in events:
        d = dataclasses.asdict(e)
        d["event_type"] = e.event_type.value
        result.append(d)
    return result


def _budget_to_dict(budget: TurnBudget) -> dict[str, Any]:
    return dataclasses.asdict(budget)


def _reaction_to_dict(trigger: ReactionTrigger, options: list[ReactionOption]) -> dict[str, Any]:
    """Build the reaction_prompt message sent to the client."""
    return {
        "type": "reaction_prompt",
        "trigger": {
            "trigger_type": trigger.trigger_type.value,
            "source_creature_id": trigger.source_creature_id,
            "data": {k: v for k, v in trigger.data.items()},
        },
        "options": [
            {
                "action_type": opt.action_type.value,
                "description": opt.description,
                "params": {k: v for k, v in opt.params.items()},
            }
            for opt in options
        ],
    }


def _player_to_dict(player: PlayerCharacter) -> dict[str, Any]:
    from dnd_simulator.core.awareness import describe_item
    from dnd_simulator.round import Round

    scores = player.ability_scores
    equipped = [
        {"slot": e.slot.value, "item_id": e.item_id, "name": e.name, "description": e.description}
        for e in Round._build_equipped(player)
    ]
    inventory = []
    for item in player.inventory:
        entry: dict[str, object] = {
            "id": item.id,
            "name": item.name,
            "type": item.item_type.value,
            "description": describe_item(item),
            "price": item.price,
        }
        if item.accessory_def is not None:
            entry["slot"] = item.accessory_def.slot.value
        inventory.append(entry)
    return {
        "player_id": player.id,
        "name": player.name,
        "race": player.race.value,
        "char_class": player.char_class.value,
        "level": player.level,
        "alignment": player.alignment.value,
        "hp": player.current_hp,
        "max_hp": player.max_hp,
        "ac": effective_ac(player),
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
        "equipped": equipped,
        "inventory": inventory,
        "resource_pools": [
            {"id": p.id, "max_uses": p.max_uses, "current_uses": p.current_uses} for p in player.resource_pools
        ],
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

    direction = calculate_direction(my_pos, target_pos) if toward else calculate_away_direction(my_pos, target_pos)

    ft = int(str(action.params.get("ft", 5)))
    return Action(name=ActionType.MOVE, params={"direction": direction, "ft": ft})


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

    # Round lifecycle (managed, not serialized)
    _round: Round | None = field(default=None, init=False, repr=False)
    _round_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _player_brain: PlayerBrain | None = field(default=None, init=False, repr=False)
    _listeners: list[SessionEventListener] = field(default_factory=list, init=False, repr=False)
    _last_turn_msg: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _on_empty: Callable[[GameSession], None] | None = field(default=None, init=False, repr=False)

    # ---------------------------------------------------------------------------
    # Player queries
    # ---------------------------------------------------------------------------

    def get_players(self) -> list[PlayerCharacter]:
        answer = self.world.query_layer("entities", Query(question=QueryType.PLAYERS, params={}))
        result = answer.value
        if isinstance(result, list):
            return result
        return []

    def get_player(self, player_id: str | None = None) -> PlayerCharacter | None:
        if player_id:
            answer = self.world.query_layer("entities", Query(question=QueryType.PLAYER, params={"id": player_id}))
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

    def _bind_session_context(self) -> None:
        """Ensure session_id is bound in contextvars for all log calls."""
        structlog.contextvars.bind_contextvars(session_id=self.session_id)

    def add_listener(self, listener: SessionEventListener) -> None:
        self._bind_session_context()
        with self._lock:
            self._listeners.append(listener)
            count = len(self._listeners)
        logger.info("add_listener", listener_count=count)

    def get_last_turn_msg(self) -> dict[str, Any] | None:
        """Return the last turn message for replay by the caller."""
        return self._last_turn_msg

    def remove_listener(self, listener: SessionEventListener) -> None:
        self._bind_session_context()
        stop_round = False
        is_empty = False
        with self._lock:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)
            count = len(self._listeners)
            if not self._listeners:
                is_empty = True
                if self._round is not None:
                    stop_round = True
        logger.info("remove_listener", listener_count=count, stop_round=stop_round)
        if stop_round:
            self.stop_round()
        if is_empty and self._on_empty is not None:
            self._on_empty(self)

    def _fire(self, method: str, *args: object) -> None:
        """Call a method on all listeners, swallowing individual errors."""
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                getattr(listener, method)(*args)
            except Exception:
                logger.exception("listener_error", listener=type(listener).__name__, method=method)

    # ---------------------------------------------------------------------------
    # Shared state builder for round callbacks
    # ---------------------------------------------------------------------------

    def _build_round_state(
        self,
        msg_type: str,
        player: PlayerCharacter,
        game_round: Round,
        entities_layer: EntitiesLayer,
    ) -> dict[str, Any]:
        """Build the common state dict shared by on_turn, on_action, and on_round_end."""
        perceived = game_round.get_perceived_events(player)
        query_fn = self.world._make_query_fn("entities")
        awareness = entities_layer.build_awareness(player, self.world.time, query_fn)
        return {
            "type": msg_type,
            "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
            "awareness": _awareness_to_dict(awareness, creature=player),
            "events": _events_to_list(perceived),
            "player": _player_to_dict(player),
            "location": _location_data(self.world, player.location_id),
        }

    # ---------------------------------------------------------------------------
    # Round lifecycle
    # ---------------------------------------------------------------------------

    def start_round(self, player: PlayerCharacter) -> Round:
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

            entities_layer = get_entities_layer(self.world)

            # Wire on_turn: fires when Round calls brain.choose_action for the player
            # Uses awareness from Round (which includes merchants, etc.) — not _build_round_state
            def on_turn(
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> None:
                msg: dict[str, Any] = {
                    "type": "turn",
                    "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
                    "awareness": _awareness_to_dict(awareness, creature=creature),
                    "events": _events_to_list(events),
                    "player": _player_to_dict(player),
                    "location": _location_data(self.world, player.location_id),
                }
                if awareness.turn_budget is not None:
                    msg["budget"] = _budget_to_dict(awareness.turn_budget)
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
            game_round = Round(self.world, entities_layer, dispatcher=dispatcher)

            # Wire on_action: fires after each action by any creature
            def on_action(creature: Creature, action: Action, budget: TurnBudget | None, error: str) -> None:
                self._last_turn_msg = None  # turn is being processed
                msg = self._build_round_state("action_result", player, game_round, entities_layer)
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
                msg = self._build_round_state("round_result", player, game_round, entities_layer)
                self._fire("on_round_result", msg)

            game_round.set_on_round_end(on_round_end)

            self._round = game_round

            def run_round_loop() -> None:
                try:
                    game_round.run_loop()
                except Exception:
                    import traceback

                    logger.error("round_loop_error", traceback=traceback.format_exc())
                self._fire("on_game_over")

            # Copy contextvars (session_id etc.) into the round thread
            ctx = contextvars.copy_context()
            thread = threading.Thread(
                target=ctx.run, args=(run_round_loop,), daemon=True, name=f"round-{self.session_id}"
            )
            self._round_thread = thread
            thread.start()

            return game_round

    def stop_round(self) -> None:
        """Stop the round loop and clean up."""
        self._bind_session_context()
        logger.info("stop_round")
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
            brain.submit_action(Action(name=ActionType.END_TURN))  # unblock queue
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
        if action.name == ActionType.MOVE and ("toward" in action.params or "away_from" in action.params):
            player = self.get_player()
            if player is not None:
                entities_layer = get_entities_layer(self.world)
                action = resolve_abstract_move(action, player, entities_layer)

        brain.submit_action(action)

    def submit_player_reaction(self, action: Action) -> None:
        """Submit a player reaction to the brain queue.

        Raises RuntimeError if round is not running.
        """
        brain = self._player_brain
        if brain is None:
            raise RuntimeError("Round not running — cannot submit reaction")
        brain.submit_reaction(action)
