# Task: Built-in intent interruptions

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 4 — Interruptible journeys and E2E closure

## Description

Define one engine-level operation for interrupting a creature's current wait, sleep, or travel intent and wire it to the built-in reasons already owned by the entities layer. Taking damage and entering combat interrupt immediately. A traveler arriving at a location held by another awake anchor is drawn into that scene and stops there instead of silently continuing to the next edge. Ordinary leg arrival without a scene continues the stored route, while final arrival and elapsed wait/sleep remain successful completion rather than interruption.

The operation must be idempotent and must not apply rest rewards or travel progress twice. Interruption keeps the creature at its last reached location, clears the intent once, and makes an eligible anchor available on the next activation pass. Keep the reason set built in; declarative trigger tables and Brain policy remain out of scope.

## Tests First

- A sleeping or waiting creature that takes damage wakes immediately without receiving rest completion benefits; repeating the interruption is a no-op.
- Starting combat at a location clears every participant's active intent before initiative proceeds, without moving a traveler or duplicating a combat participant.
- A traveler arriving at an intermediate location occupied by an awake anchor stops at that location and regains control; the same leg arrival at an otherwise dormant location schedules the next leg normally.
- Reaching a final destination clears travel as successful arrival, and reaching a wait or sleep timer applies its completion exactly once rather than reporting an interruption.

## Implementation

Add a focused interruption reason and helper beside the existing intent completion functions. Call it from the authoritative damage/combat paths and from activation after a travel leg reaches a scene. Preserve the existing `advance_travel_intent` route state until the reached leg has been committed, then decide whether to continue or interrupt. Emit structured logs/events only from this central operation so callers cannot disagree about semantics.

Likely files: `core/intent.py`, `layers/entities/intent_completion.py`, `layers/entities/activation_manager.py`, `layers/entities/combat_manager.py`, `layers/entities/combat_resolution.py`, and product-level intent/combat/round tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Damage, combat entry, and arrival into an awake scene interrupt through one idempotent operation.
- [x] Interrupted rest grants no completion effects and interrupted travel remains at the last reached location.
- [x] Timer completion, ordinary leg progression, and final arrival retain their existing successful behavior.

## Status

`done`

## Developer Notes

Added one idempotent interruption helper with built-in damage, combat, and scene reasons. Combat entry interrupts
all participants before their combat state is initialized; positive attack damage uses the same helper without
granting rest completion. Activation now commits travel one leg at a time, so arrival at a location already held by
an awake anchor stops the traveler there, while dormant locations, final arrival, and timed completion keep their
existing behavior. Full backend and frontend checks passed.
