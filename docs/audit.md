# Code Audit

> **Date**: 2026-03-26
> **Scope**: full (post Sprint 006 Phase 4)

## Summary
- Dead code: 0 new issues (4 backlog stubs from prior audit still valid)
- Code smells: 0 new issues (8 prior items in backlog still valid)
- Security: 0 new issues (9 prior items in backlog still valid)
- Architecture violations: 0 new issues (prior items tracked)
- Convention violations: 0 new issues
- Layer contract: 0 issues
- Test gaps: 0 new (12 prior gaps still in backlog)
- Vision drift: 0 issues

Sprint 006 introduced library templates, manifest-based loading, world assembly API, and a frontend WorldBuilder wizard. All new code is clean: proper module boundaries, no new `Any` types, no architecture violations, full test coverage for backend (unit + integration). Frontend has no test runner but was E2E verified via Playwright.

## Dead Code

No new dead code. Prior backlog stubs still valid:
- `rules/conditions.py:32` `auto_fail_str_dex_saves()` — future saving throw system
- `core/brain.py:59` `move_away_from_target()` — future movement AI
- `core/turn_budget.py:54` `refund()` — future reaction system
- `round.py:302` `check_reactions()` — stubbed reaction system

TODOs (legitimate, keeping):
- `round.py:387` — reaction awareness list
- `rules/modifiers.py:285` — two-handed weapon exclusion

## Code Smells

No new smells. `routes_master.py` grew to 400 lines with library/assembly endpoints (was ~330). Still flat structure, no deep nesting — not actionable yet but approaching the threshold for splitting into separate route modules.

Prior backlog items (8) unchanged — `layers/entities/layer.py`, `layers/politics/layer.py`, `round.py`, etc.

## Security

No new security issues. Sprint 006 adds library browsing and world assembly — both read-only or create-only operations, no new attack surface.

Prior 9 issues unchanged (CORS wildcard, no auth, no WS message limits, etc.).

## Architecture Violations

No new violations. Prior items:
- `round.py:29` imports `EntitiesLayer` directly (medium, tracked)
- `routes_master.py:25` imports `Query`/`QueryType` from core (low, adapter uses them for god-mode query)
- `routes_ws.py:28` imports `Action`/`ActionType` from core (low, WS constructs actions from client JSON)
- `routes_player.py:10-11` imports `Ability`/`PlayerCharacter` from core (low)

New `content_loader/` modules (assembly.py, library.py, manifest.py) have clean imports — only from within `content_loader/` package plus stdlib.

## Convention Violations

No new violations. `Any` usage in `core/models.py:6` tracked from prior audit.

## Layer Contract

All 5 layers implement the Layer ABC fully. No changes to layer implementations in sprint 006.

## Test Gaps

No new gaps. All sprint 006 backend modules have corresponding tests:
- `test_library_catalog.py` — 13 tests for library.py
- `test_library_structure.py` — 17 tests for metadata files
- `test_manifest_resolver.py` — 13 tests for manifest.py
- `test_manifest_game_service.py` — 16 tests for service integration
- `test_world_assembly.py` — 17 tests for assembly.py
- `test_library_and_assembly.py` (integration) — 17 tests for API endpoints

Prior 12 test gap items unchanged.

## Vision Drift

No drift. Sprint 006 reinforces core vision principles:
- **Content is data**: worlds are now composable from YAML library templates
- **Classic mode works without LLM**: library/assembly flow is entirely rule-based
- **Layers are independent**: each layer template is a standalone unit; worlds compose 5 independent templates
- **Master controls through endpoints**: assembly/fork operations go through GameService
