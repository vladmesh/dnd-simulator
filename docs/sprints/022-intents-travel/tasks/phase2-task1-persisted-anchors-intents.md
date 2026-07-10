# Task: Persisted anchors and timed intents

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 2 — Anchors, wait and sleep intents

## Description

Introduce the minimal activity model on `Creature`: an explicit anchor capability and a typed current intent for timed wait or sleep. The intent owns its kind, start time, and wake time; `wake_at_seconds` must stop being a parallel source of truth. Both fields must round-trip through the strict `EntitySave` union for players, NPCs, and generic creatures.

Keep this model in `core/` as transport- and layer-independent data. This task only establishes state and persistence. It does not change activation or action handlers yet, and it does not add travel fields that Phase 3 has not designed.

## Tests First

- A player, NPC, and generic creature with different anchor values and wait/sleep intents survive an EntitiesLayer save/load round-trip without losing the intent kind or timestamps.
- A creature with no intent round-trips as idle, without a fabricated wake time.
- The strict save schema rejects an unknown intent kind or extra intent fields instead of silently accepting a state that the engine cannot execute.

## Implementation

Add typed activity/intent data under `core/` and fields on `Creature`. Extend `CreatureFields` and entity serialization/restoration to use the same model for all creature variants. Remove `wake_at_seconds` from runtime and save models once all reads in this task's compile boundary have moved to the intent wake time; temporary handler/activation compatibility may read the new field but must not maintain both representations.

Likely files: `core/character.py`, a focused `core/intent.py`, `layers/entities/save_models.py`, `layers/entities/entity_serialization.py`, `layers/entities/layer.py`, and serialization tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Anchor status is explicit on every `Creature`, not inferred from `PlayerCharacter`.
- [x] Wait and sleep use a typed persisted intent with one authoritative wake time.
- [x] All `EntitySave` creature variants preserve the new fields under `extra="forbid"`.

## Status

`done`

## Developer Notes

Added `TimedIntent` with strict wait/sleep kinds and absolute start/wake timestamps. `Creature.current_intent` is the only runtime wake source; the old standalone field was removed. Existing activation and action callers were migrated mechanically to the new field without changing their behavior, leaving the player-agnostic activation rewrite for task 2. `PlayerCharacter` defaults to an anchor while other creatures default to non-anchor, and save payloads persist the explicit value for every creature kind.
