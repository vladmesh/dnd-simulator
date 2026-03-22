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

    def get_players(self) -> list[PlayerCharacter]:
        """Return all player characters in this session."""
        answer = self.world.query_layer("entities", Query(question="players", params={}))
        result = answer.value
        if isinstance(result, list):
            return result
        return []

    def get_player(self, player_id: str | None = None) -> PlayerCharacter | None:
        """Look up a player character.

        If *player_id* is given, return that specific player.
        Otherwise return the first (and usually only) player — handy for
        single-player sessions and backward compatibility.
        """
        if player_id:
            answer = self.world.query_layer(
                "entities", Query(question="player", params={"id": player_id})
            )
            result = answer.value
            return result if isinstance(result, PlayerCharacter) else None
        # Legacy: return first player
        players = self.get_players()
        return players[0] if players else None

    @property
    def player_location(self) -> str:
        """Shortcut for the first player's current location."""
        player = self.get_player()
        return player.location_id if player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        player = self.get_player()
        if player:
            player.location_id = value
