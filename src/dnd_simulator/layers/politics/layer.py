"""PoliticsLayer — nations, diplomacy, warfare, economy."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    FactionRelation,
    Leader,
    LeaderTrait,
    Nation,
)
from dnd_simulator.rules.politics import (
    calculate_military_upkeep,
    calculate_region_income,
    calculate_stability_drift,
    calculate_trade_income,
    calculate_war_strength,
    clamp,
    leader_death_chance,
    peace_chance,
    rebellion_chance,
    trade_agreement_chance,
    war_declaration_chance,
)

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta


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

        # Income from settlements (if available), else fall back to terrain-based
        self._region_income_fn = region_income_fn

    @property
    def name(self) -> str:
        return "politics"

    @property
    def tick_interval(self) -> int:
        return 2_592_000  # 30 days in seconds

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
        """Get relation between two factions.

        Same faction = FRIENDLY. Unspecified = NEUTRAL.
        """
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
        """Process monthly political updates.

        World only calls this when tick_interval has elapsed,
        so delta covers at least one month.
        """
        months = max(1, delta.seconds // 2_592_000)
        events: list[Event] = []
        for _ in range(months):
            events.extend(self._monthly_tick())
        return events

    def _monthly_tick(self) -> list[Event]:
        """One month of political simulation."""
        events: list[Event] = []

        # 1. Economy
        events.extend(self._process_economy())

        # 2. Wars
        events.extend(self._process_wars())

        # 3. Stability
        events.extend(self._process_stability())

        # 4. Diplomacy (new wars, peace, trade)
        events.extend(self._process_diplomacy())

        # 5. Leaders (death, aging)
        events.extend(self._process_leaders())

        # 6. Increment war durations
        for key in list(self._war_durations):
            if self._relations.get(key) == DiplomaticStatus.WAR:
                self._war_durations[key] += 1

        # 7. Remove dead nations (no regions)
        self._remove_dead_nations(events)

        return events

    def _process_economy(self) -> list[Event]:
        """Calculate income, trade, and upkeep for each nation."""
        for nation in self._nations.values():
            # Base income from controlled regions
            if self._region_income_fn:
                income = sum(self._region_income_fn(rid) for rid in nation.regions)
            else:
                income = sum(
                    calculate_region_income(self._region_terrains.get(rid, "plains")) for rid in nation.regions
                )

            # Trade income
            trade_partners = self._count_trade_partners(nation.id)
            income += calculate_trade_income(nation.wealth, trade_partners)

            # Leader merchant bonus
            if nation.leader and nation.leader.trait == LeaderTrait.MERCHANT:
                income *= 1.3

            # Military upkeep
            upkeep = calculate_military_upkeep(nation.military)

            nation.wealth = clamp(nation.wealth + income - upkeep)

        return []

    def _process_wars(self) -> list[Event]:
        """Resolve active wars — winner takes a border region."""
        events: list[Event] = []

        for key, status in list(self._relations.items()):
            if status != DiplomaticStatus.WAR:
                continue

            nation_a = self._nations.get(key[0])
            nation_b = self._nations.get(key[1])
            if not nation_a or not nation_b:
                continue

            # Roll for each side
            strength_a = calculate_war_strength(nation_a.military, nation_a.stability, self._rng.random())
            strength_b = calculate_war_strength(nation_b.military, nation_b.stability, self._rng.random())

            if abs(strength_a - strength_b) < 5.0:
                # Stalemate — both lose a bit of military
                nation_a.military = clamp(nation_a.military - 1.0)
                nation_b.military = clamp(nation_b.military - 1.0)
                continue

            winner, loser = (nation_a, nation_b) if strength_a > strength_b else (nation_b, nation_a)

            # Find border region to conquer
            border_region = self._find_border_region(winner.id, loser.id)
            if border_region:
                loser.regions.remove(border_region)
                winner.regions.append(border_region)
                events.append(
                    Event(
                        event_type=EventType.CUSTOM,
                        source_layer=self.name,
                        data={
                            "type": "region_conquered",
                            "winner": winner.id,
                            "loser": loser.id,
                            "region": border_region,
                        },
                        description=(f"{winner.name} conquers {border_region} from {loser.name}"),
                    )
                )

            # War costs
            winner.military = clamp(winner.military - 2.0)
            loser.military = clamp(loser.military - 4.0)
            loser.stability = clamp(loser.stability - 3.0)

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

            # Rebellion check
            if self._rng.random() < rebellion_chance(nation.stability):
                nation.wealth = clamp(nation.wealth * 0.7)
                nation.military = clamp(nation.military * 0.6)
                nation.stability = 30.0  # Reset to low-but-not-critical
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

    def _process_diplomacy(self) -> list[Event]:
        """Check for new wars, peace treaties, trade agreements."""
        events: list[Event] = []
        nation_ids = list(self._nations.keys())

        for i, nid_a in enumerate(nation_ids):
            for nid_b in nation_ids[i + 1 :]:
                nation_a = self._nations[nid_a]
                nation_b = self._nations[nid_b]
                key = _relation_key(nid_a, nid_b)
                status = self._relations.get(key, DiplomaticStatus.PEACE)

                # Are they neighbors?
                if not self._nations_are_neighbors(nid_a, nid_b):
                    continue

                if status == DiplomaticStatus.WAR:
                    # Peace check
                    months = self._war_durations.get(key, 0)
                    if self._rng.random() < peace_chance(months):
                        self._relations[key] = DiplomaticStatus.PEACE
                        self._war_durations.pop(key, None)
                        events.append(
                            Event(
                                event_type=EventType.CUSTOM,
                                source_layer=self.name,
                                data={"type": "peace", "nation_a": nid_a, "nation_b": nid_b},
                                description=f"{nation_a.name} and {nation_b.name} sign a peace treaty",
                            )
                        )

                elif status == DiplomaticStatus.PEACE:
                    # War declaration check (both directions)
                    for aggressor, target in [(nation_a, nation_b), (nation_b, nation_a)]:
                        chance = war_declaration_chance(
                            aggressor.military,
                            target.military,
                            aggressor.leader.trait.value if aggressor.leader else None,
                        )
                        if self._rng.random() < chance:
                            self._relations[key] = DiplomaticStatus.WAR
                            self._war_durations[key] = 0
                            events.append(
                                Event(
                                    event_type=EventType.CUSTOM,
                                    source_layer=self.name,
                                    data={"type": "war_declared", "aggressor": aggressor.id, "target": target.id},
                                    description=f"{aggressor.name} declares war on {target.name}!",
                                ),
                            )
                            break  # Only one war declaration per pair per month

                    # Trade agreement check (if still at peace)
                    if self._relations.get(key) == DiplomaticStatus.PEACE:
                        for n in [nation_a, nation_b]:
                            if (
                                n.leader
                                and n.leader.trait in (LeaderTrait.MERCHANT, LeaderTrait.DIPLOMAT)
                                and self._rng.random() < trade_agreement_chance()
                            ):
                                self._relations[key] = DiplomaticStatus.TRADE_AGREEMENT
                                events.append(
                                    Event(
                                        event_type=EventType.CUSTOM,
                                        source_layer=self.name,
                                        data={"type": "trade_agreement", "nation_a": nid_a, "nation_b": nid_b},
                                        description=(f"{nation_a.name} and {nation_b.name} sign a trade agreement"),
                                    )
                                )
                                break

        return events

    def _process_leaders(self) -> list[Event]:
        """Age leaders and check for death."""
        events: list[Event] = []

        for nation in self._nations.values():
            if not nation.leader:
                nation.leader = self._generate_leader()
                continue

            nation.leader.age += 1  # 1 month = ~1 year in game terms for leader aging

            if self._rng.random() < leader_death_chance(nation.leader.age):
                old_name = nation.leader.name
                nation.leader = self._generate_leader()
                nation.stability = clamp(nation.stability - 10.0)

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
            # Clean up relations
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

    # -- helpers --

    def _count_trade_partners(self, nation_id: str) -> int:
        """Count nations with trade agreement or alliance."""
        count = 0
        for key, status in self._relations.items():
            if nation_id in key and status in (DiplomaticStatus.TRADE_AGREEMENT, DiplomaticStatus.ALLIANCE):
                count += 1
        return count

    def _find_border_region(self, winner_id: str, loser_id: str) -> str | None:
        """Find a loser's region adjacent to any winner's region."""
        winner = self._nations.get(winner_id)
        loser = self._nations.get(loser_id)
        if not winner or not loser:
            return None

        winner_regions = set(winner.regions)

        for rid in loser.regions:
            neighbors = self._region_adjacency.get(rid, [])
            if any(n in winner_regions for n in neighbors):
                return rid

        return None

    def _nations_are_neighbors(self, nid_a: str, nid_b: str) -> bool:
        """Check if two nations share a border."""
        nation_a = self._nations.get(nid_a)
        nation_b = self._nations.get(nid_b)
        if not nation_a or not nation_b:
            return False

        b_regions = set(nation_b.regions)
        for rid in nation_a.regions:
            neighbors = self._region_adjacency.get(rid, [])
            if any(n in b_regions for n in neighbors):
                return True
        return False

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
        """Answer queries about the political world.

        Supported queries (see QueryType enum):
        - NATIONS: list all nation IDs
        - NATION_INFO: params={nation_id} -> full nation data
        - RELATIONS: params={nation_id} -> all relations for a nation
        - REGION_OWNER: params={region_id} -> owning nation ID or None
        """
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
            return Answer(value=relation.value)

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
