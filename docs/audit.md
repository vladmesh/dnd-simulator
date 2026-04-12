# Code Audit

> **Date**: 2026-04-13
> **Scope**: full (post Sprint 016)

## Summary
- Dead code: 7 issues (all carry-forward from previous audit — none new)
- Code smells: 5 issues
- Security: 5 issues
- Architecture violations: 2 issues
- Convention violations: 5 issues
- Layer contract: 0 issues
- Test gaps: 8 issues
- Vision drift: 0 issues

**Total: 32 issues**

## Dead Code

Sprint 016 introduced no new dead code. All items below are carry-forward from the previous audit.

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

Sprint 016 split `routes_master.py` into `routes_session.py` + `routes_world.py`. The god-class smell in `game_service.py` and the oversized `round.py` persist.

| File | Issue | Suggestion |
|------|-------|------------|
| `service/game_service.py` (939 lines, 44+ methods) | God class mixing session mgmt, content CRUD, catalog CRUD, entity CRUD, player creation | Split into domain-focused service objects per sprint 017+ |
| `round.py` (614 lines) | `run_combat_turn` (~70 lines) and `run_peaceful_turn` (~70 lines) still long | Extract combat-turn and awareness-building into helpers |
| `layers/entities/layer.py` (600 lines) | Large layer delegating to 5 sub-managers | Acceptable given decomposition; monitor for growth |
| `core/action_defs.py` (541 lines) | Large action registry — grew with paladin/smite/rest | Consider data-driven YAML format long term |
| `service/session.py` (517 lines) | Session + GameSession + PlayerBrain callback logic | Extract player brain callbacks to own module |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:86-89` | CORS wildcard `allow_origins=["*"]` — any origin can make cross-origin requests to the API | medium |
| All API endpoints | Zero authentication — session_id (8-char hex) is the only guard against session hijacking | medium |
| `adapters/api/routes_ws.py:91` | WS origin check disabled by default; `WS_ALLOWED_ORIGINS` env var must be set manually | low |
| `llm/brain.py`, `llm/prompts.py` | Player `say` text flows unsanitized into LLM prompts — no explicit injection mitigation (blast radius limited: tool-call-only output schema) | low |
| `adapters/api/routes_ws.py:163-164` | WS `params` dict passed without schema validation to action handlers — malformed params could trigger handler-level errors | low |

## Architecture Violations

Sprint 016 closed two violations from the previous audit:
- `round.py` now uses `CreatureHost` protocol instead of importing `EntitiesLayer` directly.
- `llm/` no longer imports from `layers/`.

Two violations remain:

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_player.py:16-17` | Route imports `POINT_BUY_BUDGET`, `STARTING_GOLD` from `rules/character_creation` and calls `effective_ac()` from `rules/modifiers` directly | Expose via `GameService.get_setup_config()` and `GameService.get_player_status()`; adapters should not call rule functions | low |
| `adapters/api/routes_player.py:14` | Route imports `PlayerCharacter` from `core.player` to type the internal `_player_status` helper | Move `_player_status` into service layer | low |

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| 30+ files across codebase | `dict[str, Any]` used in `Event.data`, `Query.params`, `Action.params`, serialization helpers in `core/` and `service/` | CLAUDE.md: use `object` not `Any` in state dicts |
| `layers/geography/models.py:35` | `Region` — `@dataclass` without `frozen=True` | Pure data models should be frozen |
| `layers/politics/models.py:29,38` | `Leader`, `Nation` — `@dataclass` without `frozen=True`; mutations happen in `warfare.py` / `economy.py` | Justify mutability or use explicit `replace()`-style update pattern |
| `layers/settlements/models.py:17` | `Settlement` — `@dataclass` without `frozen=True`; mutated by layer tick | Same as above |
| `rules/rule_brain.py:38` | `_CombatContext` — `@dataclass` without `frozen=True`; used as turn-scoped value object | Should be `frozen=True` — no mutation needed |

## Layer Contract

All 5 layers (Geography, Politics, Settlements, Ecology, Entities) implement the full Layer ABC (`name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`). **No issues.**

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/weapons.py` | `tests/unit/test_rules_weapons.py` | missing — indirect coverage only via `test_attack_resolution.py` |
| `rules/action_provider.py` | `tests/unit/test_rules_action_provider.py` | missing — isolated test exists but in `test_action_provider_isolated.py`, no direct module test |
| `rules/fighting_style.py` | `tests/unit/test_rules_fighting_style.py` | missing — only tested via `test_second_wind.py` and `test_create_player.py` |
| `rules/geography.py` | `tests/unit/test_rules_geography.py` | missing — `is_daylight()` covered by `test_geography_formulas.py` but module has no dedicated test |
| `rules/politics.py` | `tests/unit/test_rules_politics.py` | missing — covered via layer tests only |
| `rules/settlements.py` | `tests/unit/test_rules_settlements.py` | missing — covered via layer tests only |
| `service/commands_time.py` | any unit test | missing — 0 direct test references |
| `tests/unit/test_ws.py` | WS malformed JSON scenario | missing — `test_unknown_message_type` exists but no test for malformed JSON (non-parseable text sent over WS) |

**WS test gaps:** Current `test_ws.py` covers 6 scenarios (invalid session, no player, end-turn, action+end-turn, unknown type, query type rejected). Missing: malformed JSON, disconnect during active game loop, reaction prompt flow.

## Vision Drift

Sprint 016 tech-sweep changes:

- **EntityKind StrEnum**: runtime discriminator for entity type — aligns with "content is data" principle, no drift.
- **BrainType StrEnum**: replaces hardcoded string comparisons — aligns with "brain is swappable" and enum conventions. No drift.
- **CreatureHost protocol**: decouples `round.py` from `EntitiesLayer` — improves layer independence. No drift.
- **llm/ decoupled from layers/**: removes upward dependency — correct direction. No drift.
- **Fail-fast cleanup**: removes silent defaults — aligns with project conventions. No drift.

**No vision drift detected.**
