# Code Audit

> **Date**: 2026-03-29
> **Scope**: full (post Sprint 011)

## Summary
- Dead code: 5 issues
- Code smells: 25 issues
- Security: 11 issues
- Architecture violations: 7 issues
- Convention violations: 5 issues
- Layer contract: 1 issue
- Test gaps: 9 issues
- Vision drift: 2 issues

---

## Dead Code

| File | Issue | Action |
|------|-------|--------|
| `rules/geography.py:172` | `is_daylight()` — tested but never called from production code | backlog — wire into geography layer or remove |
| `rules/conditions.py:27` | `prone_stand_cost()` — tested but never integrated into movement handler | backlog — wire into Prone movement penalty or remove |
| `rules/conditions.py:32` | `auto_fail_str_dex_saves()` — tested but no saving throw handler exists yet | backlog — wire into saving throws when implemented or remove |
| `content_loader/items.py:228` | `parse_equipped_armor()` — superseded by `extract_all_equipped()` | remove |
| `content_loader/items.py:232` | `parse_equipped_shield()` — superseded by `extract_all_equipped()` | remove |

---

## Code Smells

### Oversized Files (>400 lines)

| File | Lines | Suggestion |
|------|-------|------------|
| `service/game_service.py` | 846 | Split `WorldCrudService` (YAML/disk) from `SessionService` (in-memory) |
| `layers/politics/layer.py` | 615 | Move `_process_economy`, `_process_wars`, `_process_diplomacy` into `PoliticsSimulator` helper |
| `layers/entities/combat_manager.py` | 590 | Extract serialization (`get_combats_state`/`load_combats_state`) into `CombatSerializer` |
| `layers/entities/layer.py` | 588 | Extract `get_state`/`load_state` (194 combined lines) into `EntitiesSerializer` |
| `adapters/api/routes_master.py` | 560 | Split by domain: `routes_worlds.py`, `routes_sessions.py`, `routes_creatures.py` |
| `round.py` | 555 | Extract awareness loop into `_build_turn_awareness()` |
| `service/session.py` | 460 | Extract 3 inline closures from `start_round` into named methods |
| `layers/entities/perception.py` | 418 | Replace event dispatch if-elif chain with `dict[EventType, handler]` lookup |
| `layers/entities/activation_manager.py` | 406 | Break out squad materialization into `_materialize_squads()` |

### Long Functions (>80 lines)

| File | Function | Lines | Suggestion |
|------|----------|-------|------------|
| `round.py` | `run_combat_turn` | 132 | Split into `_prepare_turn()` + `_run_action_loop()` |
| `layers/entities/layer.py` | `load_state` | 114 | Extract `_restore_entity()` per entity type |
| `core/brain.py` | `_choose_combat_action` | 114 | Break into per-action decision helpers |
| `service/session.py` | `start_round` | 103 | Extract closures into `_make_on_turn()`, `_make_on_action()`, `_make_on_round_end()` |
| `service/game_service.py` | `get_world_template` | 96 | Extract per-domain serializers |
| `service/game_service.py` | `start_game` | 95 | Extract `_build_layers()` |
| `rules/modifiers.py` | `attack_modifiers` | 93 | Break into `_collect_condition_modifiers()` + `_collect_equipment_modifiers()` |

### Deep Nesting (4+ levels)

| File | Function | Depth | Suggestion |
|------|----------|-------|------------|
| `layers/politics/layer.py` | `_process_diplomacy` | 7 | Extract `_check_peace()`, `_check_war_declaration()`, `_check_trade()` |
| `rules/handlers/movement.py` | `handle_wait` | 7 | Name-match fallback should raise, not silently `pass` |
| `layers/entities/layer.py` | `load_state` | 6 | Per-entity-type restore functions |
| `layers/entities/combat_manager.py` | `_check_sneak_attack` | 5 | Extract `_has_ally_adjacent()` |

### Hardcoded Strings Instead of Enums

| Location | Pattern | Suggestion |
|----------|---------|------------|
| `service/game_service.py` L535,595,611,626 | `if source == "library":` | Compare with `LayerSource.LIBRARY` enum |
| `layers/ecology/`, `combat_manager.py`, `activation_manager.py` | `str(answer.value) == "hostile"` | Return `FactionRelation` enum from query, compare directly |
| `layers/entities/layer.py`, `query_handler.py`, `commands_creatures.py` | `entity_type == "player"` / `"npc"` / `"creature"` | Add `EntityType(StrEnum)` |
| `content_loader/schemas.py`, `service/brain_factory.py` | `ai_type == "rule_based"` | Add `BrainType(StrEnum)` |

### Silent Failure / Fail-Soft Patterns

| File | Pattern | Suggestion |
|------|---------|------------|
| `service/game_service.py:215` | `contextlib.suppress(Exception)` around autosave | Log at ERROR level; don't suppress fully |
| `service/game_service.py:763` | `contextlib.suppress(Exception)` in `create_player` autosave | Same |
| `service/commands_save.py:41` | `contextlib.suppress(Exception)` | Same |
| `service/game_service.py:816` | `except Exception: return` in `_try_restore_session` | Log at WARNING with exc_info |
| `rules/handlers/movement.py` | `except ValueError: pass` in travel name-match | Return error in `ActionResult` or raise |
| `layers/entities/awareness_builder.py` | 6x `except Exception` with `logger.warning` | Use specific exceptions (`KeyError`, `LookupError`) |

### Frontend Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `components/master/SchemaForm.tsx` | 488 lines, 30+ nested helpers | Split `ArrayField`, `ObjectField`, `PrimitiveField` into separate files |
| `components/game/EventLog.tsx` | `eslint-disable-next-line react-hooks/exhaustive-deps` | Fix the actual deps |
| `transport/apiClient.ts` | 365 lines, 35+ methods on single object | Group by domain: `worldsApi`, `sessionsApi`, `creaturesApi` |
| `components/master/WorldOverview.tsx` | 331 lines, multiple sub-views inlined | Split into `WorldMap`, `NpcList`, `NationList` |

---

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `service/game_service.py:245` | `world_id` path parameter used in filesystem path construction with no sanitization — path traversal possible (`../../etc/passwd`). Fix: add `pattern=r"^[a-z0-9_]+$"` constraint like `ForkWorldRequest.id` | **high** |
| `adapters/api/routes_ws.py:161` | `msg.get("params", {})` passed as `Action.params` with zero schema validation — arbitrary nested objects pass through | medium |
| `adapters/api/app.py:80` | `allow_origins=["*"]` — CORS fully open | medium |
| `adapters/api/routes_ws.py:88-93` | WS origin check only fires when `WS_ALLOWED_ORIGINS` env var is set; default = no check | medium |
| `adapters/api/app.py:99-102` | `/api/frontend-error` accepts arbitrary JSON with no size/field validation, logged verbatim | medium |
| `adapters/api/schemas.py:251-252` | `UpdateLayerFileRequest.content: str` has no `max_length` — arbitrary YAML size written to disk | medium |
| `llm/prompts.py:46,53,60,133` | NPC memory, entity descriptions, inventory interpolated into system prompt without separation boundary | medium |
| `llm/brain.py:76` | Player-visible action descriptions (including player text) flow into LLM user message unfiltered | medium |
| `adapters/api/routes_ws.py:46-58` | `future.result(timeout=30)` blocks Round thread if WS client stops reading — stall vector | medium |
| `adapters/api/schemas.py:24,43` | `ability_scores` and `attacks` accept arbitrary values with no bounds validation | low |
| `adapters/api/app.py:61` | `os.getenv("OPENROUTER_API_KEY", "")` uses empty default instead of failing fast | low |

---

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_master.py:297-325` | `get_session_state` calls `session.world.query_layer()` 6+ times directly, assembling world state in route handler | `GameService.get_world_state(session_id)` should do assembly; adapter calls one service method | **high** |
| `rules/action_provider.py:123-127` | `MerchantActionProvider.__init__` stores a world-query callback — injects I/O capability into rules/ | Provider should live in `service/` or callback passed to a free function | **high** |
| `rules/dice.py:9` | `import os` + `os.environ.get("DND_DICE_SEED")` — I/O in pure rules module | Seed injection via constructor or passed `rng` arg | medium |
| `rules/action_provider.py:35-40` | `BaseActionProvider.__init__` stores `self._types` — stateful class in rules/ | Standalone `get_base_action_types()` function or frozen dataclass | medium |
| `adapters/api/routes_player.py:10-11,53-74` | Imports `PlayerCharacter`, `Ability` from core; walks ability scores directly in serialization helper | `GameService` should return a DTO; adapter maps DTO -> response | medium |
| `adapters/api/routes_master.py:33` | Imports `Query, QueryType` from `core.models` to construct raw queries in route handler | Queries should be constructed inside `GameService` | medium |
| `adapters/api/routes_ws.py:29` | Imports `Action, ActionType` from `core.action` — constructs domain objects inline | Acceptable boundary translation, but borderline | low |

---

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `core/turn_budget.py:8` | `ActionCost` is `@dataclass` without `frozen=True` — pure value type, never mutated | Use `@dataclass(frozen=True)` for value types |
| `core/models.py:198` | `Event.data: dict[str, Any]` | Use `dict[str, object]` per project style |
| `core/models.py:222` | `Query.params: dict[str, Any]` | Use `dict[str, object]` per project style |
| Widespread (15+ files) | `dict[str, Any]` in layer `get_state`, serialization, LLM tools, adapters | Use `dict[str, object]` per project style |
| `layers/ecology/layer.py:292` | `str(answer.value) == "hostile"` — compares enum `.value` as string | Compare against `FactionRelation.HOSTILE` enum directly |

---

## Layer Contract

| Layer | Issue |
|-------|-------|
| `EcologyLayer._are_hostile` | Compares `str(answer.value) == "hostile"` instead of using `FactionRelation` enum — fragile cross-layer contract |

All five layers implement the full Layer ABC (`name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`). No missing methods.

---

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/weapons.py` | Dedicated `test_weapons.py` | **missing** — only indirect coverage via `test_combat_pipeline.py` |
| `rules/handlers/equipment.py` | Dedicated handler unit tests | **missing** — only indirect via `test_accessories.py` dispatcher |
| `layers/entities/layer.py` | `test_entities_layer.py` integration test | **missing** — scattered unit coverage but no single layer integration test |
| `service/commands_save.py` | Unit tests for `autosave_all_sessions`, `delete_save`, `list_saves` | **missing** |
| `adapters/api/routes_content.py` | Tests for `list_catalog_entries`, `list_schemas`, `get_schema`, `list_refs` | **missing** |
| `adapters/api/routes_master.py` | Tests for `list_library_templates`, `fork_world_layer` | **missing** |
| WS: fast-forward completion | Player `wait` -> time skip -> NPC resumes | **not tested** |
| WS: disconnect during NPC turn | Reconnect after NPC turn completes | **not tested** |
| WS: NPC full combat turn | Multi-action RuleBrain loop completing autonomously | **not tested** (only indirect) |

---

## Vision Drift

| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| `ClassFeatures` / proficiency system hardcoded in Python (`core/class_features.py`, `rules/proficiency.py`) | **Content is data** — "engine knows nothing about specific items/spells" | Adding a new class (Paladin, Barbarian) requires code changes, not YAML. Sprint 011 added `GREAT_WEAPON_FIGHTING` as more hardcoded Python. Known tech debt but actively growing. |
| `parse_class_features` in `content_loader/creatures.py` silently returns `[]` for Fighter without `fighting_style` key | **Fail-fast** code style rule | Fighter without `FighterFeatures` gets no class features — no proficiency AC bonus, no fighting style. Degrades silently with no validation. |
