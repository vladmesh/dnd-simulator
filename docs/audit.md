# Code Audit

> **Date**: 2026-03-28
> **Scope**: full (post Sprint 010)

## Summary
- Dead code: 1 issue (unchanged)
- Code smells: 7 issues (6 Python + 1 frontend) — 1 resolved, 3 new
- Security: 2 issues (1 medium, 1 low) — unchanged
- Architecture violations: 3 issues — 2 new
- Convention violations: 0 issues
- Layer contract: 0 issues
- Test gaps: 2 issues — 1 new
- Vision drift: 0 issues

## Dead Code

Ruff F401 clean. Two TODOs remain relevant:
- `round.py:409` — reaction awareness (future feature)
- `rules/modifiers.py:285` — two-handed weapon exclusion (future feature)

| File | Issue | Action |
|------|-------|--------|
| `rules/conditions.py:32` | `auto_fail_str_dex_saves()` — defined but never called anywhere in codebase | backlog (needed for paralyzed/stunned conditions, D&D 5e saving throw rules — will be used when save mechanics are implemented) |

## Code Smells

| File | Lines | Issue | Suggestion |
|------|-------|-------|------------|
| `service/game_service.py` | 837 | Largest file, 43 methods | Extract command groups into separate modules (already partially done with `commands_*.py`) |
| `layers/politics/layer.py` | 615 | Large layer | Acceptable — politics has many tick sub-operations |
| `layers/entities/layer.py` | 577 | Large layer | Already factored out combat_manager, activation_manager, etc. |
| `adapters/api/routes_master.py` | 560 | Large route file, 34 routes | Consider splitting content-editing routes from session-control routes |
| `layers/entities/combat_manager.py` | 535 | Large module | Consider extracting initiative/turn logic from combat state management |
| `service/session.py` | 457 | Growing module, 27 methods — serialization + round lifecycle mixed | Extract round lifecycle or listener dispatch to separate module |
| `frontend: SchemaForm.tsx` | 488 | Large component, recursive rendering | Extract FormField/FormArray/FormObject subcomponents |

**Resolved from previous audit:** `ActionBar.tsx` decomposed from 532 → 140 lines across 9 subcomponents in sprint 010 phase 2.

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:80` | `allow_origins=["*"]` — CORS wide open | low (local dev only, must lock down before deployment) |
| `adapters/api/routes_master.py:290-330` | `get_session_state` does 7+ direct `world.query_layer()` calls with assert-based validation — a malformed layer response crashes the endpoint with AssertionError (500) instead of a clean error | medium |

No new security issues from sprint 010 — all changes were frontend decomposition and UI polish.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:290-330` | Thick adapter: `get_session_state` orchestrates 7+ layer queries directly | Extract to `GameService.get_world_state()` — adapter should call one service method | medium |
| `core/brain.py:50,63,141` | Core imports from `rules/` via lazy imports in RuleBrain methods (`calculate_direction`, `calculate_away_direction`, `get_weapon_attack`) — violates core→rules dependency direction | Move RuleBrain to `rules/` or `service/`, or inject rule functions | medium |
| `layers/entities/layer.py:465,484,490` | Layer imports from `content_loader` in `load_state` (`parse_player`, `parse_npc`, `parse_ability_scores`, `parse_attacks`) | Layers should depend on core only; content_loader is a peer module | low |

## Convention Violations

No issues. `Any` usage is limited to Pydantic validators and structlog event dicts — standard patterns.

## Layer Contract

No issues. All 5 layers implement the full Layer ABC.

## Test Gaps

| Area | Issue | Mitigation |
|------|-------|------------|
| `content_loader/` modules: `refs`, `utils`, `creatures` | No dedicated unit tests | Partially covered by integration tests (`test_catalog_assembly.py`, `test_content_api.py`, `test_library_and_assembly.py`) and parser tests. `refs` and `utils` are the least covered. |
| `service/session.py` (457 lines, 27 methods) | No dedicated unit test | Covered indirectly by `test_session_awareness.py` (awareness serialization only), `test_ws.py`, and integration tests. Round lifecycle, listener dispatch, and `resolve_abstract_move` are untested in isolation. |

Sprint 010 frontend tests added: `ActionButton.test.tsx`, `BattleMapInspect.test.tsx`, `drawers.test.tsx`, `CreatureForm.test.tsx`, `CreatureList.test.tsx`. Good coverage of decomposed components. Unit test count: 1452 tests, all passing.

## Vision Drift

No drift. Sprint 010 changes: phase 1 fixed UX bugs from sprint 009 E2E report (combat log i18n, click-to-inspect, master panel polish); phase 2 decomposed ActionBar.tsx. All UI/UX work — no mechanics changes. Classic mode, single global round, brain swappability, layer independence all preserved.
