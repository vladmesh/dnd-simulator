"""Transport adapters — how players connect to the game.

Thin wrappers over GameService that handle a specific transport protocol:
- cli: terminal REPL (input/print)
- api: REST API via FastAPI (planned)
- telegram: Telegram bot (planned)

Adapters contain no game logic. They translate transport-specific
input/output into GameService calls.
"""
