"""Transport adapters — how players connect to the game.

Thin wrappers that handle a specific transport protocol:
- cli: terminal REPL via GameService commands (input/print)
- cli_loop: turn-based game loop CLI using game_loop.py
- api: REST API via FastAPI (planned)
- telegram: Telegram bot (planned)

Adapters contain no game logic. They translate transport-specific
input/output into game calls.
"""
