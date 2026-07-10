"""EcologyLayer — tick-based squad movement, abstract combat, world ecology.

The mechanics live in sibling submodules (``movement``, ``squad_combat``, ``lairs``); this
layer is the thin facade that ticks them and answers queries (politics-package pattern).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.lair import Lair
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.core.queries import LairInfo, SquadInfo
from dnd_simulator.core.squad import Squad
from dnd_simulator.layers.common.rng_state import dump_rng_state, load_rng_state
from dnd_simulator.layers.ecology.lairs import apply_lair_dematerialize, respawn_lairs
from dnd_simulator.layers.ecology.movement import move_squad
from dnd_simulator.layers.ecology.squad_combat import resolve_squad_combat
from dnd_simulator.layers.ecology.state import EcologyState, LairRuntimeState, SquadRuntimeState

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta

logger = structlog.get_logger(domain="ecology")


class EcologyLayer(Layer):
    """Manages squads: movement, abstract combat, materialization coordination."""

    def __init__(
        self,
        squads: list[Squad] | None = None,
        location_graph: LocationGraph | None = None,
        lairs: list[Lair] | None = None,
        seed: int | None = None,
    ) -> None:
        self._squads: dict[str, Squad] = {}
        if squads:
            for s in squads:
                self._squads[s.id] = s
        self._lairs: dict[str, Lair] = {}
        if lairs:
            for lair in lairs:
                self._lairs[lair.id] = lair
        self._location_graph = location_graph
        self._last_move_time: dict[str, int] = {}  # squad_id → game-time seconds of last move
        self._route_index: dict[str, int] = {}  # squad_id → current index in route
        self._route_direction: dict[str, int] = {}  # squad_id → +1 forward, -1 reverse
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "ecology"

    @property
    def tick_interval(self) -> int:
        return 3600  # 1 hour

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """Move squads and resolve squad-vs-squad combat."""
        now = time.to_total_seconds()
        events: list[Event] = []
        logger.debug("ecology_tick", squad_count=len(self._squads), delta_seconds=delta.seconds)

        # Phase 1: Move squads
        for squad in list(self._squads.values()):
            last = self._last_move_time.get(squad.id, 0)
            if now - last < squad.tick_interval:
                logger.debug("squad_skip", squad_id=squad.id, cooldown_remaining=squad.tick_interval - (now - last))
                continue
            moved = move_squad(squad, self._route_index, self._route_direction, self._location_graph, self._rng)
            logger.info(
                "squad_tick",
                squad_id=squad.id,
                squad_name=squad.name,
                location=squad.current_location_id,
                moved=moved is not None,
                moved_to=moved[1] if moved else None,
            )
            if moved:
                events.append(
                    Event(
                        event_type=EventType.SQUAD_MOVE,
                        source_layer=self.name,
                        data={
                            "squad_id": squad.id,
                            "squad_name": squad.name,
                            "from": moved[0],
                            "to": moved[1],
                        },
                        description=f"{squad.name} moved from {moved[0]} to {moved[1]}",
                    )
                )
            self._last_move_time[squad.id] = now

        # Phase 2: Resolve squad-vs-squad combat at shared locations
        events.extend(
            resolve_squad_combat(
                self._squads,
                self._location_graph,
                self._last_move_time,
                self._route_index,
                self._route_direction,
                query_fn,
                self._rng,
            )
        )

        # Phase 3: Respawn lair populations
        respawn_lairs(self._lairs, now)

        if events:
            logger.info(
                "ecology_tick_summary",
                tick_events=len(events),
                squads={
                    s.id: {"location": s.current_location_id, "strength": s.strength} for s in self._squads.values()
                },
            )

        return events

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """Process external events."""
        if event.event_type is EventType.SQUAD_DEMATERIALIZED:
            squad_id = str(event.data["squad_id"])
            new_strength = int(event.data["new_strength"])
            if squad_id in self._squads:
                self._squads[squad_id].strength = new_strength
                logger.info("squad_strength_updated", squad_id=squad_id, new_strength=new_strength)
        elif event.event_type is EventType.LAIR_DEMATERIALIZED:
            apply_lair_dematerialize(self._lairs, event, self._rng)
        return ActionResult()

    def query(self, query: Query) -> Answer:
        """Answer queries about squads.

        Supported queries:
        - SQUADS_AT_LOCATION: params={location_id} -> list of squad dicts at that location
        - SQUAD_INFO: params={squad_id} -> full squad data dict
        """
        q = query.question
        params = query.params

        if q is QueryType.SQUADS_AT_LOCATION:
            location_id = str(params["location_id"])
            result = [
                self._squad_info(squad) for squad in self._squads.values() if squad.current_location_id == location_id
            ]
            return Answer(value=result)

        if q is QueryType.SQUAD_INFO:
            squad_id = str(params["squad_id"])
            squad = self._squads[squad_id]  # KeyError if not found
            return Answer(value=self._squad_info(squad))

        if q is QueryType.LAIRS_AT_LOCATION:
            location_id = str(params["location_id"])
            lairs = [self._lair_info(lair) for lair in self._lairs.values() if lair.location_id == location_id]
            return Answer(value=lairs)

        raise ValueError(f"Unknown ecology query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize mutable squad state."""
        state = EcologyState(
            squads={
                sid: SquadRuntimeState(current_location_id=s.current_location_id, strength=s.strength)
                for sid, s in self._squads.items()
            },
            lairs={
                lid: LairRuntimeState(
                    state=lair.state,
                    alive_members=lair.alive_members,
                    core_alive=lair.core_alive,
                    last_respawn_time=lair.last_respawn_time,
                )
                for lid, lair in self._lairs.items()
            },
            last_move_time=dict(self._last_move_time),
            route_index=dict(self._route_index),
            route_direction=dict(self._route_direction),
            rng_state=dump_rng_state(self._rng),
        )
        return state.model_dump(mode="json")

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable squad fields from saved state."""
        data = EcologyState.model_validate(state)
        load_rng_state(self._rng, data.rng_state)

        for sid, sdata in data.squads.items():
            if sid in self._squads:
                self._squads[sid].current_location_id = sdata.current_location_id
                self._squads[sid].strength = sdata.strength

        for lid, ldata in data.lairs.items():
            lair = self._lairs.get(lid)
            if lair is None:
                continue
            lair.state = ldata.state
            lair.alive_members = ldata.alive_members
            lair.core_alive = ldata.core_alive
            lair.last_respawn_time = ldata.last_respawn_time

        self._last_move_time = dict(data.last_move_time)
        self._route_index = dict(data.route_index)
        self._route_direction = dict(data.route_direction)

    @staticmethod
    def _squad_info(squad: Squad) -> SquadInfo:
        return SquadInfo(
            id=squad.id,
            name=squad.name,
            faction_id=squad.faction_id,
            squad_type=squad.squad_type,
            behavior=squad.behavior,
            current_location_id=squad.current_location_id,
            strength=squad.strength,
            max_strength=squad.max_strength,
            member_templates=tuple(squad.member_templates),
        )

    @staticmethod
    def _lair_info(lair: Lair) -> LairInfo:
        """Materialization view: current alive roster, not the full template list.

        Treasury fields are in-memory only — consumed by ActivationManager, never serialized.
        """
        current_minions = tuple(lair.alive_members) if lair.alive_members is not None else tuple(lair.members)
        return LairInfo(
            id=lair.id,
            name=lair.name,
            faction_id=lair.faction_id,
            location_id=lair.location_id,
            members=current_minions,
            core=lair.core if lair.core_alive else None,
            state=lair.state,
            has_core=lair.core is not None,
            core_alive=lair.core_alive,
            treasure_items=tuple(lair.treasure_items),
            treasure_gold=lair.treasure_gold,
            treasure_behind_core=lair.treasure_behind_core,
        )
