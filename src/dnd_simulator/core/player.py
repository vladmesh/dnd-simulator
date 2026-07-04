"""Player character model."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.character import Character


@dataclass
class PlayerCharacter(Character):
    """The player's avatar in the world.

    Decisions are made by an attached Brain (PlayerBrain), just like NPCs.
    Transport-specific I/O (CLI, WebSocket) is handled by the Brain's turn handler.

    Save/load is handled by ``content_loader.creatures`` (``player_to_full_save_data`` /
    ``load_player_save_data``) so ``core`` carries no dependency on ``content_loader``.
    """
