# Task: E2E — Fork, Edit YAML, Create Session, Verify Changes

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 4 — Layer Editor

## Description

End-to-end test: fork a layer via MasterScreen, edit its YAML through the layer editor, create a new session, and verify the edited content is reflected in the running game.

## Tests First

Playwright E2E scenarios added to the E2E suite:

1. **Fork → Edit → Session** (happy path):
   - Navigate to /master, select world
   - Fork the entities layer (click Fork button)
   - Click "Edit" on the now-custom entities layer
   - Select npcs.yaml from file tabs
   - Change an NPC's name in the YAML (e.g. rename "Captain Elena" to "Captain Modified")
   - Click Save, verify success feedback
   - Create a new session from this world
   - Open god-mode session view, verify the NPC has the modified name

2. **Edit validation error**:
   - Open editor on a custom layer
   - Enter invalid YAML (e.g. unmatched brackets)
   - Click Save
   - Verify error message appears with YAML parse details
   - Verify original file content is unchanged (reload and check)

3. **Library layer is read-only**:
   - Navigate to /master, select a world with library layers
   - Verify library layers show "View" (not "Edit")
   - Click "View" on a library layer
   - Verify editor opens in read-only mode (no Save button or Save disabled)

## Implementation

Add scenarios to the E2E playbook and implement in Playwright. Reuse existing E2E patterns for /master navigation and session creation.

## Acceptance Criteria

- [ ] All 3 E2E scenarios pass
- [ ] No regressions in existing E2E scenarios
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
