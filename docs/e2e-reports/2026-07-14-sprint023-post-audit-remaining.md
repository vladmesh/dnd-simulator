# E2E Report: Sprint 023 post-audit remaining regression

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** partial 1, 2, 6
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 7 targeted checks, 7 passed
- Quick fixes: 0 applied
- Blockers: no new product blocker found
- Full required non-LLM regression: not completed in this run

## Results

| Section | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing Player/DM split | pass | Both cards were visible and routed to `/play` and `/master`. |
| 1.2 | Sword Vale player setup | pass | New Session opened character creation and a Fighter entered a live session. |
| 1.3 | Language toggle | pass | In the live session, EN to RU translated controls, headings, character class and exit action. Content location name remained English, consistent with the declared content-language contract. |
| 1.4 | Point-buy preview | pass | Fighter with STR 15, CON 14 and Defense showed HP 12, AC 19, Chain Mail, Longsword and Shield. |
| 2.1 | Nearby perception and inspect | pass | Nearby NPC `marta` exposed Attack, Talk and Inspect; Inspect opened from the player UI. |
| 2.3 | Wait time advance | pass | Wait advanced the live game clock from Y1490 M6 D1 10:00 to 11:00. |
| 6.1, 6.5 | Master worlds and live-session list | pass | Worlds tab showed library/editable controls; Sessions listed the live Sword Vale session once and its Manage link. |

## Findings

### Blockers

- None observed in the scenarios above.

### Remaining required coverage

- The accumulated Paladin reports cover the Phase 8 acceptance path. The required no-LLM regression still needs the unexecuted playbook rows: peaceful talk/movement, combat baseline, Fighter/Rogue feature permutations, equipment/accessories, Master mutations, conditions, reactions, faction relations, lairs/loot, and intents/travel.
- This partial run therefore cannot unblock Phase 8 Task 2 or serve as the post-audit green boundary.

### Minor

- Backend structured logs recorded one `listener_error` from `WsEventListener.on_turn` immediately after the player session connected. The UI remained usable and no browser error followed. The same transient observation appears in the earlier Paladin continuation and needs separate reproduction before it is treated as a product blocker.

## Log Analysis

- Browser console had no errors and one pre-existing warning.
- No traceback was emitted; one transient structured `listener_error` is recorded above.
