# Task: Anchor-driven activation and fast-forward

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 2 — Anchors, wait and sleep intents

## Description

Make activation depend on the creature's anchor capability instead of its Python class. A living, idle anchor keeps its local scene active; an anchor with a wait or sleep intent does not. Nearby non-anchor creatures must not keep the scene running after its last awake anchor starts a timed intent. Combat remains active independently of anchors.

Teach the round loop to derive its next wake point from timed intents. When no creature needs a round before that point, advance the world directly to the nearest wake time, complete the timer boundary, and reactivate from anchor state. Preserve the existing materialization and encounter boundaries without making activation transitive.

## Tests First

- An explicitly anchored NPC or generic creature activates its co-located scene even when no `PlayerCharacter` exists.
- A `PlayerCharacter` whose anchor flag is off does not activate a scene merely because of its type.
- When the only awake anchor starts waiting beside a rule NPC, the NPC becomes dormant and the world jumps to the anchor's wake time instead of executing hundreds of six-second NPC turns.
- With two timed intents, fast-forward stops at the earlier wake point and leaves the later intent in progress.
- A creature in combat stays active without an awake anchor; a dormant non-anchor does not become a new anchor by being near another active creature.

## Implementation

Refactor `ActivationManager.update_activation` into type-agnostic passes over `Creature`. Replace player-location naming and the no-player early return with anchor locations. Expire/complete timed intent boundaries consistently, without proximity silently deleting an unrelated intent. Update `CreatureHost` and `EntitiesLayer` wake-point queries to read intents, then adapt `Round._fast_forward` to the new contract.

Keep encounter, squad, and lair materialization keyed to anchored active locations as today. Do not introduce `Brain.gate()` or declarative triggers in this phase.

Likely files: `layers/entities/activation_manager.py`, `layers/entities/layer.py`, `core/creature_host.py`, `round.py`, activation/round tests, and affected materialization tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Activation contains no `PlayerCharacter` type check or player-presence early return.
- [x] Active creatures do not activate further creatures transitively.
- [x] Waiting beside an ordinary NPC reaches the nearest wake point without per-round churn.
- [x] Combat activity and materialization behavior remain covered.

## Status

`done`

## Developer Notes

Activation now recomputes every creature from explicit anchor locations, timed intents, and combat state. Awake anchors of any creature class hold a scene active; ordinary active creatures do not propagate activation. Proximity no longer clears timed intents, so fast-forward wakes only the earliest timer and preserves later ones. Tests that previously treated `active=True` as a lasting mandate now assign `is_anchor=True` explicitly. One full-check attempt ended with pytest code 139 after all 2451 tests passed; the clean retry completed backend and frontend gates.
