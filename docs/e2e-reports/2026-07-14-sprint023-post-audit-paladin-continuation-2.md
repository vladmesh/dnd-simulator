# E2E Report: Sprint 023 post-audit Paladin continuation

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 3.5, 14.1--14.4
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 4 targeted, 4 passed
- Quick fixes: 0 applied
- Product blockers: 0 found
- Full required non-LLM regression: not completed in this continuation

## Results

| Scenario | Status | Notes |
|---|---|---|
| 14.1 Paladin L1 creation | pass | Human Paladin L1 had 12 HP with CON 14, AC 18, Chain Mail, Longsword and Shield. Fighting Style and spell slots were absent. |
| 14.2 Lay on Hands | pass | After UI combat damage, healing self for 1 HP changed 10/12 to 11/12 and logged pool 5 to 4. The action exposed only the valid self target; hostile creatures were not selectable. |
| 3.5 L1 to L2 defer and confirmation | pass | Killing `xp_dummy` awarded 500 XP and opened the L2 modal. Close deferred it, the Character panel retained `Level up`, and reopening with Dueling produced L2, 20 max HP and two level-one spell slots. |
| 14.3 Divine Smite and 14.4 scope | pass | The UI offered `Attack practice_thug + Smite (slot 1) (2/2)`. A successful hit logged `1d8 slashing + 2d8 divine_smite + +2 dueling`, killed the hostile target, and returned to peaceful UI. |

## Findings

### Blockers

- None in the Paladin continuation. This report does not replace the required full non-LLM post-audit regression.

### Minor

- The backend logged one `listener_error` in `WsEventListener.on_turn` immediately after the initial player WebSocket disconnected during session setup. The Paladin flow continued, and no traceback or browser error followed; reproduce separately before treating it as a product defect.

## Log Analysis

- No traceback or exception appeared after the live scenarios began.
- Browser console reported no errors and one existing warning.
