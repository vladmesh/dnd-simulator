# Code Audit

> **Date**: 2026-03-27
> **Scope**: full (post Sprint 008)

## Summary
- Dead code: 0 issues
- Code smells: 4 issues (large files)
- Security: 2 issues (1 medium, 1 low)
- Architecture violations: 1 issue
- Convention violations: 0 issues
- Layer contract: 0 issues
- Test gaps: 1 issue
- Vision drift: 0 issues

## Dead Code

No issues. Ruff F401 clean. Two TODOs remain relevant:
- `round.py:387` — reaction awareness (future feature)
- `rules/modifiers.py:285` — two-handed weapon exclusion (future feature)

## Code Smells

| File | Lines | Issue | Suggestion |
|------|-------|-------|------------|
| `service/game_service.py` | 836 | Largest file, 43 methods | Extract command groups into separate modules (already partially done with `commands_*.py`) |
| `layers/politics/layer.py` | 609 | Large layer | Acceptable — politics has many tick sub-operations |
| `layers/entities/layer.py` | 560 | Large layer | Already factored out combat_manager, activation_manager, etc. |
| `adapters/api/routes_master.py` | 554 | Large route file, 32 routes | Consider splitting content-editing routes from session-control routes |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:80` | `allow_origins=["*"]` — CORS wide open | low (local dev only, must lock down before deployment) |
| `adapters/api/routes_master.py:290-330` | `get_session_state` does 7+ direct `world.query_layer()` calls with assert-based validation — a malformed layer response crashes the endpoint with AssertionError (500) instead of a clean error | medium |

Rate limiting on WebSocket: present (`routes_ws.py:131`). No new security issues from sprint 008.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:290-330` | Thick adapter: `get_session_state` orchestrates 7+ layer queries directly, using `Query`/`QueryType` from core | Extract to `GameService.get_world_state()` — adapter should call one service method | medium |

Note: `routes_player.py` imports `Ability` and `PlayerCharacter` from core for response serialization — borderline but acceptable since it's type-driven formatting, not business logic.

## Convention Violations

No new issues. `Any` usage in `content_loader/schemas.py` is Pydantic validator signatures (`v: Any`) — standard pattern, not a convention violation. `rules/dice.py` imports `os` for `DND_DICE_SEED` env var — acceptable for test seeding.

## Layer Contract

No issues. All layers implement the full Layer ABC.

## Test Gaps

| Area | Issue | Mitigation |
|------|-------|------------|
| `content_loader/` modules: `schema_gen`, `refs`, `utils`, `monsters`, `creatures`, `items` | No dedicated unit tests | Partially covered by integration tests (`test_catalog_assembly.py`, `test_content_api.py`, `test_library_and_assembly.py`) and parser tests (`test_content_parsers_creatures.py`). `schema_gen` and `refs` are the least covered — these were added in sprint 008 phase 3. |

WebSocket coverage is solid: 12 unit tests + 12 integration tests covering connect, disconnect, invalid messages, actions, combat, trading, equip/unequip.

## Vision Drift

No drift. Sprint 008 changes (content schema, CRUD, catalogs, DM world management) align with vision: content stays as data (YAML), master controls go through service layer, no LLM assumptions added.
