from __future__ import annotations

from typing import Any

from dnd_simulator.service.base import GameServiceProtocol


class PoliticsCommands(GameServiceProtocol):
    """Mixin: politics and settlements hot controls."""

    def patch_nation(self, session_id: str, nation_id: str, updates: dict[str, Any]) -> None:
        """Update mutable nation fields in a live session."""
        session = self._get_session(session_id)
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
        session = self._get_session(session_id)
        layer = self._get_settlements_layer(session)
        settlement = layer.get_settlement(settlement_id)

        if "population" in updates:
            settlement.population = int(updates["population"])
        if "prosperity" in updates:
            settlement.prosperity = float(updates["prosperity"])
        if "defenses" in updates:
            settlement.defenses = float(updates["defenses"])
