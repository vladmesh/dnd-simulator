# E2E Report: Sprint 023 post-audit

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** targeted 1, 2, 3, 6, 10, 13, 14, 15
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 11 tested, 10 passed, 1 failed
- Quick fixes: 0 applied
- Blockers: 1 found

## Results

### Session setup and player flow

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page Player/DM split | pass | Both cards navigate to `/play` and `/master`. |
| 1.2, 1.4, 1.5 | Fighter creation | pass | Sword Vale session created with Human Fighter, STR 15, CON 14, Defense; UI showed HP 12, AC 19 and expected starting equipment. |
| 1.3 | Language selector | pass | EN/RU controls were visible throughout the player and Master views. |
| 2.1, 2.3 | Peaceful nearby and wait | pass | Nearby NPC controls were shown; Wait advanced time from 10:00 to 11:00. |
| 3.1, 3.2, 3.4 | Combat lifecycle | pass | Player attack emitted typed combat start, attack, death, reputation, and combat-ended messages; the UI returned to peaceful mode and exposed loot. |
| 13.2 | Reputation write-back | pass | Killing Marta changed Kingdom Forces reputation from 100 to 80 in the live log. |
| 15.1 | Loot surface after death | pass | Marta was listed in Loot with Take all and Empty controls. |

### Master panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds list | pass | Library/editable world controls rendered, including the expected fork/delete distinction. |
| 6.5 | Sessions list and management | pass | The newly created live session appeared with its player and world, and Manage opened the session controls. |
| 6.6–6.11 | Master control surfaces | pass | Creatures, Time, Saves, and Live panes loaded; creature rows exposed AI/activity controls, Time exposed Advance, Saves exposed Save/Load, and Live waited for events. |

### Paladin

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 14.1 | Paladin character creation | fail | After selecting Paladin, the creation form removes the Fighting Style selector. The playbook requires Defense, Dueling, and Great Weapon Fighting at L1, so the scenario cannot be completed. |

## Findings

### Minor

- In an EN player session, nearby creature race content displayed as `человек`. This is the declared non-blocking `DND_LANGUAGE` content-name contract from Sprint 023 Phase 7, not a session-locale regression.

### Blockers

- Paladin L1 creation has no Fighting Style selector. This violates playbook scenario 14.1 and blocks the Level 2/Divine Smite follow-up scenarios, so the run cannot establish post-audit E2E readiness.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` contained no error, exception, or traceback lines.
- Browser reported no console errors and one benign closed-WebSocket warning during navigation.
- Structured debug-log directory contained no unexpected error artifact.

## Scope note

The run was expanded because the checklist requires every non-LLM playbook scenario. It stopped short of the remaining dependent scenarios after the mandatory Paladin creation blocker above; the report must not be treated as a green post-audit E2E boundary.
