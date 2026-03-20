# Code Audit

> **Date**: 2026-03-20
> **Scope**: full

## Summary
- Dead code: 0 issues
- Code smells: 1 issue (2 fixed, 1 deferred by design)
- Security: 0 issues
- Architecture violations: 0 issues (3 fixed)
- Convention violations: 1 issue (3 fixed, 1 deferred)
- Layer contract: 0 issues
- Test gaps: 12 issues
- **Total: 14 issues**

## Dead Code

No issues found. Ruff F401 passes clean, no stale TODOs.

## Code Smells

| File | Issue | Status |
|------|-------|--------|
| `layers/entities/layer.py` | was 557 LOC | **fixed** — extracted `combat_manager.py` (322 LOC), layer.py now 310 LOC |
| `layers/politics/layer.py` | 582 LOC | **deferred** — file is well-structured internally (`_monthly_tick` orchestrator + focused `_process_*` methods, no LLM prompts despite original suggestion). Splitting would add complexity without reducing cognitive load |
| `core/character.py` | 461 LOC | **deferred** — `build_awareness`/`build_combat_awareness` are free functions, not methods. File is below 500 LOC. Revisit if it grows |
| `service.py` | 434 LOC | watch for growth |

## Security

No issues. `.env` is gitignored. No hardcoded secrets. No subprocess calls. API keys read from env vars only in adapters.

## Architecture Violations

No issues. All three `core/ → layers/` violations fixed:
- `perceive_by_id` — now uses `query_layer("entities", "perceive_entity")`
- `_knows_by_name` — duck typing via `getattr` instead of `isinstance(Npc)`
- `build_combat_awareness` — reads `is_wounded` from `entities_in_region` query data

**Rules purity**: clean. **LLM instantiation**: clean. **Cross-layer imports**: clean.

## Convention Violations

| File:Line | Violation | Status |
|-----------|-----------|--------|
| `core/models.py` | `ActionResult` not frozen | **fixed** — `frozen=True` |
| `core/models.py` | `Answer` not frozen | **fixed** — `frozen=True` |
| `service.py` | `MasterResponse` not frozen | **fixed** — `frozen=True` |
| `core/models.py:160,167` | `params: dict[str, Any]` and `value: Any` in Query/Answer | **deferred** — changing to `object` causes 58 mypy errors across 8 files; every consumer of `Answer.value` indexes/iterates it without type narrowing. Proper fix requires typed query/answer protocol or cast discipline — not a quick fix |

Note: mutable dataclasses on Entity, Creature, Character, World, CombatState, BattleMap, layer models — these are legitimately stateful, no issue.

## Layer Contract

No issues. All 4 layers (Geography, Politics, Settlements, Entities) implement the full Layer ABC.

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `core/action.py` | `tests/test_action.py` | **missing** (new file) |
| `core/models.py` | `tests/test_models.py` | **missing** |
| `core/player.py` | `tests/test_player.py` | **missing** |
| `core/world.py` | `tests/test_world.py` | **missing** |
| `llm/client.py` | `tests/test_llm_client.py` | **missing** (may need mocking) |
| `llm/prompts.py` | `tests/test_prompts.py` | **missing** |
| `storage/store.py` | `tests/test_store.py` | **missing** |
| `adapters/cli_loop.py` | — | skip (integration/UI) |
| `adapters/cli.py` | — | skip (integration/UI) |
| `content_loader.py` | `tests/test_content_loader.py` | **missing** |
| `service.py` | `tests/test_service.py` | **missing** |
| `layers/entities/` | `tests/test_entities_layer.py` | **missing** (only `test_npc_layer.py` exists, may be partial) |
