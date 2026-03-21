from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.models import Query
from dnd_simulator.service.session import GameSession, MasterResponse

if TYPE_CHECKING:
    from dnd_simulator.layers.politics.layer import PoliticsLayer
    from dnd_simulator.layers.settlements.layer import SettlementsLayer


class PoliticsCommands:
    """Mixin: politics and settlements commands."""

    def _get_politics_layer(self, session: GameSession) -> PoliticsLayer:
        raise NotImplementedError

    def _get_settlements_layer(self, session: GameSession) -> SettlementsLayer:
        raise NotImplementedError

    def _cmd_nations(self, session: GameSession) -> MasterResponse:
        """List all nations with summary stats."""
        world = session.world
        nation_ids = world.query_layer("politics", Query(question="nations", params={}))

        lines = [f"=== Nations of the World (Year {world.time.year}) ==="]
        current_region = world.location_graph.region_of(session.player_location) if session.player_location else ""
        for nid in nation_ids.value:
            info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nid}))
            n = info.value
            leader = n["leader"]
            leader_str = f"{leader['name']} ({leader['trait']})" if leader else "none"
            marker = ""
            owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": current_region}))
            if owner.value == nid:
                marker = " ← you are here"
            lines.append(
                f"  {n['name']}: W={n['wealth']:.0f} M={n['military']:.0f} S={n['stability']:.0f}"
                f"  Leader: {leader_str}  Regions: {len(n['regions'])}{marker}"
            )

        return MasterResponse(text="\n".join(lines))

    def _cmd_nation_info(self, session: GameSession, nation_id: str) -> MasterResponse:
        """Detailed info about a specific nation."""
        world = session.world

        try:
            info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nation_id}))
        except KeyError:
            nations = world.query_layer("politics", Query(question="nations", params={}))
            return MasterResponse(text=f"Nation '{nation_id}' not found. Known: {', '.join(nations.value)}")

        n = info.value
        leader = n["leader"]

        lines = [
            f"=== {n['name']} ===",
            f"Wealth: {n['wealth']:.0f}  |  Military: {n['military']:.0f}  |  Stability: {n['stability']:.0f}",
        ]
        if leader:
            lines.append(f"Leader: {leader['name']}, age {leader['age']} ({leader['trait']})")

        lines.append(f"Regions: {', '.join(n['regions'])}")

        # Relations
        rels = world.query_layer("politics", Query(question="relations", params={"nation_id": nation_id}))
        if rels.value:
            lines.append("\nDiplomacy:")
            for r in rels.value:
                other_info = world.query_layer(
                    "politics", Query(question="nation_info", params={"nation_id": r["nation"]})
                )
                status_str = r["status"].replace("_", " ").title()
                lines.append(f"  {other_info.value['name']}: {status_str}")

        return MasterResponse(text="\n".join(lines))

    def _cmd_settlements(self, session: GameSession) -> MasterResponse:
        """List all settlements in current region."""
        world = session.world
        region_id = world.location_graph.region_of(session.player_location)

        settlements = world.query_layer(
            "settlements", Query(question="region_settlements", params={"region_id": region_id})
        )

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
        lines = [f"=== Settlements in {info.value['name']} ==="]

        if not settlements.value:
            lines.append("  No settlements here.")
        else:
            for s in settlements.value:
                lines.append(
                    f"  {s['name']} ({s['type']})"
                    f"  Pop: {s['population']}  Prosperity: {s['prosperity']:.0f}"
                    f"  Defenses: {s['defenses']:.0f}"
                )

        return MasterResponse(text="\n".join(lines))

    def patch_nation(self, session_id: str, nation_id: str, updates: dict[str, Any]) -> None:
        """Update mutable nation fields in a live session."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        layer = self._get_politics_layer(session)
        nation = layer.get_nation(nation_id)

        if "wealth" in updates:
            nation.wealth = float(updates["wealth"])
        if "military" in updates:
            nation.military = float(updates["military"])
        if "stability" in updates:
            nation.stability = float(updates["stability"])

    def patch_settlement(self, session_id: str, settlement_id: str, updates: dict[str, Any]) -> None:
        """Update mutable settlement fields in a live session."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        layer = self._get_settlements_layer(session)
        settlement = layer.get_settlement(settlement_id)

        if "population" in updates:
            settlement.population = int(updates["population"])
        if "prosperity" in updates:
            settlement.prosperity = float(updates["prosperity"])
        if "defenses" in updates:
            settlement.defenses = float(updates["defenses"])
