# E2E Report: Sprint 023 post-audit final areas

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 11, 13, 15, 16
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 7 targeted checks, 6 passed, 1 failed
- Quick fixes: 0 applied
- Blockers: 1 found
- Full required non-LLM regression: not complete because the lair lifecycle boundary failed.

## Results

| Section | Scenario | Status | Notes |
|---|---|---|---|
| 11.2 | Disengage prevents OA | pass | In the live Sword Vale fight with Gretta, Disengage consumed the action, then a 30 ft move completed with no reaction prompt or OA event; movement reached 0 ft and Reaction remained 1. |
| 13.2--13.3 | Auto-hostility and reputation | pass | Attacking peaceful Gretta began combat without target-scope rejection. Her death logged `Kingdom Forces` reputation 100 -> 80. |
| 15.1, 15.5 | Corpse loot and action surface | pass | The corpse exposed only Inspect in Nearby. Loot showed 500g and four items; after `Take all`, player gold changed 1000 -> 1500 and the holder showed Empty. |
| 15.2 | Lair materialization and core lifecycle | fail | Test Vale's Forest Clearing initially materialized one goblin chieftain and three minions. Setting that core's HP to 0 through the Master UI, then reconnecting the player, materialized a second chieftain and minion roster while retaining the dead original core. The log has new `lair_materialize` events but no terminal depletion/write-back for the edited core. |
| 16.1 | Wait beside RuleBrain NPC | pass | At the Salty Anchor, Wait advanced 10:00 -> 11:00 and returned the player action surface. |
| 16.2 | Travel over graph edges | pass | UI travel reached Market Square, Guard Post, Forest Road, and Forest Clearing without teleporting. Structured logs contain one `travel_start` and one `travel_leg_arrive` for each clicked edge. |
| 16.3 | Arrival cleanup | pass | After each arrival, the Location panel updated to the reached node and the normal player controls returned once; no stale journey surface was visible. |

## Findings

### Blockers

- Lair core mutation through the supported Master creature editor is not reconciled into a single depleted lair lifecycle. A reconnect after `current_hp=0` duplicates the lair roster rather than preserving a terminal core state. This blocks the required lair/treasury boundary and therefore Phase 8 Task 2.

### Minor

- The browser recorded only the pre-existing dev-mode WebSocket-close warning while pages were replaced. No browser errors occurred.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` has no error, exception, or traceback. It includes the expected rejected `take` attempt made before ending combat; the successful post-combat take completed normally.
- `/tmp/dnd-e2e-logs/session_d953fe0d/full.jsonl` records initial and reconnect-time `lair_materialize` events for distinct chieftain/minion IDs after the edited core reached 0 HP.
- `/tmp/dnd-e2e-logs/session_14956288/full.jsonl` records the combat death, reputation change, and loot transfer for Gretta.
