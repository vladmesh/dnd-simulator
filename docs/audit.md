# Code Audit

> **Date**: 2026-04-13
> **Scope**: full (post Sprint 017)

## Summary
- Dead code: 7 issues
- Code smells: 5 issues
- Security: 5 issues
- Architecture violations: 2 issues
- Convention violations: 8 issues
- Layer contract: 0 issues
- Test gaps: 9 issues
- Vision drift: 0 issues

**Total: 36 issues**

## Dead Code

All items are carry-forward from the previous audit. Sprint 017 introduced no new dead code.

| File | Function | Action |
|------|----------|--------|
| `rules/reactions.py:15` | `can_opportunity_attack()` — 0 prod callers, duplicates inline check in `find_oa_triggers()` | remove or consolidate |
| `rules/conditions.py:27` | `prone_stand_cost()` — only called in tests, prone mechanic not yet wired | backlog (wire with prone) |
| `rules/movement.py:201` | `walk_path()` — 12 test refs, 0 prod callers; budget-aware path walking | backlog (wire with move_to) |
| `core/turn_budget.py:58` | `refund()` — 1 test ref, 0 prod | backlog |
| `core/player.py:73` | `to_save_data()` — 1 test ref, 0 prod | backlog |
| `rules/geography.py:172` | `is_daylight()` — 5 test refs, 0 prod; day/night cycle not wired | backlog |
| `core/models.py:189` | `TimeDelta.from_days()` — 7 test refs, 0 prod; harmless convenience | ignore |

**Frontend dead export** (carry-forward):

| File | Issue | Action |
|------|-------|--------|
| `frontend/src/components/master/RefSelect.tsx:64` | `clearRefCache` exported but never imported | remove export |

## Code Smells

The 939-line `game_service.py` and 614-line `round.py` persist. Sprint 017 added no new large files. `content_loader/schemas.py` grew but is a data-driven Pydantic module (acceptable).

| File | Issue | Suggestion |
|------|-------|------------|
| `service/game_service.py` (945 lines, 44+ methods) | God class: session mgmt, content CRUD, catalog CRUD, entity CRUD, player creation | Extract service objects by domain (e.g., `CatalogService`, `EntityService`) |
| `round.py` (614 lines) | `run_combat_turn` (~70 lines) and `run_peaceful_turn` (~70 lines) still long | Extract into helper functions |
| `content_loader/schemas.py` (431 lines, +6 since 016) | Large Pydantic schema collection but growing | Acceptable as single source of truth; monitor |
| `layers/entities/layer.py` (601 lines) | Large layer with 5 sub-managers | Acceptable given AwarenessBuilder/ActivationManager/CombatManager decomposition |
| `core/action_defs.py` (553 lines, +12 since 016) | Large action registry — grew with level-up action defs | Consider data-driven YAML format long term |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:86-89` | CORS wildcard `allow_origins=["*"]` — any origin can cross-origin request | medium |
| All API endpoints | Zero authentication — session_id (8-char hex) only guard | medium |
| `adapters/api/routes_ws.py:91` | WS origin check disabled by default; `WS_ALLOWED_ORIGINS` env var optional | low |
| `llm/brain.py:93-95`, `llm/prompts.py:76` | Player `say` text flows into LLM system prompt but via i18n translate (low blast radius) | low |
| `adapters/api/routes_ws.py:163-164` | WS `params` dict passed without schema validation; malformed params could trigger handler errors | low |

## Architecture Violations

Sprint 017 maintained correct dependency flow. Two violations remain from prior work:

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_player.py:18-20` | Route imports `STARTING_GOLD`, `xp_to_next_level()`, `effective_ac()`, `perform_level_up()` from rules/ and calls them directly | Expose via `GameService` methods; adapters should not call rules | low |
| `adapters/api/routes_player.py:16` | Route imports `PlayerCharacter` from `core.player` to type internal helper | Move `_player_status()` into service layer | low |

## Convention Violations

Sprint 017 introduced new violations:

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `content_loader/schemas.py:40,96,212,340` | 5 uses of `Any` type in validators and model_post_init | CLAUDE.md: use `object` not `Any` in state dicts (context is Pydantic, acceptable but not ideal) |
| `core/turn_budget.py:18` | `@dataclass` without `frozen=True` — turn budget is per-turn immutable value object | Should be `frozen=True` |
| `layers/geography/models.py:35` | `Region` — `@dataclass` without `frozen=True` | Intentionally mutable (region state during game); document or freeze |
| `layers/politics/models.py:29,38` | `Leader`, `Nation` — `@dataclass` without `frozen=True`; mutated by layer | Intentional (dynamic politics); justify or freeze |
| `layers/settlements/models.py:17` | `Settlement` — `@dataclass` without `frozen=True`; mutated by layer | Intentional (population, prosperity changes); justify or freeze |
| `rules/perform_level_up.py:28-54` | `perform_level_up()` mutates Character in-place (not pure) | Comment as intentional or use replace() pattern |
| `core/resource.py:16` | `@dataclass` without `frozen=True` — ResourcePool is a value object | Should be `frozen=True` |

## Layer Contract

All 5 layers (Geography, Politics, Settlements, Ecology, Entities) fully implement the Layer ABC: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. **No issues.**

## Test Gaps

Sprint 017 added leveling infrastructure but test coverage remains incomplete:

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/weapons.py` | `tests/unit/test_rules_weapons.py` | missing — only via `test_attack_resolution.py` |
| `rules/action_provider.py` | `tests/unit/test_rules_action_provider.py` | missing — isolated test in `test_action_provider_isolated.py` only |
| `rules/fighting_style.py` | `tests/unit/test_rules_fighting_style.py` | missing — via `test_second_wind.py` + `test_create_player.py` only |
| `rules/perform_level_up.py` | `tests/unit/test_rules_perform_level_up.py` | missing — level-up E2E tested but not isolated unit |
| `rules/leveling.py` | `tests/unit/test_rules_leveling.py` | missing — XP formulas only tested via integration |
| `rules/geography.py` | `tests/unit/test_rules_geography.py` | missing — `is_daylight()` in `test_geography_formulas.py` only |
| `service/commands_time.py` | any unit test | missing — 0 direct refs |
| `tests/unit/test_ws.py:malformed-json` | WS malformed JSON scenario | missing — `test_unknown_message_type` exists but no raw malformed JSON test |
| `tests/integration/test_player_state_xp.py` | XP grant flow (kill → XP → level-up) | added in 017 but coverage thin (2 scenarios) |

**WS test coverage:** 6 scenarios (invalid session, no player, end-turn, action+end-turn, unknown type, query rejected). Missing: malformed JSON, disconnect during active loop, reaction prompts, concurrent message handling.

## Vision Drift

Sprint 017 phase 4 closed with:
- **Level-up system**: pure rule-based (`perform_level_up`), works for Fighter L1→L2, Rogue L1→L2, Paladin L1→L2 (with fighting_style selection). Full RuleBrain coverage (no LLM required) ✓
- **Battle map overrides**: per-location `battle_map` YAML field, fail-fast validator pinning "feet" coord convention ✓
- **XP on kill**: EcologyLayer emits `CreatureKilled` event, service grants XP, triggers `level_up_available` flag ✓

All changes align with vision invariants:
- **Classic mode without LLM**: Level-up fully rule-based, no LLM dependency ✓
- **Single global round**: All creatures including leveling-up ones share one round ✓
- **Layer independence**: Geography/Politics/Settlements/Ecology/Entities each independently tick ✓
- **Master through endpoints only**: Level-up UI → API → GameService (no direct state mutation) ✓
- **Brain is swappable**: Level-up happens at Character level, no brain-specific state ✓
- **Content is data**: Battle-map per location in YAML; level-up choices via UI (not hardcoded) ✓

**No vision drift detected.**
