"""EcologyLayer — tick-based squad movement, abstract combat, world ecology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, Query, QueryType
from dnd_simulator.core.squad import Squad

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta


class EcologyLayer(Layer):
    """Manages squads: movement, abstract combat, materialization coordination."""

    def __init__(self, squads: list[Squad] | None = None) -> None:
        self._squads: dict[str, Squad] = {}
        if squads:
            for s in squads:
                self._squads[s.id] = s

    @property
    def name(self) -> str:
        return "ecology"

    @property
    def tick_interval(self) -> int:
        return 3600  # 1 hour

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """Advance squad simulation. Movement logic added in Task 2."""
        return []

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """Process external events. Expanded in later tasks."""
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
            result: list[dict[str, Any]] = []
            for squad in self._squads.values():
                if squad.current_location_id == location_id:
                    result.append(self._squad_to_dict(squad))
            return Answer(value=result)

        if q is QueryType.SQUAD_INFO:
            squad_id = str(params["squad_id"])
            squad = self._squads[squad_id]  # KeyError if not found
            return Answer(value=self._squad_to_dict(squad))

        raise ValueError(f"Unknown ecology query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize mutable squad state (location, strength)."""
        squads: dict[str, dict[str, object]] = {}
        for sid, s in self._squads.items():
            squads[sid] = {
                "current_location_id": s.current_location_id,
                "strength": s.strength,
            }
        return {"squads": squads}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable squad fields from saved state."""
        squads_data = state["squads"]
        assert isinstance(squads_data, dict)
        for sid, sdata in squads_data.items():
            assert isinstance(sdata, dict)
            if sid in self._squads:
                self._squads[sid].current_location_id = str(sdata["current_location_id"])
                self._squads[sid].strength = int(sdata["strength"])

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
