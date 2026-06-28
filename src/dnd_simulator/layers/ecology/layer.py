"""EcologyLayer — tick-based squad movement, abstract combat, world ecology."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.core.squad import Squad, SquadBehavior
from dnd_simulator.rules.abstract_combat import TriggeredEncounter, resolve_abstract_combat
from dnd_simulator.rules.dice import get_global_rng

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta

logger = structlog.get_logger(domain="ecology")

# Behaviors that follow a fixed route
_ROUTE_BEHAVIORS = {SquadBehavior.PATROL, SquadBehavior.TRADE}

# Behaviors that roam randomly within territory
_ROAM_BEHAVIORS = {SquadBehavior.ROAM, SquadBehavior.HUNT, SquadBehavior.RAID}


class EcologyLayer(Layer):
    """Manages squads: movement, abstract combat, materialization coordination."""

    def __init__(
        self,
        squads: list[Squad] | None = None,
        location_graph: LocationGraph | None = None,
        lairs: list[Lair] | None = None,
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
            moved = self._move_squad(squad)
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
        events.extend(self._resolve_squad_combat(query_fn))

        # Phase 3: Respawn lair populations
        self._respawn_lairs(now)

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
            self._apply_lair_dematerialize(event)
        return ActionResult()

    def _apply_lair_dematerialize(self, event: Event) -> None:
        """Sync a lair's surviving population from a finished visit."""
        lair_id = str(event.data["lair_id"])
        lair = self._lairs.get(lair_id)
        if lair is None:
            return
        alive_members = event.data.get("alive_members")
        lair.alive_members = [str(m) for m in alive_members] if isinstance(alive_members, list) else []
        lair.core_alive = bool(event.data.get("core_alive", lair.core_alive))
        # Anchor the respawn countdown to this visit so respawn waits a full interval afterwards.
        lair.last_respawn_time = int(event.data.get("at_seconds", lair.last_respawn_time))

        # Depletion: a cored lair dies permanently when its core dies; a coreless lair
        # may run dry by chance after a full wipe (roll only when wiped, via short-circuit).
        core_died = lair.core is not None and not lair.core_alive
        chance_ran_dry = (
            lair.core is None
            and not lair.alive_members
            and lair.depletion_chance > 0.0
            and get_global_rng().random() < lair.depletion_chance
        )
        if core_died or chance_ran_dry:
            lair.state = LairState.DEPLETED

        logger.info(
            "lair_population_updated",
            lair_id=lair_id,
            alive_members=len(lair.alive_members),
            core_alive=lair.core_alive,
            state=lair.state.value,
        )

    def _respawn_lairs(self, now: int) -> None:
        """Refill ACTIVE lairs to their full roster once respawn_interval has elapsed since the last visit."""
        for lair in self._lairs.values():
            if lair.state is not LairState.ACTIVE:
                continue
            if lair.alive_members is None or len(lair.alive_members) >= len(lair.members):
                continue  # already at full roster
            if now - lair.last_respawn_time < lair.respawn_interval:
                continue
            lair.alive_members = None  # back to full roster
            lair.last_respawn_time = now
            logger.info("lair_respawn", lair_id=lair.id)

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
            result: list[dict[str, Any]] = []
            for squad in self._squads.values():
                if squad.current_location_id == location_id:
                    result.append(self._squad_to_dict(squad))
            return Answer(value=result)

        if q is QueryType.SQUAD_INFO:
            squad_id = str(params["squad_id"])
            squad = self._squads[squad_id]  # KeyError if not found
            return Answer(value=self._squad_to_dict(squad))

        if q is QueryType.LAIRS_AT_LOCATION:
            location_id = str(params["location_id"])
            lairs = [self._lair_to_dict(lair) for lair in self._lairs.values() if lair.location_id == location_id]
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

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def _move_squad(self, squad: Squad) -> tuple[str, str] | None:
        """Move a squad according to its behavior. Returns (from, to) or None if no move."""
        if squad.behavior is SquadBehavior.GUARD:
            return None

        if squad.behavior in _ROUTE_BEHAVIORS:
            return self._move_route(squad)

        if squad.behavior in _ROAM_BEHAVIORS:
            return self._move_roam(squad)

        return None

    def _move_route(self, squad: Squad) -> tuple[str, str] | None:
        """Move along route, reversing at endpoints."""
        if not squad.route:
            return None

        # Initialize route tracking
        if squad.id not in self._route_index:
            try:
                self._route_index[squad.id] = squad.route.index(squad.current_location_id)
            except ValueError:
                self._route_index[squad.id] = 0
            self._route_direction[squad.id] = 1

        idx = self._route_index[squad.id]
        direction = self._route_direction[squad.id]
        next_idx = idx + direction

        # Reverse at endpoints
        if next_idx < 0 or next_idx >= len(squad.route):
            direction = -direction
            self._route_direction[squad.id] = direction
            next_idx = idx + direction

        if next_idx < 0 or next_idx >= len(squad.route):
            return None  # single-location route

        old = squad.current_location_id
        self._route_index[squad.id] = next_idx
        squad.current_location_id = squad.route[next_idx]
        return (old, squad.current_location_id)

    def _move_roam(self, squad: Squad) -> tuple[str, str] | None:
        """Move to a random neighbor within territory."""
        if self._location_graph is None:
            return None

        edges = self._location_graph.neighbors(squad.current_location_id)
        candidates = [e.target_id for e in edges if e.target_id in squad.territory]
        if not candidates:
            return None

        old = squad.current_location_id
        squad.current_location_id = random.choice(candidates)
        return (old, squad.current_location_id)

    # ------------------------------------------------------------------
    # Squad-vs-squad combat
    # ------------------------------------------------------------------

    def _resolve_squad_combat(self, query_fn: QueryFn) -> list[Event]:
        """Find hostile squads at same location and resolve combat."""
        events: list[Event] = []

        # Group squads by location
        by_location: dict[str, list[Squad]] = defaultdict(list)
        for squad in self._squads.values():
            by_location[squad.current_location_id].append(squad)

        # Check each location with multiple squads
        fought: set[str] = set()
        for location_id, squads in by_location.items():
            if len(squads) < 2:
                continue

            for i, a in enumerate(squads):
                if a.id in fought:
                    continue
                for b in squads[i + 1 :]:
                    if b.id in fought:
                        continue
                    if not self._are_hostile(a, b, query_fn):
                        continue

                    event = self._fight_squads(a, b, location_id)
                    events.append(event)
                    fought.add(a.id)
                    fought.add(b.id)
                    break  # each squad fights at most once per tick

        # Remove destroyed squads
        destroyed = [sid for sid, s in self._squads.items() if s.strength <= 0]
        for sid in destroyed:
            logger.info("squad_destroyed", squad_id=sid)
            del self._squads[sid]
            self._last_move_time.pop(sid, None)
            self._route_index.pop(sid, None)
            self._route_direction.pop(sid, None)

        return events

    def _are_hostile(self, a: Squad, b: Squad, query_fn: QueryFn) -> bool:
        """Check if two squads are hostile via faction relations."""
        if a.faction_id == b.faction_id:
            return False
        answer = query_fn(
            "politics",
            Query(QueryType.FACTION_RELATION, params={"a": a.faction_id, "b": b.faction_id}),
        )
        return answer.value == FactionRelation.HOSTILE

    def _fight_squads(self, a: Squad, b: Squad, location_id: str) -> Event:
        """Resolve combat between two squads. Loser retreats."""
        # Model squad B as encounters for squad A
        b_encounters = [TriggeredEncounter(cr=cr, count=1) for cr in b.member_crs] if b.member_crs else []
        a_encounters = [TriggeredEncounter(cr=cr, count=1) for cr in a.member_crs] if a.member_crs else []

        result_a = resolve_abstract_combat(a.strength, b_encounters)
        result_b = resolve_abstract_combat(b.strength, a_encounters)

        a.strength = max(0, a.strength - result_a.strength_lost)
        b.strength = max(0, b.strength - result_b.strength_lost)

        # Determine winner/loser
        if result_a.won:
            winner, loser = a, b
        else:
            winner, loser = b, a

        # Loser retreats to a random neighbor (if alive and graph available)
        if loser.strength > 0 and self._location_graph is not None:
            edges = self._location_graph.neighbors(location_id)
            if edges:
                loser.current_location_id = random.choice(edges).target_id

        logger.info(
            "squad_combat",
            winner=winner.id,
            loser=loser.id,
            winner_strength=winner.strength,
            loser_strength=loser.strength,
        )

        return Event(
            event_type=EventType.SQUAD_COMBAT,
            source_layer=self.name,
            data={
                "location_id": location_id,
                "winner_id": winner.id,
                "winner_name": winner.name,
                "loser_id": loser.id,
                "loser_name": loser.name,
                "winner_strength": winner.strength,
                "loser_strength": loser.strength,
            },
            description=f"{winner.name} defeated {loser.name} at {location_id}",
        )

    @staticmethod
    def _squad_to_dict(squad: Squad) -> dict[str, Any]:
        return {
            "id": squad.id,
            "name": squad.name,
            "faction_id": squad.faction_id,
            "squad_type": squad.squad_type.value,
            "behavior": squad.behavior.value,
            "current_location_id": squad.current_location_id,
            "strength": squad.strength,
            "max_strength": squad.max_strength,
            "member_templates": list(squad.member_templates),
        }

    @staticmethod
    def _lair_to_dict(lair: Lair) -> dict[str, Any]:
        """Materialization view: current alive roster, not the full template list."""
        current_minions = list(lair.alive_members) if lair.alive_members is not None else list(lair.members)
        return {
            "id": lair.id,
            "name": lair.name,
            "faction_id": lair.faction_id,
            "location_id": lair.location_id,
            "members": current_minions,
            "core": lair.core if lair.core_alive else None,
            "state": lair.state.value,
        }
