"""Game service layer — session lifecycle, action dispatch, world commands.

- GameService: world loading, session creation/deletion; thin facade composed of command mixins
- WorldBuilderCommands / PlayerCommands: mixins peeled off GameService (world+content+catalog CRUD;
  create_player/level_up_player/player_status). GameServiceProtocol (base) declares the shared interface
- GameSession: player connection, round thread, listener dispatch, action submission;
  spectator-listeners (read-only broadcast, never drive the round) + disconnect grace-period evict
- identity: Role (worldbuilder/DM/admin/player) + Identity + resolve_identity; the request-seam
  backing get_identity (X-User-Id/X-Role headers, no auth/DB). Attribution + UI-lens projection, not enforced
- ActionDispatcher: validate → handler → budget consume pipeline
- action_parsing: parse JSON payloads into Action (ActionParseError); keeps adapters off core Action types
- BrainFactory: creates Brain instances from ai_type string
- commands_*: domain-specific command modules (creatures, politics, time, save, world_state)
- dto: typed DTOs returned by service methods (PlayerStatusData, ResourcePoolView)
"""

from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession

__all__ = ["GameService", "GameSession"]
