"""SettlementsLayer — cities, towns, and villages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
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
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState


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

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Process monthly settlement updates.

        World only calls this when tick_interval has elapsed,
        so delta covers at least one month.
        """
        months = max(1, delta.seconds // 2_592_000)
        events: list[Event] = []
        for _ in range(months):
            events.extend(self._monthly_tick(world_state))
        return events

    def _monthly_tick(self, world_state: WorldState) -> list[Event]:
        """One month of settlement simulation."""
        events: list[Event] = []

        # Extract geography state for weather
        geo_state = world_state.layer_states.get("geography", {})
        regions_data = geo_state.get("regions", {})
        assert isinstance(regions_data, dict)

        # Extract politics state for nation wealth/stability
        pol_state = world_state.layer_states.get("politics", {})
        nations_data = pol_state.get("nations", {})
        assert isinstance(nations_data, dict)

        # Build region -> nation data lookup
        region_to_nation = self._build_region_nation_map(nations_data)

        for settlement in self._settlements.values():
            # 1. Weather -> harvest -> prosperity
            region_data = regions_data.get(settlement.region_id, {})
            assert isinstance(region_data, dict)
            weather = str(region_data.get("weather", "clear"))

            harvest_mod = calculate_harvest_modifier(weather, settlement.type.value)
            settlement.prosperity = clamp(settlement.prosperity + harvest_mod)

            # 2. Nation wealth/stability -> prosperity drift
            nation_data = region_to_nation.get(settlement.region_id)
            if nation_data:
                drift = prosperity_drift(
                    settlement.prosperity,
                    float(nation_data.get("wealth", 50)),
                    float(nation_data.get("stability", 50)),
                )
                settlement.prosperity = clamp(settlement.prosperity + drift)

            # 3. Population change
            pop_change = calculate_population_change(settlement.population, settlement.prosperity)
            settlement.population = max(10, settlement.population + pop_change)

        return events

    def _build_region_nation_map(self, nations_data: dict[str, object]) -> dict[str, dict[str, Any]]:
        """Map region_id -> nation data dict."""
        result: dict[str, dict[str, Any]] = {}
        for _nid, ndata in nations_data.items():
            assert isinstance(ndata, dict)
            regions = ndata.get("regions", [])
            assert isinstance(regions, list)
            for rid in regions:
                result[str(rid)] = ndata
        return result

    def handle_event(self, event: Event) -> ActionResult:
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

        Supported queries:
        - "settlements": list all settlement IDs
        - "settlement_info": params={settlement_id} -> full settlement data
        - "region_settlements": params={region_id} -> settlements in a region
        - "region_income": params={region_id} -> total income from settlements
        """
        q = query.question
        params = query.params

        if q == "settlements":
            return Answer(value=list(self._settlements.keys()))

        if q == "settlement_info":
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

        if q == "region_settlements":
            region_id = params["region_id"]
            result = []
            for s in self._settlements.values():
                if s.region_id == region_id:
                    result.append(
                        {
                            "id": s.id,
                            "name": s.name,
                            "type": s.type.value,
                            "population": s.population,
                            "prosperity": s.prosperity,
                            "defenses": s.defenses,
                        }
                    )
            return Answer(value=result)

        if q == "region_income":
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
