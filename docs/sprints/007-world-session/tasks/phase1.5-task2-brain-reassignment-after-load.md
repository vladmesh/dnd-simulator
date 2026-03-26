# Task: Reassign Brains After Load

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1.5 — Save/Load Gaps

## Description

Two related problems:

1. **Brain switch lost on load**: `_try_restore_session` calls `start_game()` which assigns brains based on template `ai_type`. Then `world.load()` restores `ai_type` from save. But the brain object was already assigned before `load_state` overwrote `ai_type` — so if the user switched an NPC from `rule_based` to `llm` (or vice versa), the brain doesn't match.

2. **Spawned creatures have no brain after load**: Task 1 makes `load_state()` recreate spawned entities, but `EntitiesLayer` doesn't know about `BrainFactory` (correct — it's a service-level dependency). The recreated entities will have `brain=None`.

Fix: after `world.load()` completes in both `_try_restore_session` and the manual `load_save` flow, loop through all entities and (re)assign brains via `BrainFactory` based on their current `ai_type`. This matches the existing pattern in `start_game` (lines 124-129).

Extract a helper `_assign_brains(session)` to avoid duplicating the loop in three places (start_game, restore, load_save).

## Tests First

Unit tests (mocked BrainFactory):

1. **Brain switch preserved after load**: Create NPC with `ai_type="rule_based"`, assign RuleBrain. Change `ai_type` to `"llm"`. Save state. Create fresh layer, load state. Call brain reassignment. Assert the NPC's brain is LlmBrain (or RuleBrain fallback if no LLM configured — the point is it re-reads `ai_type`).

2. **Spawned creature gets brain after load**: Save state includes a spawned NPC (from task 1). Load on fresh layer. Call brain reassignment. Assert the spawned NPC has a brain (not None).

3. **Brain reassignment is idempotent**: Call `_assign_brains` twice. No errors, brains still correct.

## Implementation

1. Extract `_assign_brains(self, session: Session) -> None` in `GameService` — loops entities, assigns brain via factory. Same logic as current lines 124-129 in `start_game`.

2. Call `_assign_brains` after `world.load()` in `_try_restore_session`.

3. Call `_assign_brains` after `world.load()` in `load_save` (the manual save/load endpoint handler).

4. Replace the inline loop in `start_game` with a call to `_assign_brains`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `_assign_brains` helper exists and is used in all three code paths
- [ ] Spawned creatures get a brain after load
- [ ] Brain switch (ai_type change) is preserved across save/load

## Status

`done`

## Developer Notes

- Extracted `_assign_brains(entities_layer)` in `GameService`, added to `GameServiceProtocol`.
- For NPCs: always reassigns brain from `ai_type` (handles brain switch case).
- For generic Creatures: assigns brain only if `brain is None` (handles spawned creatures).
- Called in 3 places: `start_game`, `_try_restore_session`, `load_game`.
- Slightly restructured `load_game` to call `_assign_brains` after both old/new format load paths, before backward-compat player block.
