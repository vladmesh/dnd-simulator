# Task: E2E — full level-up cycle

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 3 — Level-up UI + E2E

## Description

Add a Playwright E2E scenario covering the full XP → level-up → features-applied loop and register it in the regression playbook.

Scenario (Paladin, highest payoff since it exercises the only real choice):

1. New session, create Paladin L1 with a CR ≥ 1/2 opponent within reach.
2. Kill the opponent — XP crosses 300 threshold.
3. `level_up_available` flag appears, modal auto-opens.
4. Player selects Fighting Style = Dueling, confirms.
5. Post-confirm: level 2 shown in `PlayerStats`, HP max increased, Divine Smite action available (spell slot pool appears), +2 damage with one-handed weapon (Dueling) is visible on attack breakdown in a subsequent hit.

Also cover the no-choice class:

6. Secondary check (can be combined or separate scenario): Fighter L1 kills enough XP → modal auto-opens with no dropdown → confirm → Action Surge action becomes available in the action bar.

## Tests First

No unit tests — this is a Playwright integration scenario against a live stack.

Before writing the scenario:

- Ensure Phase 3 tasks 1 & 2 are merged so the modal actually exists.
- Prepare a deterministic world/content fixture so XP math is reproducible (player starts already close to 300 XP threshold, or opponent CR is chosen to cross in one kill — preferred: CR 1/2 goblin gives 100 XP, so player starts at 201).

## Implementation

- Follow `docs/e2e-playbook.md` conventions. Use existing session-setup helpers from previous sprints' E2E (e.g. sprint 015 Paladin smite E2E under `docs/sprints/015-paladin-spell-slots/`).
- Add playbook entry: **3.5 Level-up after kill** (Russian, matching existing style) describing the Paladin scenario and the Fighter quick-check.
- Run scenario via `/e2e` or manual `make frontend` + Playwright. Store report in `docs/e2e-reports/017-phase3-level-up-<date>.md`.
- If discrepancies are found between modal behavior and backend (e.g. pool not appearing after level up), raise as blockers — do NOT patch silently.

## Acceptance Criteria

- [ ] Playbook updated with new scenario 3.5
- [ ] Scenario executed end-to-end via Playwright MCP with full debug trace
- [ ] Report written to `docs/e2e-reports/`
- [ ] All existing regression scenarios still pass (no regressions from Phase 3 UI changes)
- [ ] If blockers surface, they are logged in the report and docs/STATUS.md before the phase is considered done

## Status

`pending`
