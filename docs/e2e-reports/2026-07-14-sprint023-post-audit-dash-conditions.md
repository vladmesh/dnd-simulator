# E2E Report: Sprint 023 post-audit Dash and conditions

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 4.5, 7.1, 7.2
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 3 targeted checks, 3 passed
- Quick fixes: 0 applied
- Product blockers: 0 found
- Full required non-LLM regression: not completed in this run

## Results

| Section | Scenario | Status | Notes |
|---|---|---|---|
| 4.5 | Rogue Cunning Action Dash | pass | UI-created Rogue L1 entered combat with `practice_thug`. Choosing Dash → Bonus Action changed Action 1 / Bonus 1 / Movement 30 ft to Action 1 / Bonus 0 / Movement 60 ft. Backend recorded `dash` with `extra_movement_ft: 30`. |
| 7.1 | Apply condition via Master | pass | Master edit form applied `stunned` to `practice_thug`; on reconnect the combat loop logged `turn_skipped_incapacitated`. |
| 7.2 | Stunned target grants advantage | pass | Rogue attacked the stunned `practice_thug`; backend logged `attack_roll` with `advantage: true` and the Rogue Sneak Attack reason `advantage`. |

## Findings

### Blockers

- None in the scenarios above.

### Minor

- The Master condition picker renders both `deafened` and `stunned` as «Оглушён» in RU. The first matching control applied `deafened`; the second applied `stunned`. This is a localization-label ambiguity, not a condition-runtime failure.
- Reconnecting from Master to the player page produced the known transient `listener_error` in `WsEventListener.on_turn`; the player received a usable turn and the tested actions completed.

### Remaining required coverage

- Reactions, faction relations, lairs/loot, and intents/travel remain before Task 2 can be unblocked. Prior green reports already cover Paladin, core UI, Master mutations, Fighter and equipment.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` recorded the Dash action and the stunned-target advantage/Sneak Attack path, with no traceback.
- Browser console had no errors and one pre-existing WebSocket-close warning per navigation.
