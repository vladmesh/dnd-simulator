# Task: E2E — Fork Workflow via Master Screen

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 3.5 — Move Fork UI to Master Screen

## Description

End-to-end verification that the fork workflow works through `/master` screen and that the player setup screen is clean (no layer management UI).

## Tests First

### Scenarios

1. **Player setup screen is clean** — Navigate to `/`. Assert: world cards show "New Session" button only, no "Layers" button, no layer inspector.
2. **Master screen shows layer inspector** — Navigate to `/master`. World selector defaults to first world. Assert: 5 layer rows visible with source badges.
3. **Fork from master screen** — Click Fork on a library layer. Assert: layer shows "Custom", fork button disappears.
4. **Fork persists on reload** — Reload `/master`. Assert: forked layer still shows "Custom".
5. **Session creation still works** — From `/`, click "New Session" on a world. Assert: redirected to character creation.

## Implementation

Run scenarios via Playwright MCP against live stack. Write report to `docs/e2e-reports/`.

## Acceptance Criteria

- [ ] All 5 scenarios pass
- [ ] Report written to `docs/e2e-reports/`

## Status

`pending`
