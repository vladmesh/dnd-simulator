# E2E Report: sprint020-phase1

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** 1 (landing/setup) + Phase 1 identity scenarios + peaceful regression (2.1, 2.3)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 8 tested, 8 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

Phase 1 deliverable is the identity request-seam plus its front selector/propagation. Focus was the
new selector + header/WS-param plumbing, then a peaceful regression to prove the propagation didn't
break the normal player flow.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Play/DM split + new identity selector | pass | Both cards present. New identity row: name textbox (placeholder «ваше имя») + role combobox (Создатель миров / Мастер / Админ / Игрок, default Игрок). All RU, no key/ID leaks. |
| 1.2 | Quick start — pick world, create character, enter game | pass | Sword Vale → Новая сессия (66189ec1) → Fighter/Human/Defense → game loads. AC 19 (Chain Mail 16 + Shield 2 + Defense 1), HP 10/10, equipment Chain Mail/Longsword/Shield. Done with identity (alice/dm) active. |

### Auto-discovered scenarios (Phase 1 identity)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Selector sets identity → localStorage | new `identitySlice` + LandingPage selector | pass | After name «alice» + role «Мастер», `localStorage.identity == {"userId":"alice","role":"dm"}`. |
| HTTP header propagation | `apiClient.request()` injects `X-User-Id`/`X-Role` | pass | `GET /api/master/worlds?lang=ru` request-headers on the wire: `x-user-id: alice`, `x-role: dm`. |
| WS param propagation | `wsClient.doConnect()` appends `user_id`/`role` | pass | uvicorn access log: `WebSocket /api/ws/66189ec1?player_id=player_055ed3d8&user_id=alice&role=dm [accepted]`. |
| Persistence / rehydrate across reload | slice rehydrates via `loadIdentity()` | pass | Full page reload of `/` → textbox shows «alice», combobox «Мастер» selected. |
| Session create with identity (created_by path) | task 2 stamps `meta.created_by` | pass | Session created cleanly with `X-User-Id: alice` present; player flow unaffected. |

### Section 2: Peaceful Mode (regression with identity active)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC «marta» (человек) visible in «Поблизости» with Атаковать/Говорить/Inspect. |
| 2.3 | Wait → time advance (WS action round-trip) | pass | «Ждать» advanced time Y1490 M6 D1 10:00 → 11:00 over the WS that carries the identity params. |

## Quick Fixes

- None.

## Findings

### Blockers
- None.

### Minor
- **Pre-existing (not introduced by Phase 1):** React StrictMode double-mount opens a first WS that is
  closed before it establishes, producing one console warning (`WebSocket is closed before the
  connection is established`) and a `session_empty_evict` on first mount. The second WS connects and
  the session works (time advance confirmed). This is exactly the `session-disconnect-debounce` issue
  scheduled for Phase 3. The failing URL still shows `user_id=alice&role=dm`, reconfirming the params.

## Log Analysis

- Backend: no ERROR / exception / traceback. `listener_error` count 0 this run.
- Console: 0 errors, 1 warning (the StrictMode WS artifact above).
- Integration suite (run in close-phase step 2): 157 passed, including 3 new `test_identity_seam.py`
  tests (invalid X-Role → 400, X-User-Id → world `creator`, header-less → creator "local").
