"""Transport adapters — how players connect to the game.

Thin wrappers that handle a specific transport protocol:
- api/: FastAPI REST + WebSocket adapter (world, session, content, player routes, WS game loop)

Adapters contain no game logic. They translate transport-specific
input/output into game calls.
"""
