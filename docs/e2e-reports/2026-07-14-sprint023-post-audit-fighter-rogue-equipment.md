# E2E Report: Sprint 023 post-audit Fighter, Rogue and equipment

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 4, 5, 8 (next uncovered block)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 7 targeted checks, 6 passed, 1 partial
- Quick fixes: 0 applied
- Product blockers: 0 found
- Full required non-LLM regression: not completed in this run

## Results

| Section | Scenario | Status | Notes |
|---|---|---|---|
| 4.1 | Fighter Second Wind | pass | A UI-created Fighter L1 (Defense, 12 HP, AC 19) was reduced to 6 HP as a test fixture. The Class Features drawer exposed Second Wind; using it restored 6 HP to 12/12 and removed the spent control. |
| 4.2 | Fighter Defense | pass | The same Fighter creation path showed Chain Mail, Longsword and Shield with AC 19. |
| 4.5 | Rogue combat actions | partial | A UI-created Rogue L1 entered combat through Attack on a nearby NPC. Dash and Disengage were visible while Attack was available, but the Dash click did not produce a corresponding backend action log or an unambiguous budget transition. Rerun this row with an explicit action-result capture. |
| 5.1 | Equip weapon | pass | Longsword was unequipped into the Bag and re-equipped through its UI control. |
| 5.2 | Equip armor and shield | pass | Chain Mail and Shield were each unequipped into the Bag and re-equipped through their UI controls. |
| 5.3 | Use healing potion | pass | A catalog Health Potion was supplied as a test fixture. Using the visible UI control healed 6 HP from 6/12 to 12/12 and consumed the item. |
| 8.1--8.3 | Inventory and accessory | pass | All six inventory slots were visible. Ring of Protection was equipped from the Bag, increasing AC 19 to 20, then unequipped through the Ring slot. |

## Findings

### Blockers

- Rogue Dash needs one focused rerun: the UI exposed the action, but the observed click did not reach a logged server action or prove the documented action-budget contract.

### Remaining required coverage

- The focused Rogue Dash rerun, conditions, reactions, faction relations, lairs/loot, and intents/travel remain before the required no-LLM post-audit boundary is complete. This report therefore does not unblock Phase 8 Task 2.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` contained no error, exception or traceback lines.
- Structured logs were written for the Fighter and Rogue sessions: `/tmp/dnd-e2e-logs/session_e643b28d/full.jsonl` and `/tmp/dnd-e2e-logs/session_2826db74/full.jsonl`.
- Browser console had no errors and one pre-existing WebSocket-close warning per navigation.
