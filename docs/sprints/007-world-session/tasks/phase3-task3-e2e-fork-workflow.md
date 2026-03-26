# Task: E2E — Fork Workflow via World Inspector

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 3 — Fork UI + World Inspector

## Description

End-to-end test verifying the full fork workflow through the browser: navigate to setup screen, expand a world's layer inspector, fork a library layer, verify it shows as custom. Also regression scenarios for existing setup flow (world picker, session creation).

## Tests First

### New Scenarios

1. **World Inspector shows layers** — Navigate to setup screen. Click expand on a world card. Assert: 5 layer rows visible, each with a source badge. At least one shows "Library".
2. **Fork a library layer** — Expand a world's layers. Click Fork on a library layer (e.g., geography). Wait for completion. Assert: that layer now shows "Custom" badge. Fork button is gone for that layer.
3. **Forked layer persists on reload** — After forking, reload the page. Expand the same world. Assert: the forked layer still shows "Custom".
4. **Already-custom layer has no Fork button** — If a world has a custom layer (e.g., after fork), assert no Fork button appears on it.

### Regression Scenarios

5. **World picker loads and shows worlds** — Setup screen renders world cards with names.
6. **Session creation from world picker** — Click "New Session" on a world → redirected to game screen.

## Implementation

Add Playwright test file `e2e/test_fork_workflow.py` (or extend existing setup E2E if one exists). Requires live backend + frontend stack. Use the standard E2E playbook pattern.

## Acceptance Criteria

- [ ] All new E2E scenarios pass against live stack
- [ ] Regression scenarios pass
- [ ] Report written to `docs/e2e-reports/`
- [ ] No flaky tests (each scenario deterministic)

## Status

`done`

## Developer Notes

All 6 scenarios pass clean via Playwright against the live stack. Fork creates a custom geography directory and updates manifest.yaml — verified persistence across page reload. No bugs found. Forked content cleaned up after test to restore sword_vale to original state.
