"""Game service layer — session lifecycle, action dispatch, world commands.

- GameService: world loading, session creation/deletion; thin facade composed of command mixins
- WorldBuilderCommands / PlayerCommands: mixins peeled off GameService (world+content+catalog CRUD;
  create_player/level_up_player/player_status). GameServiceProtocol (base) declares the shared interface
- GameSession: player connection, bounded round-thread lifecycle, world snapshot gate,
  listener dispatch, action submission
- ActionDispatcher: validate → handler → budget consume pipeline
- action_parsing: parse JSON payloads into Action (ActionParseError); keeps adapters off core Action types
- BrainFactory: creates Brain instances from ai_type string
- commands_*: domain-specific command modules (creatures, politics, time, save, world_state)
- dto: typed DTOs returned by service methods (PlayerStatusData, ResourcePoolView)
"""

from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession

__all__ = ["GameService", "GameSession"]
