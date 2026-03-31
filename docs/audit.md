# Code Audit

> **Date**: 2026-03-31
> **Scope**: full (post Sprint 012)

## Summary
- Dead code: 8 issues
- Code smells: 12 issues
- Security: 6 issues
- Architecture violations: 5 issues
- Convention violations: 8 issues
- Layer contract: 0 issues
- Test gaps: 12 issues
- Vision drift: 0 issues

## Dead Code

| File | Issue | Action |
|------|-------|--------|
| `content_loader/schemas.py:117` | `WeaponDefContent` class — zero references | remove |
| `content_loader/schemas.py:136` | `ArmorDefContent` class — zero references | remove |
| `content_loader/schemas.py:146` | `ShieldDefContent` class — zero references | remove |
| `content_loader/schemas.py:153` | `AccessoryDefContent` class — zero references | remove |
| `core/brain.py:80` | `RuleBrain.move_away_from_target()` — zero callers | remove |
| `core/character.py:204` | `on_tick()` — empty hook, never called, no overrides | remove |
| `service/game_service.py:782` | `_require_player()` — private, zero callers | remove |
| `rules/conditions.py:32` | `auto_fail_str_dex_saves()` — zero callers, zero tests | remove |

**Backlog** (tested but unwired — future mechanics):

| File | Function | Notes |
|------|----------|-------|
| `rules/reactions.py:15` | `can_opportunity_attack()` | 11 test refs, 0 prod. Wire when OA ships. |
| `rules/conditions.py:27` | `prone_stand_cost()` | 4 test refs, 0 prod. |
| `rules/resources.py:32` | `reset_resources()` | 12 test refs, 0 prod. Rest mechanics. |
| `rules/movement.py:201` | `walk_path()` | 12 test refs, 0 prod. Path budget. |
| `core/turn_budget.py:58` | `refund()` | 1 test ref, 0 prod. |
| `core/player.py:73` | `to_save_data()` | 1 test ref, 0 prod. Verify if save system uses this. |
| `rules/geography.py:172` | `is_daylight()` | 5 test refs, 0 prod. Day/night cycle. |
| `core/models.py:189` | `TimeDelta.from_days()` | 7 test refs, 0 prod. Harmless convenience. |

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `service/game_service.py` (861 lines, 44 methods, 33 inline imports) | God class mixing session mgmt, content CRUD, catalog CRUD, entity CRUD | Split into focused service classes by domain |
| `perception.py` (54 `.get()` calls with silent defaults) | Systematic fail-fast violation — masks missing event data with `""`, `0`, `"?"` | Use `data["key"]` — crash on missing keys |
| `awareness_builder.py` (7 broad `except Exception` blocks) | Swallows bugs, replaces real data with hardcoded fallbacks like `{"condition": "clear", "temperature": 15}` | Remove catch-alls or narrow to specific expected exceptions |
| `core/brain.py:165` | `RuleBrain._choose_combat_action` is 131 lines of if/elif chain | Decompose into strategy sub-methods or decision table |
| `service/session.py:342` | `start_round()` is 116 lines with 4 inline closures sharing near-identical serialization logic | Extract shared event-builder method |
| `round.py:210` | `run_combat_turn` is 137 lines | Extract awareness-building and action-execution into helpers |
| `adapters/api/routes_master.py` (560 lines, 40+ routes) | Oversized route module | Split by domain (sessions, creatures, world editing, saves) |
| `layers/entities/perception.py:38-93` | 55-line if/elif chain mapping EventType to handlers | Replace with dispatch dict |
| `service/session.py:342-456` | 4 closures with duplicated serialization pattern | Extract `_awareness_to_dict`, `_events_to_list` into shared method |
| `world._make_query_fn` accessed from `session.py` and `round.py` | Private method used across module boundaries | Expose as public API on World |
| `dict[str, object]` used extensively as poor man's type | 57+ occurrences across query_handler, game_service, combat_manager, schemas | Replace with TypedDict or dataclass where structure is known |
| `frontend/src/components/master/SchemaForm.tsx` (488 lines) | Large component with many inline helpers | Extract field-type renderers into separate components |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:79-82` | CORS wildcard `allow_origins=["*"]` — any site can make cross-origin requests | medium |
| All API endpoints | Zero authentication on REST and WebSocket — session_id (8-char hex) is the only guard | medium |
| `adapters/api/routes_ws.py:91` | WS origin check disabled by default (`WS_ALLOWED_ORIGINS` defaults to empty) | low |
| `llm/brain.py:86-89`, `llm/prompts.py:46` | Player speech flows unsanitized into LLM prompts — no injection mitigation (blast radius limited: tool-call-only output) | low |
| `service/game_service.py:87` | `world_name` from request used in path construction without regex guard (`_validate_world_id` exists but not called here) | low |
| `adapters/api/routes_ws.py:164` | WS `params` dict passed without schema validation to action handlers | low |

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:290-334` | Thick adapter: `get_session_state()` orchestrates 8+ layer queries inline | Single `service.get_world_state(session_id)` call | medium |
| `round.py:31` | `Round` directly imports `EntitiesLayer` (service → layer coupling) | Interact via World/Layer interface | medium |
| `llm/brain.py:49` | Imports `layers.entities.models.Npc` (deferred, inside function) | Pass data through interface, not concrete layer type | low |
| `llm/summarizer.py:10` | Top-level import of `layers.entities.models.NpcMemory` | Same — llm should not depend on layer models | low |
| `rules/dice.py:9,15-16` | `import os` + `os.environ.get("DND_DICE_SEED")` at import time | Inject seed via parameter or factory | low |

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `core/models.py`, `core/player.py`, `layers/entities/models.py`, `layers/entities/activation_manager.py` | `Any` in type annotations inside core/layer code | Use `object` not `Any` (CLAUDE.md) |
| `layers/geography/models.py:35` | `Region` — `@dataclass` without `frozen=True` | Frozen for pure data models |
| `layers/politics/models.py:29,38` | `Leader`, `Nation` — mutable dataclass | Frozen or justify mutation |
| `layers/settlements/models.py:17` | `Settlement` — mutable dataclass | Frozen or justify mutation |
| `tests/unit/test_api.py` (7 lines), `tests/unit/test_trade_ws.py` (2 lines) | Bare `200`/`404` instead of `HTTPStatus` | Use `HTTPStatus.OK` etc. |
| `rules/proficiency.py:33-34` | Hardcoded weapon name strings (`"rapier"`, `"shortsword"`) | Use enum or catalog reference |
| `layers/entities/perception.py:29-31` | Hardcoded weapon names duplicated from YAML catalogs | Reference catalog data |
| `content_loader/`, `service/game_service.py` | 31+ `.get()` with silent defaults at data boundaries | Fail fast on missing keys; use `data["key"]` |

## Layer Contract
All 5 layers (Geography, Politics, Settlements, Ecology, Entities) implement the full Layer ABC: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. **No issues.**

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/action_provider.py` | `test_rules_action_provider.py` | missing |
| `rules/actions.py` | `test_rules_actions.py` | missing |
| `rules/geography.py` | `test_rules_geography.py` | missing |
| `rules/politics.py` | `test_rules_politics.py` | missing |
| `rules/reactions.py` | `test_rules_reactions.py` | missing |
| `rules/settlements.py` | `test_rules_settlements.py` | missing |
| `rules/weapons.py` | `test_rules_weapons.py` | missing |
| `rules/handlers/combat.py` | `test_handlers_combat.py` | missing |
| `rules/handlers/equipment.py` | `test_handlers_equipment.py` | missing |
| `rules/handlers/items.py` | `test_handlers_items.py` | missing |
| `rules/handlers/movement.py` | `test_handlers_movement.py` | missing |
| `rules/handlers/reactions.py` | `test_handlers_reactions.py` | missing |

WS tests cover basic flow (10 tests) but miss: reaction prompt flow, combat-specific messages, reconnection/error handling, multi-client scenarios.

## Vision Drift
No drift detected. All key invariants hold:
- Classic mode works without LLM (RuleBrain path exists for all features including reactions)
- Single global round — no parallel time streams
- Layers independent — no cross-layer imports
- Master controls through endpoints only
- Brain swappable at runtime
- Content is data (YAML)
