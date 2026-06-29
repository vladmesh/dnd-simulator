"""Transport adapters — how players connect to the game.

Thin wrappers that handle a specific transport protocol:
- api/: FastAPI REST + WebSocket adapter (master routes, player routes, WS game loop +
  ?spectate read-only observe path, get_identity X-User-Id/X-Role header seam)

Adapters contain no game logic. They translate transport-specific
input/output into game calls.
"""
