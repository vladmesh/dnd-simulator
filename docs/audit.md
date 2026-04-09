# Code Audit

> **Date**: 2026-04-09
> **Scope**: full (post Sprint 013)

## Summary
- Dead code: 1 issue
- Code smells: 10 issues
- Security: 6 issues
- Architecture violations: 5 issues
- Convention violations: 8 issues
- Layer contract: 0 issues
- Test gaps: 8 issues
- Vision drift: 0 issues

## Dead Code

All 8 dead-code items from the previous audit (2026-03-31) have been removed. No new dead code introduced in sprint 013.

**Backlog** (tested but unwired — future mechanics):

| File | Function | Notes |
|------|----------|-------|
| `rules/reactions.py:15` | `can_opportunity_attack()` | Duplicates eligibility checks inline in `find_oa_triggers()`. 0 prod callers. Consider removing or having `find_oa_triggers` call it. |
| `rules/conditions.py:27` | `prone_stand_cost()` | Only called in tests. Wire when prone mechanic lands. |
| `rules/resources.py:32` | `reset_resources()` | 12 test refs, 0 prod. Wire with rest mechanics. |
| `rules/movement.py:201` | `walk_path()` | 12 test refs, 0 prod. Budget-aware path walking. |
| `core/turn_budget.py:58` | `refund()` | 1 test ref, 0 prod. |
| `core/player.py:73` | `to_save_data()` | 1 test ref, 0 prod. |
| `rules/geography.py:172` | `is_daylight()` | 5 test refs, 0 prod. Day/night cycle. |
| `core/models.py:189` | `TimeDelta.from_days()` | 7 test refs, 0 prod. Harmless convenience. |

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `service/game_service.py` (936 lines, 44+ methods) | God class mixing session mgmt, content CRUD, catalog CRUD, entity CRUD | Split into focused service classes by domain |
| `layers/politics/layer.py` (615 lines) | Large layer implementation | Extract sub-components (diplomacy, warfare, economy) |
| `round.py` (612 lines) | Round orchestrator doing too much | Extract combat-turn and awareness-building into helpers |
| `layers/entities/combat_manager.py` (604 lines) | Large combat module | Consider splitting initiative/damage/state transitions |
| `adapters/api/routes_master.py` (560 lines, 40+ routes) | Oversized route module | Split by domain (sessions, creatures, world editing, saves) |
| `perception.py` (54 `.get()` calls with silent defaults) | Systematic fail-fast violation — masks missing event data with `""`, `0`, `"?"` | Use `data["key"]` — crash on missing keys |
| `awareness_builder.py` (7 broad `except Exception` blocks) | Swallows bugs, replaces real data with hardcoded fallbacks like `{"condition": "clear", "temperature": 15}` | Remove catch-alls or narrow to specific expected exceptions |
| `core/brain.py:165` | `RuleBrain._choose_combat_action` is 131 lines of if/elif chain | Decompose into strategy sub-methods or decision table |
| `layers/entities/perception.py:38-93` | 55-line if/elif chain mapping EventType to handlers | Replace with dispatch dict |
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
| `adapters/api/routes_player.py:12-13` | Imports `Ability`, `PlayerCharacter` from core for response building | Build response dict in service layer | low |
| `llm/brain.py:49`, `llm/summarizer.py:10` | Imports layer-specific models (`Npc`, `NpcMemory`) | Pass data through interface, not concrete layer type | low |
| `rules/dice.py:9,15-16` | `import os` + `os.environ.get("DND_DICE_SEED")` at import time | Inject seed via parameter or factory | low |

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| 30 files across codebase | `Any` in type annotations (30 files import `Any`) | Use `object` not `Any` (CLAUDE.md) for state dicts |
| `layers/geography/models.py:35` | `Region` — `@dataclass` without `frozen=True` | Frozen for pure data models |
| `layers/politics/models.py:29,38` | `Leader`, `Nation` — mutable dataclass | Frozen or justify mutation |
| `layers/settlements/models.py:17` | `Settlement` — mutable dataclass | Frozen or justify mutation |
| `tests/unit/test_api.py`, `tests/unit/test_trade_ws.py` | Bare `200`/`404` instead of `HTTPStatus` | Use `HTTPStatus.OK` etc. |
| `rules/proficiency.py:33-34` | Hardcoded weapon name strings (`"rapier"`, `"shortsword"`) | Use enum or catalog reference |
| `layers/entities/perception.py:29-31` | Hardcoded weapon names duplicated from YAML catalogs | Reference catalog data |
| `content_loader/`, `service/game_service.py` | 31+ `.get()` with silent defaults at data boundaries | Fail fast on missing keys; use `data["key"]` |

## Layer Contract

All 5 layers (Geography, Politics, Settlements, Ecology, Entities) implement the full Layer ABC: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. **No issues.**

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
| `service/commands_save.py` | dedicated unit test | missing — only integration coverage via REST |

**Frontend:** `clearRefCache` in `frontend/src/components/master/RefSelect.tsx:64` — exported but never imported. Dead export.

WS tests cover basic flow (10 tests) but miss: reaction prompt flow, combat-specific messages, reconnection/error handling, multi-client scenarios.

## Vision Drift

No drift detected. Sprint 013 (character creation overhaul) aligns with all invariants:
- Classic mode works without LLM — point buy and HP formulas are pure rule functions
- Single global round — no changes to round structure
- Layers independent — no new cross-layer coupling
- Master controls through endpoints only
- Brain swappable at runtime — character creation doesn't touch brain logic
- Content is data — starting equipment defined in rules, resolved from YAML catalogs
