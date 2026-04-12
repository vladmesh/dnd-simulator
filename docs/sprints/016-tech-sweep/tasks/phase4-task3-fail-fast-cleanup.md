# Task: Fail-Fast Cleanup — attack target_id, autosave log, test HTTPStatus

**Date:** 2026-04-13
**Sprint:** 016-tech-sweep
**Phase:** 4 — Enums & Fail-Fast

## Description

Three small fail-fast fixes:

### 1. Attack without `target_id` — validate at dispatcher

`src/dnd_simulator/rules/handlers/combat.py:23` does `logger.info("attack", target=str(action.params["target_id"]))` before any validation — a missing `target_id` crashes with a raw `KeyError: 'target_id'` instead of a readable error. Found during E2E phase 3 (2026-04-13) when UI sends attack click without selecting a target.

Fix: validate required params in `ActionDispatcher` before handler dispatch. Each action type declares required params (either in `ActionDef` or a small dispatcher-level map). On missing param, raise `ValueError(f"Action {action_type} missing required param: {name}")`. Handlers then use `params[key]` freely.

Simpler alternative if `ActionDef` already has a `params` field: enforce at dispatcher that every declared required param is present in `action.params`.

### 2. Autosave: log + continue

`src/dnd_simulator/service/commands_save.py:41` has `contextlib.suppress(Exception)` around `autosave_session(sid)` in the shutdown autosave loop. Replace with explicit try/except + `logger.exception("autosave_failed", session_id=sid)` so failures are visible in logs. One broken session must not block saves for the others (batch semantic preserved), but silence is not OK.

### 3. Test bare status codes → HTTPStatus

`tests/unit/test_ws.py:24` and `:35` use `resp.status_code == 200`. Replace with `HTTPStatus.OK`.

## Tests First

- Integration: call ActionDispatcher with attack action that has empty `params` dict. Assert raises `ValueError` mentioning `target_id` (not `KeyError`). Creature's turn budget not consumed (existing dispatcher contract: error = no mutation).
- Integration: mock autosave_session to raise for one session out of three; assert the other two sessions are saved, and one `autosave_failed` log line emitted with matching session_id. Use structlog's capture / caplog.
- Existing test_ws.py tests still pass after HTTPStatus swap.

## Implementation

1. In dispatcher (`service/action_dispatcher.py`), after resolving `ActionDef` but before calling handler: check that required params are present. Decide where the declaration lives: if `ActionDef.params` already declares required keys, reuse. Otherwise add a minimal `required_params: tuple[str, ...]` field on `ActionDef` for now, populated at least for `ATTACK` with `("target_id",)`.
2. Remove the now-unreachable `KeyError` path from `handle_attack` (it can stay as `params["target_id"]` — guaranteed present).
3. Rewrite `autosave_all_sessions` try/except per above.
4. Edit `tests/unit/test_ws.py` two lines.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] Attack without target_id raises `ValueError` with clear message, not `KeyError`
- [ ] `contextlib.suppress(Exception)` removed from `commands_save.py`
- [ ] No bare numeric status codes left in `tests/unit/test_ws.py`
- [ ] `make check` passes

## Status

`pending`
