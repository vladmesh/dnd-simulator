# E2E Report: sprint019-phase1

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** focused smoke — 1 (setup), 2.3 (time/listener), 6.1/6.4-world/6.6/6.12 (master + SchemaForm), 10.2 (log)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Scope rationale

Phase 1 is a unit-test-net phase. Runtime-affecting changes since the last report
(`2026-06-28-sprint018-post-audit`) are narrow:

- `service/commands_world_state.py` — `get_world_state` asserts → typed `RuntimeError`
  fail-fast (happy path unchanged). Surfaced in the master SessionView "World" tab.
- `frontend/.../master/SchemaForm.tsx` — memoized `rootDefs`/`props` (identity-only;
  clears two `exhaustive-deps` warnings). Drives master content forms (Give Item, etc.).
- `service/session.py` — listener-dispatch / round-lifecycle **tests only**, no behaviour
  change. Exercised by entering a game + the turn loop.

E2E targeted exactly these surfaces plus a basic regression. No LLM scenarios.

## Summary

- Scenarios: 9 tested, 9 passed (1 with a pre-existing UX caveat)
- Quick fixes: 0
- Blockers: 0

## Results

### Section 1 — Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing Player/DM split | pass | Both cards + EN/RU toggle |
| 1.2 | Quick start → create char → enter game | pass | Session `4e2634f8`, WS connected, player turn delivered (action bar active) |
| 1.4 | Point buy | pass | Cap enforced (STR + disabled at 15), remaining 3/27 |
| 1.5 | Class-specific UI | pass | Fighter → Fighting Style selector; Defense → AC 19 (16 chain + 2 shield + 1) , HP 12 (d10+CON 2) |

### Section 2 — Peaceful

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.3 | Wait / time advance | pass | 10:00 → 11:00, action bar refreshed — listener round-trip intact |

### Section 6 — Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | editable (Fork+Delete) vs library (Fork only) |
| World tab (get_world_state) | SessionView world snapshot | pass | **Main backend change** — 7 regions+weather, 3 nations, 10 settlements render correctly, no raw-ID leak, no error. Validates assert→raise refactor happy path. |
| 6.6 | Spawn creature | pass* | Spawned `goblin_test` once a valid Role given. *See finding F1. |
| 6.12 | Give item (weapon) — **SchemaForm** | pass | "Test Sword" added to goblin inventory, form stayed open. Confirms memoized SchemaForm renders + submits correctly. |

### Section 10 — Dashboard

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.2 | Expand log overlay | pass | Overlay opens; "Waiting for events…" (peaceful Wait emits no log entry — consistent with prior behaviour) |

## Findings

### Blockers
- None.

### Minor (all pre-existing, none from this phase)

- **F1 — Spawn-creature Role is a free-text field but backend requires an enum.**
  Spawning an NPC with an empty (or arbitrary) Role returns HTTP 400 with a *raw Pydantic*
  message rendered in the dialog: `Input should be 'commoner', 'blacksmith',
  'tavern_keeper', 'guard', 'merchant', 'farmer' or 'gladiator'`. Works with a valid value.
  The Role field should be a dropdown of the `NpcRole` enum (and/or the error mapped to a
  friendly i18n toast). In the hand-built spawn dialog (`CreatureForm`), unrelated to the
  `SchemaForm` change. Candidate for the phase-3 visible-gaps backlog.

- **F2 — Mixed UI language: NPC race shows `человек` (RU) while chrome + location text are
  EN.** Frontend i18n defaults EN; backend game language (`DND_LANGUAGE`) defaults `ru`, so
  perceived content (race) comes back Russian. Pre-existing split, not a phase-1 regression.

- **F3 — Dev-only WS race on first turn.** One `listener_error` on
  `WsEventListener.on_turn` at the very first turn, paired with console warning
  "WebSocket is closed before the connection is established". This is the React StrictMode
  dev double-mount (first socket torn down + reconnected). The session listener dispatch
  **correctly isolated the error** — the game continued and all later turns delivered. No
  occurrence in production builds (no StrictMode double-mount). Notably this exercised the
  exact listener-error isolation that phase-1 task-1 added a test net for.

## Log Analysis

- Backend HTTP: only one non-2xx — the F1 400 on creature spawn. No 5xx, no tracebacks.
- Structured logs (`session_4e2634f8`): one error-level event, the F3 `listener_error`.
- `get_world_state` served multiple 200s; no malformed-layer `RuntimeError` triggered
  (expected — happy path).
