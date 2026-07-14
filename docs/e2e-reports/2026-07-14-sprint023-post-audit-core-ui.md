# E2E Report: Sprint 023 post-audit core UI

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 1.2, 1.4, 1.5, 2.1, 2.2, 2.4, 3.1--3.4
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 8 targeted checks, 8 passed
- Quick fixes: 0 applied
- Blockers: no new product blocker found
- Full required non-LLM regression: not completed in this run

## Results

| Section | Scenario | Status | Notes |
|---|---|---|---|
| 1.2 | Sword Vale player setup | pass | A new session reached character creation and then a live player session. |
| 1.4 | Point-buy preview | pass | Fighter with STR 15, CON 14 and Defense entered with 12 HP, AC 19, Chain Mail, Longsword and Shield. |
| 1.5 | Fighter class UI | pass | Fighter exposed the Fighting Style selector; Defense was selectable. |
| 2.1 | Nearby perception | pass | Marta appeared in Nearby with Attack, Talk and Inspect controls. |
| 2.2 | Talk to rule-based NPC | pass | Sending `Hello` produced the player line and Marta's reply `Что будете заказывать?` in the live log. |
| 2.4 | Move between locations | pass | Selecting the 200m Market Square path changed the location from Salty Anchor to Market Square. |
| 3.1--3.3 | Combat start and resolution | pass | Attacking Marta started combat, showed initiative and recorded an attack roll with damage. |
| 3.4 | Combat end | pass | The attack killed Marta, logged the death and reputation change, and returned the sidebar to peaceful mode. |

## Findings

### Blockers

- None in this contiguous UI block. Phase 8 Task 2 remains blocked until all required no-LLM playbook sections have a green boundary.

### Remaining required coverage

- Fighter/Rogue feature permutations, equipment/accessories, Master mutations, conditions, reactions, faction relations, lairs/loot and intents/travel remain unexecuted in the post-audit rerun.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` had no error, exception or traceback lines.
- Browser console had no errors and one existing warning.
- Structured session log: `/tmp/dnd-e2e-logs/session_8a18031c/full.jsonl`.
