# Task: E2E — Master Spawns Creature, Gives Item, Verifies Equipment

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 2 — Master Controls + Give Item UI

## Description

Playwright E2E scenario covering the master workflow end-to-end:

1. Navigate to master screen, create a session.
2. Open creature management.
3. Spawn a new creature (monster type, with basic stats).
4. Verify it appears in the creature list.
5. Open the creature for editing.
6. Give it a weapon via the Give Item dialog.
7. Verify the weapon appears in the creature's inventory display.
8. Give it a potion.
9. Verify the potion appears in inventory.
10. Delete the creature, verify it's gone.

This covers the full give_item flow plus validates existing spawn/edit/delete still work.

## Tests First

This IS the test — E2E is the verification layer for this phase.

## Implementation

- Add a new scenario to the E2E playbook in `docs/e2e-playbook.md` (or extend existing master section).
- Write Playwright test script following project conventions (check existing E2E tests for patterns).
- Run against live dev stack (`make serve` + `make frontend`).

## Acceptance Criteria

- [ ] E2E scenario passes on green dev stack
- [ ] Covers: spawn creature → give weapon → give potion → verify inventory → delete creature
- [ ] Report written to `docs/e2e-reports/`
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
