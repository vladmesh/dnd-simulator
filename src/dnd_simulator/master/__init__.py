"""Dungeon Master — the LLM-powered orchestrator.

The Master interprets player actions and translates them into world interactions:
- Decides which layers to query or update
- Manages time flow (how much to advance, when to interrupt)
- Generates narrative descriptions of what happens
- Subtly guides players toward authored content via hooks and hints
- Resolves mechanical checks using rules (dice rolls, skill checks)

The Master has access to all layers and the full world state.
It uses tool calling to interact with the simulation programmatically.
"""
