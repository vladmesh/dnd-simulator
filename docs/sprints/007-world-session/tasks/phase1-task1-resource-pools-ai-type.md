# Task: Serialize Resource Pools & NPC ai_type

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1 — Save/Load Completeness

## Description

Add resource pools and NPC `ai_type` to entities layer `get_state()`/`load_state()`. Currently resource pools are silently reset to max on load (Second Wind always available after reload), and NPC brain type reverts to `rule_based` regardless of what was set.

Changes in `layers/entities/layer.py`:
- `get_state()`: serialize `creature.resource_pools` (list of dicts: id, max_uses, current_uses, reset_on) and `npc.ai_type`
- `load_state()`: restore resource pools from saved data (overwrite current_uses on matching pool IDs), restore `npc.ai_type`

## Tests First

In `tests/unit/test_npc_layer.py` (or a new `test_entities_serialization.py`):

1. **Resource pool round-trip** — Create a fighter with Second Wind (1 use). Spend the resource (current_uses=0). Save → load → assert current_uses is still 0, not reset to max.
2. **Resource pool with multiple pools** — Creature with 2 pools at different states. Save → load → both preserved exactly.
3. **NPC ai_type round-trip** — Create NPC with `ai_type="llm"`. Save → load → assert `ai_type` is `"llm"`, not default `"rule_based"`.

## Implementation

- In `get_state()`: after the `isinstance(e, Creature)` block, serialize `resource_pools` as list of dicts.
- In `get_state()` NPC section: add `"ai_type": e.ai_type`.
- In `load_state()`: after restoring conditions/inventory on Creature, restore resource_pools by matching pool IDs (update current_uses on existing pools; pools come from content loader, we just need to patch the mutable state).
- In `load_state()` NPC section: restore `ai_type` from saved data.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Spent resource pool survives save/load round-trip
- [ ] NPC ai_type survives save/load round-trip

## Status

`pending`
