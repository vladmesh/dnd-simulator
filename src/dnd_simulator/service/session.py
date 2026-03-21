from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World


@dataclass
class GameSession:
    """An active game session."""

    session_id: str
    world: World
    player: PlayerCharacter | None = None
    lang: str = "en"
    world_name: str = ""

    @property
    def player_location(self) -> str:
        """Shortcut for player's current location."""
        return self.player.location_id if self.player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        if self.player:
            self.player.location_id = value
