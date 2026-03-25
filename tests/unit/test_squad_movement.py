"""Tests for squad movement and squad-vs-squad combat in EcologyLayer."""

from __future__ import annotations

from unittest.mock import patch

from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import Answer, EventType, GameDateTime, Query, QueryType, TimeDelta
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.layer import EcologyLayer


def _make_location(lid: str, edges: list[str]) -> Location:
    return Location(
        id=lid,
        name=lid,
        region_id="test_region",
        edges=tuple(LocationEdge(target_id=t, distance_m=1000) for t in edges),
    )


def _linear_graph() -> LocationGraph:
    """A -> B -> C (bidirectional)."""
    return LocationGraph(
        [
            _make_location("A", ["B"]),
            _make_location("B", ["A", "C"]),
            _make_location("C", ["B"]),
        ]
    )


def _make_squad(
    squad_id: str = "patrol_1",
    location: str = "A",
    faction: str = "kingdom",
    strength: int = 5,
    behavior: SquadBehavior = SquadBehavior.PATROL,
    route: list[str] | None = None,
    territory: list[str] | None = None,
    tick_interval: int = 3600,
    member_crs: list[float] | None = None,
) -> Squad:
    return Squad(
        id=squad_id,
        name=f"Squad {squad_id}",
        faction_id=faction,
        squad_type=SquadType.PATROL,
        behavior=behavior,
        current_location_id=location,
        route=route or ["A", "B", "C"],
        territory=territory or ["A", "B", "C"],
        strength=strength,
        max_strength=strength,
        member_templates=["bandit", "bandit"],
        tick_interval=tick_interval,
        member_crs=member_crs or [0.25, 0.25],
    )


def _no_query_fn(layer: str, query: Query) -> Answer:
    raise RuntimeError(f"Unexpected query to {layer}")


def _faction_query_fn(hostile_pairs: set[tuple[str, str]]) -> object:
    """Create a query_fn that answers FACTION_RELATION queries."""

    def query_fn(layer: str, query: Query) -> Answer:
        if layer == "politics" and query.question is QueryType.FACTION_RELATION:
            a, b = str(query.params["a"]), str(query.params["b"])
            key = (min(a, b), max(a, b))
            if key in hostile_pairs:
                return Answer(value="hostile")
            return Answer(value="neutral")
        raise RuntimeError(f"Unexpected query to {layer}: {query.question}")

    return query_fn


def _no_emit_fn(event: object) -> object:
    from dnd_simulator.core.models import ActionResult

    return ActionResult()


def _tick_layer(layer: EcologyLayer, seconds: int, hour: int = 1, query_fn: object = None) -> list[object]:
    """Convenience: tick the layer with given delta. Hour controls game time for tick_interval checks."""
    time = GameDateTime(year=1, month=1, day=1 + (hour // 24), hour=hour % 24)
    return layer.tick(
        TimeDelta(seconds=seconds),
        time,
        query_fn or _no_query_fn,  # type: ignore[arg-type]
        _no_emit_fn,  # type: ignore[arg-type]
    )


class TestPatrolMovement:
    """Patrol squad follows route and reverses at endpoints."""

    def test_patrol_follows_route_forward(self) -> None:
        squad = _make_squad("patrol_1", location="A", route=["A", "B", "C"])
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        _tick_layer(layer, seconds=3600, hour=1)
        assert squad.current_location_id == "B"

        _tick_layer(layer, seconds=3600, hour=2)
        assert squad.current_location_id == "C"

    def test_patrol_reverses_at_route_end(self) -> None:
        squad = _make_squad("patrol_1", location="A", route=["A", "B", "C"])
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        # A -> B -> C -> B
        _tick_layer(layer, seconds=3600, hour=1)
        assert squad.current_location_id == "B"

        _tick_layer(layer, seconds=3600, hour=2)
        assert squad.current_location_id == "C"

        _tick_layer(layer, seconds=3600, hour=3)
        assert squad.current_location_id == "B"


class TestRoamMovement:
    """Roam squad picks random neighbor within territory."""

    def test_roam_moves_within_territory(self) -> None:
        squad = _make_squad(
            "wolves_1",
            location="A",
            behavior=SquadBehavior.ROAM,
            territory=["A", "B"],
        )
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        with patch("dnd_simulator.layers.ecology.layer.random") as mock_random:
            mock_random.choice.return_value = "B"
            _tick_layer(layer, seconds=3600, hour=1)

        assert squad.current_location_id == "B"

    def test_roam_stays_if_no_territory_neighbor(self) -> None:
        """Squad at location with no neighbors in territory stays put."""
        # C only connects to B, but territory is [C, A] and A is not a neighbor of C
        squad = _make_squad(
            "wolves_1",
            location="C",
            behavior=SquadBehavior.ROAM,
            territory=["C", "A"],  # A is not a neighbor of C
        )
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        _tick_layer(layer, seconds=3600, hour=1)
        assert squad.current_location_id == "C"


class TestGuardMovement:
    """Guard squad never moves."""

    def test_guard_stays_at_location(self) -> None:
        squad = _make_squad("guard_1", location="B", behavior=SquadBehavior.GUARD)
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        for i in range(10):
            _tick_layer(layer, seconds=3600, hour=1 * (i + 1))

        assert squad.current_location_id == "B"


class TestSquadVsSquadCombat:
    """Hostile squads at same location fight via abstract combat."""

    def test_hostile_squads_fight_and_loser_retreats(self) -> None:
        strong = _make_squad(
            "strong",
            location="B",
            faction="kingdom",
            strength=6,
            behavior=SquadBehavior.GUARD,
            member_crs=[0.5, 0.5],
        )
        weak = _make_squad(
            "weak",
            location="B",
            faction="bandits",
            strength=2,
            behavior=SquadBehavior.GUARD,
            member_crs=[0.25, 0.25],
        )
        graph = _linear_graph()
        hostile_pairs = {("bandits", "kingdom")}
        qfn = _faction_query_fn(hostile_pairs)
        layer = EcologyLayer(squads=[strong, weak], location_graph=graph)

        events = _tick_layer(layer, seconds=3600, hour=1, query_fn=qfn)

        # Strong squad wins — stays at B. Weak loses — retreats to a neighbor.
        assert strong.current_location_id == "B"
        assert weak.current_location_id != "B"
        # Both lose some strength
        assert strong.strength < 6
        assert weak.strength < 2

        # Squad combat event emitted
        combat_events = [e for e in events if e.event_type is EventType.SQUAD_COMBAT]
        assert len(combat_events) >= 1

    def test_destroyed_squad_is_removed(self) -> None:
        strong = _make_squad(
            "strong",
            location="B",
            faction="kingdom",
            strength=6,
            behavior=SquadBehavior.GUARD,
            member_crs=[0.5, 0.5],
        )
        weak = _make_squad(
            "weak",
            location="B",
            faction="bandits",
            strength=1,
            behavior=SquadBehavior.GUARD,
            member_crs=[0.125],
        )
        graph = _linear_graph()
        hostile_pairs = {("bandits", "kingdom")}
        qfn = _faction_query_fn(hostile_pairs)
        layer = EcologyLayer(squads=[strong, weak], location_graph=graph)

        _tick_layer(layer, seconds=3600, hour=1, query_fn=qfn)

        # Weak squad should be destroyed (strength 0) and removed
        answer = layer.query(Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": "B"}))
        squad_ids = {s["id"] for s in answer.value}
        assert "strong" in squad_ids
        assert "weak" not in squad_ids


class TestMovementTickInterval:
    """Squad movement respects per-squad tick_interval."""

    def test_fast_squad_moves_before_slow_squad(self) -> None:
        fast = _make_squad("fast", location="A", tick_interval=3600, route=["A", "B", "C"])
        slow = _make_squad("slow", location="A", tick_interval=7200, route=["A", "B", "C"])
        graph = _linear_graph()
        layer = EcologyLayer(squads=[fast, slow], location_graph=graph)

        # After 3600s: fast moves, slow doesn't
        _tick_layer(layer, seconds=3600, hour=1)
        assert fast.current_location_id == "B"
        assert slow.current_location_id == "A"

        # After another 3600s (total 7200): fast moves again, slow moves for first time
        _tick_layer(layer, seconds=3600, hour=2)
        assert fast.current_location_id == "C"
        assert slow.current_location_id == "B"


class TestMovementEvents:
    """Squad movement emits events."""

    def test_movement_emits_squad_move_event(self) -> None:
        squad = _make_squad("patrol_1", location="A", route=["A", "B", "C"])
        graph = _linear_graph()
        layer = EcologyLayer(squads=[squad], location_graph=graph)

        events = _tick_layer(layer, seconds=3600, hour=1)

        move_events = [e for e in events if e.event_type is EventType.SQUAD_MOVE]
        assert len(move_events) == 1
        assert move_events[0].data["squad_id"] == "patrol_1"
        assert move_events[0].data["from"] == "A"
        assert move_events[0].data["to"] == "B"
