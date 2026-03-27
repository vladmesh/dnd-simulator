# Code Audit

> **Date**: 2026-03-27
> **Scope**: full (post Sprint 009)

## Summary
- Dead code: 1 issue
- Code smells: 6 issues (large files — 4 Python, 2 frontend)
- Security: 2 issues (1 medium, 1 low) — unchanged from Sprint 008
- Architecture violations: 1 issue — unchanged from Sprint 008
- Convention violations: 0 issues
- Layer contract: 0 issues
- Test gaps: 1 issue
- Vision drift: 0 issues

## Dead Code

Ruff F401 clean. Two TODOs remain relevant:
- `round.py:407` — reaction awareness (future feature)
- `rules/modifiers.py:285` — two-handed weapon exclusion (future feature)

| File | Issue | Action |
|------|-------|--------|
| `rules/conditions.py:32` | `auto_fail_str_dex_saves()` — defined but never called anywhere in codebase | backlog (needed for paralyzed/stunned conditions, D&D 5e saving throw rules — will be used when save mechanics are implemented) |

## Code Smells

| File | Lines | Issue | Suggestion |
|------|-------|-------|------------|
| `service/game_service.py` | 836 | Largest file, 43 methods | Extract command groups into separate modules (already partially done with `commands_*.py`) |
| `layers/politics/layer.py` | 609 | Large layer | Acceptable — politics has many tick sub-operations |
| `layers/entities/layer.py` | 560 | Large layer | Already factored out combat_manager, activation_manager, etc. |
| `adapters/api/routes_master.py` | 554 | Large route file, 32 routes | Consider splitting content-editing routes from session-control routes |
| `frontend: ActionBar.tsx` | 532 | Large component, heavy prop drilling | Extract drawer subcomponents; consider action context |
| `frontend: SchemaForm.tsx` | 488 | Large component, recursive rendering | Extract FormField/FormArray/FormObject subcomponents |

Sprint 009 added two sizeable frontend components. Both work but would benefit from decomposition as features grow.

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:80` | `allow_origins=["*"]` — CORS wide open | low (local dev only, must lock down before deployment) |
| `adapters/api/routes_master.py:290-330` | `get_session_state` does 7+ direct `world.query_layer()` calls with assert-based validation — a malformed layer response crashes the endpoint with AssertionError (500) instead of a clean error | medium |

Rate limiting on WebSocket: present (`routes_ws.py:131`). Origin validation: present but opt-in via `WS_ALLOWED_ORIGINS` env var. No new security issues from sprint 009 — all changes were frontend layout/UI with one new backend action handler (`move_to`) that goes through standard validation pipeline.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:290-330` | Thick adapter: `get_session_state` orchestrates 7+ layer queries directly, using `Query`/`QueryType` from core | Extract to `GameService.get_world_state()` — adapter should call one service method | medium |

Note: `routes_player.py` imports `Ability` and `PlayerCharacter` from core for response serialization — borderline but acceptable since it's type-driven formatting, not business logic.

No new architecture violations from sprint 009. The `move_to` action handler follows the standard pattern: `ActionType` registered in `core/action_defs.py`, handler in `rules/handlers/`, pure pathfinding in `rules/movement.py`, dispatched by `ActionDispatcher`.

## Convention Violations

No issues. `Any` usage in `content_loader/schemas.py` is Pydantic validator signatures (`v: Any`) — standard pattern, not a convention violation. `rules/dice.py` imports `os` for `DND_DICE_SEED` env var — acceptable for test seeding.

## Layer Contract

No issues. All 5 layers implement the full Layer ABC.

## Test Gaps

| Area | Issue | Mitigation |
|------|-------|------------|
| `content_loader/` modules: `schema_gen`, `refs`, `utils`, `monsters`, `creatures`, `items` | No dedicated unit tests | Partially covered by integration tests (`test_catalog_assembly.py`, `test_content_api.py`, `test_library_and_assembly.py`) and parser tests (`test_content_parsers_creatures.py`). `schema_gen` and `refs` are the least covered — these were added in sprint 008 phase 3. |

Sprint 009 frontend tests: `GameScreen.test.tsx` (13 scenarios), `ActionBar.test.tsx`, `EventLog.test.tsx`, `logProcessing.test.ts` (335 lines). BattleMap is mocked in unit tests but covered by WebSocket integration tests and E2E. WebSocket coverage remains solid: 12 unit tests + 12 integration tests.

## Vision Drift

No drift. Sprint 009 changes are purely UI (dashboard layout, log formatting, action bar, NPC inspect, battle map). All mechanics untouched. `move_to` action follows standard action pipeline. Classic mode (no LLM) unaffected. Single global round preserved. Brain swappability unchanged.
