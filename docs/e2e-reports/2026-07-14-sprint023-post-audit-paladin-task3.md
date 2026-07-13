# E2E Report: Sprint 023 post-audit Paladin Task 3 continuation

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 3.5, 14.1--14.4
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 4 targeted, 3 passed, 1 partial
- Quick fixes: 0 applied
- Blockers: 0 product blockers

## Results

| Scenario | Status | Notes |
|---|---|---|
| 14.1 Paladin L1 creation | pass | Human Paladin had 12 HP with CON 14, AC 18, Chain Mail, Longsword and Shield. The L1 form had no Fighting Style selector or spell slots. |
| 3.5 manual L2 re-entry | pass | Killing `xp_dummy` awarded 500 XP and opened the L2 dialog. Close deferred it, the manual `Level up` control remained visible, and it reopened the same Dueling selector. Confirm produced L2, 20 HP and two first-level slots. |
| 3.5 / 14.3 movement and Divine Smite | pass | After moving east 5 ft and advancing the round, `Attack practice_thug + Smite (slot 1)` hit for `1d8 slashing + 2d8 divine_smite + +2 str + +2 dueling`. The menu had shown 2/2 slots before the action. |
| 14.2 / 14.4 Lay on Hands and scope | partial | The Class Features drawer exposed only self as a Lay on Hands target while the hostile `practice_thug` was excluded, confirming UI target scope. The fixture left the Paladin at full HP, so submit correctly returned `Target is already at full HP`; a positive heal needs an injured valid target in a subsequent full regression. |

## Findings

- `practice_thug` disengaged after the Smite and then logged three `Cannot move there, blocked` attempts. The round continued and no exception reached the browser; this is a non-blocking RuleBrain/pathing observation.

## Log Analysis

- Backend log contained no error, exception or traceback. The expected rejected full-HP Lay on Hands request and the three blocked NPC move actions were structured `action_failed` info events.
- Browser console had no errors and one existing warning.
