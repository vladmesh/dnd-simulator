# Code Audit

> **Date**: 2026-04-12
> **Scope**: full (post Sprint 015)

## Summary
- Dead code: 1 issue
- Code smells: 7 issues
- Security: 6 issues
- Architecture violations: 4 issues
- Convention violations: 7 issues
- Layer contract: 0 issues
- Test gaps: 7 issues
- Vision drift: 0 issues

## Dead Code

Sprint 015 wired `reset_resources()` (now used in `rules/handlers/rest.py` for long/short rest actions). No new dead code introduced.

**Backlog** (tested but unwired — future mechanics):

| File | Function | Notes |
|------|----------|-------|
| `rules/reactions.py:15` | `can_opportunity_attack()` | Duplicates eligibility checks inline in `find_oa_triggers()`. 0 prod callers. |
| `rules/conditions.py:27` | `prone_stand_cost()` | Only called in tests. Wire when prone mechanic lands. |
| `rules/movement.py:201` | `walk_path()` | 12 test refs, 0 prod. Budget-aware path walking. |
| `core/turn_budget.py:58` | `refund()` | 1 test ref, 0 prod. |
| `core/player.py:73` | `to_save_data()` | 1 test ref, 0 prod. |
| `rules/geography.py:172` | `is_daylight()` | 5 test refs, 0 prod. Day/night cycle. |
| `core/models.py:189` | `TimeDelta.from_days()` | 7 test refs, 0 prod. Harmless convenience. |

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `service/game_service.py` (936 lines, 44+ methods) | God class mixing session mgmt, content CRUD, catalog CRUD, entity CRUD | Split into focused service classes by domain |
| `round.py` (622 lines) | Round orchestrator with `run_combat_turn` (69 lines) and `run_peaceful_turn` (68 lines) | Extract combat-turn and awareness-building into helpers |
| `layers/entities/layer.py` (597 lines) | Large layer delegating to 5 sub-managers | Acceptable given decomposition, but monitor |
| `adapters/api/routes_master.py` (560 lines, 40+ routes) | Oversized route module | Split by domain (sessions, creatures, world editing, saves) |
| `core/action_defs.py` (538 lines) | Large action registry — grew with paladin/smite/rest actions | Registry pattern is fine, but consider data-driven YAML format |
| `service/session.py` (517 lines) | Session + GameSession + player brain callback logic | Extract player brain callbacks to own module |
| `frontend/src/components/master/SchemaForm.tsx` (488 lines) | Large component with inline sub-components | Extract `ArrayOfObjectsField` and field renderers |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:85-89` | CORS wildcard `allow_origins=["*"]` — any site can make cross-origin requests | medium |
| All API endpoints | Zero authentication on REST and WebSocket — session_id (8-char hex) is the only guard | medium |
| `adapters/api/routes_ws.py:90-95` | WS origin check disabled by default (`WS_ALLOWED_ORIGINS` defaults to empty) | low |
| `llm/brain.py`, `llm/prompts.py` | Player speech flows unsanitized into LLM prompts — no injection mitigation (blast radius limited: tool-call-only output) | low |
| `service/game_service.py:81` | `world_name` from request used in path construction without regex guard at call site | low |
| `adapters/api/routes_ws.py:164` | WS `params` dict passed without schema validation to action handlers | low |

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:290-334` | Thick adapter: `get_session_state()` orchestrates 8+ layer queries inline | Single `service.get_world_state(session_id)` call | medium |
| `round.py:31` | `Round` directly imports `EntitiesLayer` (service → layer coupling) | Interact via World/Layer interface | medium |
| `adapters/api/routes_player.py:13-16` | Imports `Ability`, `PlayerCharacter` from core and `POINT_BUY_BUDGET`, `STARTING_GOLD` from rules | Expose setup config through service layer | low |
| `llm/brain.py:49`, `llm/summarizer.py:10` | Imports layer-specific models (`Npc`, `NpcMemory`) | Pass data through interface, not concrete layer type | low |

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| 30 files across codebase | `Any` in type annotations (30 files import `Any`) | Use `object` not `Any` (CLAUDE.md) for state dicts |
| `layers/geography/models.py:35` | `Region` — `@dataclass` without `frozen=True` | Frozen for pure data models |
| `layers/politics/models.py:29,38` | `Leader`, `Nation` — mutable dataclass | Frozen or justify mutation |
| `layers/settlements/models.py:17` | `Settlement` — mutable dataclass | Frozen or justify mutation |
| `tests/unit/test_api.py`, `tests/unit/test_trade_ws.py` | Bare `200`/`404` instead of `HTTPStatus` | Use `HTTPStatus.OK` etc. |
| `rules/proficiency.py:33-34` | Hardcoded weapon name strings (`"rapier"`, `"shortsword"`) | Use enum or catalog reference |
| `content_loader/`, `service/game_service.py` | 31+ `.get()` with silent defaults at data boundaries | Fail fast on missing keys; use `data["key"]` |

## Layer Contract

All 5 layers (Geography, Politics, Settlements, Ecology, Entities) implement the full Layer ABC. **No issues.**

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/weapons.py` | `test_rules_weapons.py` | missing (indirect coverage via other tests) |
| `rules/handlers/equipment.py` | `test_handlers_equipment.py` | missing (covered by `test_action_dispatcher.py` — 15 tests) |
| `rules/handlers/items.py` | `test_handlers_items.py` | missing (covered by `test_second_wind.py`, `test_breakdown_pipeline.py`) |
| `rules/action_provider.py` | `test_rules_action_provider.py` | missing |
| `rules/reactions.py` | `test_rules_reactions.py` | missing |
| `service/commands_politics.py` | integration/unit test | missing — 0 test references |
| `service/commands_time.py` | integration/unit test | missing — 0 test references |

**Frontend:** `clearRefCache` in `frontend/src/components/master/RefSelect.tsx:64` — exported but never imported. Dead export.

WS tests cover basic flow (10 tests) but miss: reaction prompt flow, combat-specific messages, reconnection/error handling, multi-client scenarios.

## Vision Drift

No drift detected. Sprint 015 (Paladin & Divine Smite) aligns with all invariants:
- Classic mode works without LLM — divine smite, spell slots, and rest actions are pure rule functions; RuleBrain handles smite decisions
- Single global round — no changes to round structure
- Layers independent — no new cross-layer coupling
- Master controls through endpoints only
- Brain swappable at runtime — smite choice routed through `Brain.choose_reaction` pattern; both RuleBrain and LlmBrain handle it
- Content is data — paladin features defined via `PaladinFeatures` dataclass + YAML catalogs
