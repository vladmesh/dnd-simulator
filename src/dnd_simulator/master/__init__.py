"""Dungeon Master — reserved for the LLM-powered narrative orchestrator.

The package is a skeleton from the original architecture and holds no code. Nothing imports it.
The responsibilities it was drafted for are currently split elsewhere:
- action interpretation and dispatch: service/ (GameService, ActionDispatcher)
- time flow and interrupts: core/world.py and round.py
- narrative text: layers/entities/perception.py, with LLM prompts in llm/
- mechanical checks: rules/

Reintroducing a Master means taking work back from those modules, not adding a layer on top.
"""
