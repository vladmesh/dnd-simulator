"""EcologyLayer — tick-based squad movement, abstract combat, world ecology.

The mechanics live in sibling submodules (``movement``, ``squad_combat``, ``lairs``); this
layer is the thin facade that ticks them and answers queries (politics-package pattern).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.core.queries import LairInfo, SquadInfo
from dnd_simulator.core.squad import Squad
from dnd_simulator.layers.ecology.lairs import apply_lair_dematerialize, respawn_lairs
from dnd_simulator.layers.ecology.movement import move_squad
from dnd_simulator.layers.ecology.squad_combat import resolve_squad_combat

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
            moved = move_squad(squad, self._route_index, self._route_direction, self._location_graph)
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
            apply_lair_dematerialize(self._lairs, event)
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
        squads: dict[str, dict[str, object]] = {}
        for sid, s in self._squads.items():
            squads[sid] = {
                "current_location_id": s.current_location_id,
                "strength": s.strength,
            }
        lairs: dict[str, dict[str, object]] = {}
        for lid, lair in self._lairs.items():
            lairs[lid] = {
                "state": lair.state.value,
                "alive_members": lair.alive_members,
                "core_alive": lair.core_alive,
                "last_respawn_time": lair.last_respawn_time,
            }
        return {
            "squads": squads,
            "lairs": lairs,
            "last_move_time": dict(self._last_move_time),
            "route_index": dict(self._route_index),
            "route_direction": dict(self._route_direction),
        }

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable squad fields from saved state."""
        squads_data = state["squads"]
        assert isinstance(squads_data, dict)
        for sid, sdata in squads_data.items():
            assert isinstance(sdata, dict)
            if sid in self._squads:
                self._squads[sid].current_location_id = str(sdata["current_location_id"])
                self._squads[sid].strength = int(sdata["strength"])

        lairs_data = state.get("lairs")
        if isinstance(lairs_data, dict):
            for lid, ldata in lairs_data.items():
                assert isinstance(ldata, dict)
                lair = self._lairs.get(str(lid))
                if lair is None:
                    continue
                lair.state = LairState(str(ldata["state"]))
                am = ldata.get("alive_members")
                lair.alive_members = [str(m) for m in am] if isinstance(am, list) else None
                lair.core_alive = bool(ldata.get("core_alive", True))
                lair.last_respawn_time = int(ldata.get("last_respawn_time", 0))

        lmt = state.get("last_move_time")
        if isinstance(lmt, dict):
            self._last_move_time = {str(k): int(v) for k, v in lmt.items()}

        ri = state.get("route_index")
        if isinstance(ri, dict):
            self._route_index = {str(k): int(v) for k, v in ri.items()}

        rd = state.get("route_direction")
        if isinstance(rd, dict):
            self._route_direction = {str(k): int(v) for k, v in rd.items()}

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
