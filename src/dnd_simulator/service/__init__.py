"""Game service layer — session lifecycle, action dispatch, world commands.

- GameService: world loading, session creation/deletion, content CRUD, catalog management
- GameSession: player connection, round thread, listener dispatch, action submission
- ActionDispatcher: validate → handler → budget consume pipeline
- BrainFactory: creates Brain instances from ai_type string
- commands_*: domain-specific command modules (politics, time, save, entities)
- dto: typed DTOs returned by service methods (PlayerStatusData, ResourcePoolView)
"""

from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession

__all__ = ["GameService", "GameSession"]
