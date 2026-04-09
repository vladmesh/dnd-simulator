"""PoliticsLayer — nations, diplomacy, warfare, economy."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.layers.politics.diplomacy import process_diplomacy
from dnd_simulator.layers.politics.economy import process_economy
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    FactionRelation,
    Leader,
    LeaderTrait,
    Nation,
)
from dnd_simulator.layers.politics.warfare import process_wars
from dnd_simulator.rules.politics import (
    calculate_stability_drift,
    clamp,
    leader_death_chance,
    rebellion_chance,
)

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta

_TICK_INTERVAL_SECONDS = 2_592_000  # 30 days

REBELLION_WEALTH_FACTOR = 0.7
REBELLION_MILITARY_FACTOR = 0.6
REBELLION_STABILITY_RESET = 30.0
LEADER_DEATH_STABILITY_COST = 10.0

_LEADER_NAMES = [
    "Aldric",
    "Brenna",
    "Caspian",
    "Daria",
    "Edmund",
    "Freya",
    "Gareth",
    "Helena",
    "Ivan",
    "Isolde",
    "Kael",
    "Lyra",
    "Magnus",
    "Nadia",
    "Orin",
    "Petra",
    "Roland",
    "Senna",
    "Theron",
    "Ursula",
    "Varek",
    "Wren",
]


def _relation_key(a: str, b: str) -> tuple[str, str]:
    """Canonical key for a pair of nations (sorted)."""
    return (min(a, b), max(a, b))


class PoliticsLayer(Layer):
    """Geopolitics simulation: nations, economy, warfare, diplomacy."""

    def __init__(
        self,
        nations: list[Nation] | None = None,
        region_terrains: dict[str, str] | None = None,
        region_adjacency: dict[str, list[str]] | None = None,
        seed: int | None = None,
        region_income_fn: Callable[[str], float] | None = None,
        faction_relations: dict[tuple[str, str], FactionRelation] | None = None,
        faction_names: dict[str, str] | None = None,
    ) -> None:
        self._nations: dict[str, Nation] = {}
        if nations:
            for n in nations:
                self._nations[n.id] = n

        self._region_terrains: dict[str, str] = region_terrains or {}
        self._region_adjacency: dict[str, list[str]] = region_adjacency or {}
        self._relations: dict[tuple[str, str], DiplomaticStatus] = {}
        self._war_durations: dict[tuple[str, str], int] = {}
        self._faction_relations: dict[tuple[str, str], FactionRelation] = faction_relations or {}
        self._faction_names: dict[str, str] = faction_names or {}
        self._rng = random.Random(seed)

        self._region_income_fn = region_income_fn

    @property
    def name(self) -> str:
        return "politics"

    @property
    def tick_interval(self) -> int:
        return _TICK_INTERVAL_SECONDS

    def get_nation(self, nation_id: str) -> Nation:
        """Get a nation by ID. Raises KeyError if not found."""
        if nation_id not in self._nations:
            raise KeyError(f"Nation '{nation_id}' not found")
        return self._nations[nation_id]

    def set_relation(self, nation_a: str, nation_b: str, status: DiplomaticStatus) -> None:
        """Set diplomatic status between two nations."""
        key = _relation_key(nation_a, nation_b)
        self._relations[key] = status
        if status == DiplomaticStatus.WAR:
            if key not in self._war_durations:
                self._war_durations[key] = 0
        else:
            self._war_durations.pop(key, None)

    def get_relation(self, nation_a: str, nation_b: str) -> DiplomaticStatus:
        """Get diplomatic status between two nations."""
        return self._relations.get(_relation_key(nation_a, nation_b), DiplomaticStatus.PEACE)

    def set_faction_relation(self, faction_a: str, faction_b: str, relation: FactionRelation) -> None:
        """Set relation between two factions."""
        key = _relation_key(faction_a, faction_b)
        self._faction_relations[key] = relation

    def get_faction_relation(self, faction_a: str, faction_b: str) -> FactionRelation:
        """Get relation between two factions. Same faction = FRIENDLY. Unspecified = NEUTRAL."""
        if faction_a == faction_b:
            return FactionRelation.FRIENDLY
        return self._faction_relations.get(_relation_key(faction_a, faction_b), FactionRelation.NEUTRAL)

    def get_region_owner(self, region_id: str) -> str | None:
        """Which nation owns a region, if any."""
        for nation in self._nations.values():
            if region_id in nation.regions:
                return nation.id
        return None

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """Process monthly political updates."""
        months = max(1, delta.seconds // _TICK_INTERVAL_SECONDS)
        events: list[Event] = []
        for _ in range(months):
            events.extend(self._monthly_tick())
        return events

    def _monthly_tick(self) -> list[Event]:
        """One month of political simulation."""
        events: list[Event] = []

        # 1. Economy
        process_economy(
            self._nations,
            self._relations,
            self._region_terrains,
            region_income_fn=self._region_income_fn,
        )

        # 2. Wars
        events.extend(
            process_wars(self._nations, self._relations, self._war_durations, self._region_adjacency, self._rng)
        )

        # 3. Stability
        events.extend(self._process_stability())

        # 4. Diplomacy (new wars, peace, trade)
        events.extend(
            process_diplomacy(self._nations, self._relations, self._war_durations, self._region_adjacency, self._rng)
        )

        # 5. Leaders (death, aging)
        events.extend(self._process_leaders())

        # 6. Increment war durations
        for key in list(self._war_durations):
            if self._relations.get(key) == DiplomaticStatus.WAR:
                self._war_durations[key] += 1

        # 7. Remove dead nations (no regions)
        self._remove_dead_nations(events)

        return events

    def _process_stability(self) -> list[Event]:
        """Update stability and check for rebellions."""
        events: list[Event] = []

        for nation in list(self._nations.values()):
            at_war = any(
                self._relations.get(_relation_key(nation.id, other_id)) == DiplomaticStatus.WAR
                for other_id in self._nations
                if other_id != nation.id
            )

            drift = calculate_stability_drift(
                nation.stability,
                at_war,
                nation.wealth,
                nation.leader.trait.value if nation.leader else None,
            )
            nation.stability = clamp(nation.stability + drift)

            if self._rng.random() < rebellion_chance(nation.stability):
                nation.wealth = clamp(nation.wealth * REBELLION_WEALTH_FACTOR)
                nation.military = clamp(nation.military * REBELLION_MILITARY_FACTOR)
                nation.stability = REBELLION_STABILITY_RESET
                nation.leader = self._generate_leader()

                events.append(
                    Event(
                        event_type=EventType.CUSTOM,
                        source_layer=self.name,
                        data={"type": "rebellion", "nation": nation.id},
                        description=f"Rebellion in {nation.name}! {nation.leader.name} seizes power",
                    )
                )

        return events

    def _process_leaders(self) -> list[Event]:
        """Age leaders and check for death."""
        events: list[Event] = []

        for nation in self._nations.values():
            if not nation.leader:
                nation.leader = self._generate_leader()
                continue

            nation.leader.age += 1

            if self._rng.random() < leader_death_chance(nation.leader.age):
                old_name = nation.leader.name
                nation.leader = self._generate_leader()
                nation.stability = clamp(nation.stability - LEADER_DEATH_STABILITY_COST)

                events.append(
                    Event(
                        event_type=EventType.CUSTOM,
                        source_layer=self.name,
                        data={
                            "type": "leader_died",
                            "nation": nation.id,
                            "old_leader": old_name,
                            "new_leader": nation.leader.name,
                        },
                        description=(
                            f"{old_name} of {nation.name} has died. "
                            f"{nation.leader.name} ({nation.leader.trait.value}) takes the throne"
                        ),
                    )
                )

        return events

    def _remove_dead_nations(self, events: list[Event]) -> None:
        """Remove nations that lost all regions."""
        dead = [nid for nid, n in self._nations.items() if not n.regions]
        for nid in dead:
            nation = self._nations.pop(nid)
            for key in list(self._relations):
                if nid in key:
                    self._relations.pop(key, None)
                    self._war_durations.pop(key, None)
            events.append(
                Event(
                    event_type=EventType.CUSTOM,
                    source_layer=self.name,
                    data={"type": "nation_destroyed", "nation": nid},
                    description=f"{nation.name} has fallen!",
                )
            )

    def _generate_leader(self) -> Leader:
        """Create a random new leader."""
        name = self._rng.choice(_LEADER_NAMES)
        trait = self._rng.choice(list(LeaderTrait))
        age = self._rng.randint(25, 55)
        return Leader(name=name, age=age, trait=trait)

    # -- Layer interface --

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """Politics doesn't react to external events (yet)."""
        return ActionResult()

    def query(self, query: Query) -> Answer:
        """Answer queries about the political world."""
        q = query.question
        params = query.params

        if q is QueryType.NATIONS:
            return Answer(value=list(self._nations.keys()))

        if q is QueryType.NATION_INFO:
            nation = self._nations[params["nation_id"]]
            return Answer(
                value={
                    "id": nation.id,
                    "name": nation.name,
                    "regions": list(nation.regions),
                    "wealth": nation.wealth,
                    "military": nation.military,
                    "stability": nation.stability,
                    "leader": {
                        "name": nation.leader.name,
                        "age": nation.leader.age,
                        "trait": nation.leader.trait.value,
                    }
                    if nation.leader
                    else None,
                },
            )

        if q is QueryType.RELATIONS:
            nation_id = params["nation_id"]
            result: list[dict[str, str]] = []
            for key, status in self._relations.items():
                if nation_id in key:
                    other = key[1] if key[0] == nation_id else key[0]
                    result.append({"nation": other, "status": status.value})
            return Answer(value=result)

        if q is QueryType.REGION_OWNER:
            owner = self.get_region_owner(params["region_id"])
            return Answer(value=owner)

        if q is QueryType.FACTION_RELATION:
            relation = self.get_faction_relation(str(params["a"]), str(params["b"]))
            return Answer(value=relation)

        if q is QueryType.FACTION_NAME:
            faction_id = str(params["faction_id"])
            return Answer(value=self._faction_names.get(faction_id))

        raise ValueError(f"Unknown politics query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize politics state."""
        nations: dict[str, Any] = {}
        for nid, n in self._nations.items():
            nations[nid] = {
                "id": n.id,
                "name": n.name,
                "regions": list(n.regions),
                "wealth": n.wealth,
                "military": n.military,
                "stability": n.stability,
                "leader": {
                    "name": n.leader.name,
                    "age": n.leader.age,
                    "trait": n.leader.trait.value,
                }
                if n.leader
                else None,
            }

        relations: dict[str, str] = {}
        for key, status in self._relations.items():
            relations[f"{key[0]}:{key[1]}"] = status.value

        war_durations: dict[str, int] = {}
        for key, months in self._war_durations.items():
            war_durations[f"{key[0]}:{key[1]}"] = months

        return {
            "nations": nations,
            "relations": relations,
            "war_durations": war_durations,
        }

    def load_state(self, state: dict[str, object]) -> None:
        """Restore politics from saved state."""
        nations_data = state["nations"]
        assert isinstance(nations_data, dict)
        self._nations.clear()

        for nid, ndata in nations_data.items():
            assert isinstance(ndata, dict)
            leader_data = ndata.get("leader")
            leader = None
            if leader_data:
                assert isinstance(leader_data, dict)
                leader = Leader(
                    name=str(leader_data["name"]),
                    age=int(leader_data["age"]),
                    trait=LeaderTrait(str(leader_data["trait"])),
                )

            regions = ndata.get("regions", [])
            assert isinstance(regions, list)

            self._nations[str(nid)] = Nation(
                id=str(nid),
                name=str(ndata["name"]),
                regions=[str(r) for r in regions],
                wealth=float(ndata.get("wealth", 50.0)),
                military=float(ndata.get("military", 50.0)),
                stability=float(ndata.get("stability", 70.0)),
                leader=leader,
            )

        relations_data = state.get("relations", {})
        assert isinstance(relations_data, dict)
        self._relations.clear()
        for key_str, status_str in relations_data.items():
            parts = str(key_str).split(":")
            self._relations[(parts[0], parts[1])] = DiplomaticStatus(str(status_str))

        war_data = state.get("war_durations", {})
        assert isinstance(war_data, dict)
        self._war_durations.clear()
        for key_str, months in war_data.items():
            parts = str(key_str).split(":")
            self._war_durations[(parts[0], parts[1])] = int(months)
