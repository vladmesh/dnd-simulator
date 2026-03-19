"""NPCs layer — individual characters as LLM agents.

The most concrete and most expensive simulation layer:
- Authored NPCs: hand-crafted backstories, traits, and goals (loaded from content/)
- Procedural NPCs: generated on demand from settlement/region context
- Each NPC is an LLM agent with its own system prompt and memory

Depends on: all lower layers (an NPC's behavior is shaped by the world around them).
"""
