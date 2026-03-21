from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.models import Query
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World


@dataclass
class GameSession:
    """An active game session."""

    session_id: str
    world: World
    lang: str = "en"
    world_name: str = ""

    def get_player(self) -> PlayerCharacter | None:
        """Look up the player entity from the entities layer."""
        answer = self.world.query_layer("entities", Query(question="player", params={}))
        result = answer.value
        if isinstance(result, PlayerCharacter):
            return result
        return None

    @property
    def player_location(self) -> str:
        """Shortcut for player's current location."""
        player = self.get_player()
        return player.location_id if player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        player = self.get_player()
        if player:
            player.location_id = value
