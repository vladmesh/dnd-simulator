# Phase 2 E2E Report

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 2 — Adapter & Routes

## New Functionality Tested

Phase 2 was a pure backend refactor — no new UI features. Verification targets:
1. REST routes preserved after `routes_master.py` split into `routes_world` + `routes_session`.
2. `get_session_state()` moved to `GameService` still serves dashboard.
3. WebSocket turn flow intact.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| `GET /openapi.json` lists all `/api/master/*` + `/api/player/*` paths | 34 paths including sessions, worlds, catalogs, saves | All present | pass |
| Load world list at `/play` | Sword Vale + Test Vale shown | Both worlds rendered | pass |
| Create session (Test Vale) | Session ID returned, character creation screen opens | Session `b1e0d182` created, char form loaded with 27-pt buy + Fighting Style selector | pass |
| Create Fighter char (Defense style) | HP 10, AC 18, dashboard opens via WS | Dashboard renders with Adventurer 10/10, banner "The Dusty Flagon", action bar live | pass |
| Action bar turn flow (Attack→End Turn) | Turn events flow via WS, actions acknowledge | Attack activated, End Turn dispatched, no WS drop | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world list | pass | |
| Start session + join as player | pass | Session state hydrated via new extracted command |
| WS turn events | pass | Turn received after char creation, ends cleanly |

## Quick Fixes Applied

None.

## Log Analysis

- `/tmp/dnd-e2e-logs/session_b1e0d182/full.jsonl` — no errors, no exceptions, no WARN-level findings outside expected `action_failed` info warnings.
- Backend `backend.log` clean on startup; no import-order issues after route module split.

## Blockers

None.

## Minor Issues

- **Integration test flakiness:** First `make test-integration` run showed 2 WebSocket-timeout failures (`test_oa_triggers_on_leaving_reach`, `test_attack_event_has_structured_dice`). Two consecutive re-runs: 134/134 green. Failures are transient WS receive timeouts, not tied to phase 2 changes (routes module did not alter WS handler). Leave as pre-existing flakiness; not blocking.
- `/play` dashboard still renders a "1" button on Fighter action bar (Second Wind counter). Behavior matches phase 1 closure; not in scope for phase 2.
