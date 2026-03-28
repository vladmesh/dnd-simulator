"""SettlementsLayer — cities, towns, and villages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.layers.settlements.models import Settlement, SettlementType
from dnd_simulator.rules.settlements import (
    calculate_harvest_modifier,
    calculate_population_change,
    calculate_settlement_income,
    clamp,
    conquest_effects,
    prosperity_drift,
)

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta


class SettlementsLayer(Layer):
    """Settlements simulation: population, prosperity, harvest, conquest effects."""

    def __init__(
        self,
        settlements: list[Settlement] | None = None,
        region_terrains: dict[str, str] | None = None,
    ) -> None:
        self._settlements: dict[str, Settlement] = {}
        if settlements:
            for s in settlements:
                self._settlements[s.id] = s
        self._region_terrains: dict[str, str] = region_terrains or {}

    @property
    def name(self) -> str:
        return "settlements"

    @property
    def tick_interval(self) -> int:
        return 2_592_000  # 30 days in seconds

    def get_settlement(self, settlement_id: str) -> Settlement:
        """Get a settlement by ID. Raises KeyError if not found."""
        if settlement_id not in self._settlements:
            raise KeyError(f"Settlement '{settlement_id}' not found")
        return self._settlements[settlement_id]

    def get_region_income(self, region_id: str) -> float:
        """Total income from all settlements in a region."""
        total = 0.0
        terrain = self._region_terrains.get(region_id, "plains")
        for s in self._settlements.values():
            if s.region_id == region_id:
                total += calculate_settlement_income(s.type.value, terrain, s.prosperity)
        return total

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """Process monthly settlement updates.

        World only calls this when tick_interval has elapsed,
        so delta covers at least one month.
        """
        months = max(1, delta.seconds // 2_592_000)
        events: list[Event] = []
        for _ in range(months):
            events.extend(self._monthly_tick(query_fn))
        return events

    def _monthly_tick(self, query_fn: QueryFn) -> list[Event]:
        """One month of settlement simulation."""
        events: list[Event] = []

        for settlement in self._settlements.values():
            # 1. Weather -> harvest -> prosperity
            weather_answer = query_fn(
                "geography", Query(question=QueryType.WEATHER, params={"region_id": settlement.region_id})
            )
            weather_val = weather_answer.value
            weather = str(weather_val.get("condition", "clear")) if isinstance(weather_val, dict) else "clear"

            harvest_mod = calculate_harvest_modifier(weather, settlement.type.value)
            settlement.prosperity = clamp(settlement.prosperity + harvest_mod)

            # 2. Nation wealth/stability -> prosperity drift
            owner_answer = query_fn(
                "politics", Query(question=QueryType.REGION_OWNER, params={"region_id": settlement.region_id})
            )
            owner_val = owner_answer.value
            if owner_val:
                nation_answer = query_fn(
                    "politics", Query(question=QueryType.NATION_INFO, params={"nation_id": str(owner_val)})
                )
                nation_val = nation_answer.value
                if isinstance(nation_val, dict):
                    drift = prosperity_drift(
                        settlement.prosperity,
                        float(nation_val.get("wealth", 50)),
                        float(nation_val.get("stability", 50)),
                    )
                    settlement.prosperity = clamp(settlement.prosperity + drift)

            # 3. Population change
            pop_change = calculate_population_change(settlement.population, settlement.prosperity)
            settlement.population = max(10, settlement.population + pop_change)

        return events

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """React to conquest events from politics layer."""
        if event.data.get("type") == "region_conquered":
            region_id = str(event.data["region"])
            return ActionResult(events=self._apply_conquest(region_id))
        return ActionResult()

    def _apply_conquest(self, region_id: str) -> list[Event]:
        """Apply conquest damage to all settlements in a region."""
        events: list[Event] = []

        for s in self._settlements.values():
            if s.region_id != region_id:
                continue

            prosperity_pen, defenses_pen, pop_loss_frac = conquest_effects(s.type.value)
            s.prosperity = clamp(s.prosperity + prosperity_pen)
            s.defenses = clamp(s.defenses + defenses_pen)
            pop_loss = int(s.population * pop_loss_frac)
            s.population = max(10, s.population - pop_loss)

            events.append(
                Event(
                    event_type=EventType.CUSTOM,
                    source_layer=self.name,
                    data={
                        "type": "settlement_damaged",
                        "settlement": s.id,
                        "region": region_id,
                    },
                    description=(
                        f"{s.name} suffers from the conquest (prosperity {s.prosperity:.0f}, pop {s.population})"
                    ),
                )
            )

        return events

    def query(self, query: Query) -> Answer:
        """Answer queries about settlements.

        Supported queries (see QueryType enum):
        - SETTLEMENTS: list all settlement IDs
        - SETTLEMENT_INFO: params={settlement_id} -> full settlement data
        - REGION_SETTLEMENTS: params={region_id} -> settlements in a region
        - REGION_INCOME: params={region_id} -> total income from settlements
        """
        q = query.question
        params = query.params

        if q is QueryType.SETTLEMENTS:
            return Answer(value=list(self._settlements.keys()))

        if q is QueryType.SETTLEMENT_INFO:
            s = self._settlements[params["settlement_id"]]
            return Answer(
                value={
                    "id": s.id,
                    "name": s.name,
                    "region_id": s.region_id,
                    "type": s.type.value,
                    "population": s.population,
                    "prosperity": s.prosperity,
                    "defenses": s.defenses,
                },
            )

        if q is QueryType.REGION_SETTLEMENTS:
            region_id = params["region_id"]
            result = []
            for s in self._settlements.values():
                if s.region_id == region_id:
                    result.append(
                        {
                            "id": s.id,
                            "name": s.name,
                            "region_id": s.region_id,
                            "type": s.type.value,
                            "population": s.population,
                            "prosperity": s.prosperity,
                            "defenses": s.defenses,
                        }
                    )
            return Answer(value=result)

        if q is QueryType.REGION_INCOME:
            return Answer(value=self.get_region_income(params["region_id"]))

        raise ValueError(f"Unknown settlements query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize settlements state."""
        settlements: dict[str, Any] = {}
        for sid, s in self._settlements.items():
            settlements[sid] = {
                "id": s.id,
                "name": s.name,
                "region_id": s.region_id,
                "type": s.type.value,
                "population": s.population,
                "prosperity": s.prosperity,
                "defenses": s.defenses,
            }
        return {"settlements": settlements}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore settlements from saved state."""
        settlements_data = state["settlements"]
        assert isinstance(settlements_data, dict)
        self._settlements.clear()

        for sid, sdata in settlements_data.items():
            assert isinstance(sdata, dict)
            self._settlements[str(sid)] = Settlement(
                id=str(sdata["id"]),
                name=str(sdata["name"]),
                region_id=str(sdata["region_id"]),
                type=SettlementType(str(sdata["type"])),
                population=int(sdata.get("population", 100)),
                prosperity=float(sdata.get("prosperity", 50.0)),
                defenses=float(sdata.get("defenses", 30.0)),
            )
