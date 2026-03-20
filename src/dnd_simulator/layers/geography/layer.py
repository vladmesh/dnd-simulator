"""GeographyLayer — concrete implementation of Layer for the physical world."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import Answer, Event, EventType, Query
from dnd_simulator.layers.geography.formulas import (
    apply_weather_temperature_modifier,
    calculate_base_temperature,
    calculate_daylight_hours,
    calculate_distance_km,
    calculate_travel_hours,
    get_season,
)
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
    WeatherCondition,
)
from dnd_simulator.layers.geography.weather import WeatherEngine

if TYPE_CHECKING:
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState


class GeographyLayer(Layer):
    """Physical world simulation: terrain, weather, temperature, daylight."""

    def __init__(
        self,
        regions: list[Region] | None = None,
        weather_seed: int | None = None,
    ) -> None:
        self._regions: dict[str, Region] = {}
        if regions:
            for r in regions:
                self._regions[r.id] = r
        self._weather = WeatherEngine(seed=weather_seed)

    @property
    def name(self) -> str:
        return "geography"

    @property
    def tick_interval(self) -> int:
        return 0  # always tick — internal step calculation handles granularity

    def add_region(self, region: Region) -> None:
        self._regions[region.id] = region

    def get_region(self, region_id: str) -> Region:
        if region_id not in self._regions:
            raise KeyError(f"Region '{region_id}' not found")
        return self._regions[region_id]

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Advance weather and recalculate temperatures."""
        events: list[Event] = []
        time = world_state.time

        # One weather transition per ~6 hours
        steps = max(1, delta.total_hours // 6)

        for region in self._regions.values():
            season = get_season(time.month, region.latitude)
            old_weather = region.weather

            for _ in range(steps):
                base_temp = calculate_base_temperature(region.latitude, time.month, time.hour, region.elevation)
                region.weather = self._weather.next_weather(region, season, base_temp)

            # Final temperature with weather modifier
            base_temp = calculate_base_temperature(region.latitude, time.month, time.hour, region.elevation)
            region.temperature = apply_weather_temperature_modifier(base_temp, region.weather)

            if region.weather != old_weather:
                events.append(
                    Event(
                        event_type=EventType.WEATHER_CHANGED,
                        source_layer=self.name,
                        data={
                            "region_id": region.id,
                            "old_weather": old_weather.value,
                            "new_weather": region.weather.value,
                            "temperature": region.temperature,
                        },
                        description=(
                            f"Weather in {region.name} changed from {old_weather.value} to {region.weather.value}"
                        ),
                    )
                )

        return events

    def handle_event(self, event: Event) -> list[Event]:
        """Geography doesn't react to external events."""
        return []

    def query(self, query: Query) -> Answer:
        """Answer queries about the physical world.

        Supported queries:
        - "weather": params={region_id} -> condition and temperature
        - "connections": params={region_id} -> connected regions with directions
        - "travel_time": params={from_id, to_id} -> travel hours, distance
        - "daylight": params={region_id, month?} -> hours of daylight
        - "region_info": params={region_id} -> full region data
        - "regions": -> list of all region IDs
        """
        q = query.question
        params = query.params

        if q == "weather":
            region = self.get_region(params["region_id"])
            return Answer(
                value={
                    "condition": region.weather.value,
                    "temperature": region.temperature,
                },
                description=f"{region.name}: {region.weather.value}, {region.temperature}°C",
            )

        if q == "connections":
            region = self.get_region(params["region_id"])
            return Answer(
                value=[{"target_id": c.target_id, "direction": c.direction.value} for c in region.connections],
            )

        if q == "travel_time":
            origin = self.get_region(params["from_id"])
            dest = self.get_region(params["to_id"])
            distance = calculate_distance_km(origin.latitude, origin.longitude, dest.latitude, dest.longitude)
            elevation_diff = max(0.0, dest.elevation - origin.elevation)
            hours = calculate_travel_hours(distance, dest.terrain, dest.weather, elevation_diff)
            return Answer(
                value={"hours": hours, "distance_km": distance},
                description=f"{distance} km, ~{hours} hours on foot",
            )

        if q == "daylight":
            region = self.get_region(params["region_id"])
            month = params.get("month", 6)
            hours = calculate_daylight_hours(region.latitude, int(month))
            return Answer(value=hours, description=f"{hours} hours of daylight")

        if q == "region_info":
            region = self.get_region(params["region_id"])
            return Answer(
                value={
                    "id": region.id,
                    "name": region.name,
                    "latitude": region.latitude,
                    "longitude": region.longitude,
                    "elevation": region.elevation,
                    "terrain": region.terrain.value,
                    "water_proximity": region.water_proximity,
                    "weather": region.weather.value,
                    "temperature": region.temperature,
                }
            )

        if q == "regions":
            return Answer(value=list(self._regions.keys()))

        raise ValueError(f"Unknown geography query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize geography state."""
        regions: dict[str, Any] = {}
        for rid, r in self._regions.items():
            regions[rid] = {
                "id": r.id,
                "name": r.name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "elevation": r.elevation,
                "terrain": r.terrain.value,
                "water_proximity": r.water_proximity,
                "connections": [{"target_id": c.target_id, "direction": c.direction.value} for c in r.connections],
                "weather": r.weather.value,
                "temperature": r.temperature,
            }
        return {"regions": regions}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore geography from saved state."""
        regions_data = state["regions"]
        assert isinstance(regions_data, dict)
        self._regions.clear()

        for rid, rdata in regions_data.items():
            assert isinstance(rdata, dict)

            connections: list[Connection] = []
            conn_list = rdata.get("connections", [])
            assert isinstance(conn_list, list)
            for c in conn_list:
                assert isinstance(c, dict)
                connections.append(
                    Connection(
                        target_id=str(c["target_id"]),
                        direction=Direction(str(c["direction"])),
                    )
                )

            region = Region(
                id=str(rid),
                name=str(rdata["name"]),
                latitude=float(rdata["latitude"]),
                longitude=float(rdata["longitude"]),
                elevation=float(rdata["elevation"]),
                terrain=TerrainType(str(rdata["terrain"])),
                water_proximity=float(rdata["water_proximity"]),
                connections=connections,
                weather=WeatherCondition(str(rdata.get("weather", "clear"))),
                temperature=float(rdata.get("temperature", 15.0)),
            )
            self._regions[rid] = region
