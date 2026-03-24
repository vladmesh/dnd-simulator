# Code Audit

> **Date**: 2026-03-24
> **Scope**: full

## Summary
- Dead code: 8 issues
- Code smells: 10 issues
- Security: 7 issues
- Architecture violations: 4 issues
- Convention violations: 8 issues
- Layer contract: 0 issues
- Test gaps: 15 issues
- Vision drift: 0 issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| `layers/entities/layer.py:86` | `active_creatures_at_location()` — zero callers | remove or backlog |
| `rules/conditions.py:111` | `auto_fail_str_dex_saves()` — never invoked | backlog (future saving throw system) |
| `core/location.py:55` | `region_of()` — zero callers | remove or backlog |
| `core/location.py:59` | `settlement_of()` — zero callers | remove or backlog |
| `core/brain.py:59` | `move_away_from_target()` — zero callers | backlog (future movement AI) |
| `core/turn_budget.py:54` | `refund()` — zero callers | backlog (future reaction system) |
| `round.py:302` | `check_reactions()` — stubbed, zero callers | backlog (future reaction system) |
| `service/session.py:387` | `round_running` property — zero callers | remove |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `layers/entities/layer.py` (821 lines) | God class — 30 methods covering awareness, activation, combat, queries, perception | Extract awareness builder, activation manager, query handler |
| `layers/politics/layer.py` (587 lines) | God class — diplomacy, leaders, economy, warfare, trade in one class | Extract subsystem handlers |
| `layers/entities/layer.py:518-642` | `query()` is 125 lines | Split by query type into helper methods |
| `round.py:125-248` | `run_combat_turn` is 124 lines | Extract sub-phases |
| `layers/entities/combat_manager.py:206-311` | `resolve_attack` is 106 lines | Extract damage calculation, condition application |
| `layers/entities/layer.py:208,217,228,243` | 4x `except Exception: pass` in `build_peaceful_awareness` | Log errors; fail-fast or at least surface diagnostics |
| `adapters/api/routes_ws.py:58` | `except Exception: pass` in WS send — silent swallow | Log the exception |
| Service command mixins (27 occurrences) | `# type: ignore[attr-defined]` proliferation | Add a `Protocol` or ABC for the shared mixin interface |
| `llm/client.py:70,112,113` | `# type: ignore[arg-type]` on OpenAI SDK calls | Use typed dicts or `cast()` |
| `layers/politics/layer.py:338` | Magic number `0.08` for trade agreement probability | Extract to named constant or function like other probabilities |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:68-71` | CORS `allow_origins=["*"]` — any origin can access API | medium |
| `storage/store.py:84-85` | Path traversal: `name` and `world` params unsanitized in `_path_for()`. Save name like `../../etc/passwd` resolves outside saves dir. `save` method also creates arbitrary dirs via `mkdir(parents=True)` | medium |
| (global) | No authentication/authorization — all endpoints open to anyone with session ID | medium |
| `adapters/api/routes_ws.py:137` | No max WebSocket message size configured — client can send arbitrarily large payloads | low |
| `adapters/api/routes_ws.py:151-155` | Action `params` passed as raw dict from client with no schema validation | low |
| `adapters/api/app.py:86-90` | `/api/frontend-error` writes unsanitized client JSON into server logs (log injection) | low |
| `llm/prompts.py` | Player `say()` text may flow into NPC memory → system prompt. System/user separation maintained but system prompt contains prior player utterances | low |

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `layers/entities/models.py:123-248` | ~120 lines of game content hardcoded in Python (schedules, flavor text, canned dialogue) | Move to YAML data files under `content/` per "content is data" principle | medium |
| `adapters/api/routes_ws.py:58-59` | `except Exception: pass` in cross-thread WS bridge silently drops all errors including 30s timeouts | Log exceptions; surface hung event loop conditions | medium |
| `adapters/api/routes_ws.py:152-155` | Adapter constructs domain `Action` from raw JSON (knows `ActionType`, field names) | Move parsing to service layer | low |
| `adapters/api/routes_player.py:52-75` | `_player_status()` maps `Ability` enum to strings — presentation logic in adapter | Use Pydantic schema with `from_player()` classmethod | low |

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| ~~All layers + callers (~60 string comparisons)~~ | ~~Query system uses hardcoded strings instead of enum~~ | **FIXED 2026-03-24**: Added `QueryType` enum to `core/models.py`, replaced all 60+ string comparisons across 4 layers, 3 service files, 1 adapter, and 5 test files |
| `core/models.py:164` | `Query.params: dict[str, Any]` and `Answer.value: Any` | Use `object` not `Any` for strict mypy |
| `adapters/api/routes_player.py:45,52` | Helper functions typed as `Any` | Use proper types |
| `adapters/api/routes_master.py:346,351` | Helper functions typed as `Any` | Use proper types |
| `core/awareness.py:60,80` | `PeacefulAwareness` and `CombatAwareness` are mutable but are read-only snapshots | `@dataclass(frozen=True)` |
| `layers/geography/models.py:27` | `Connection` is mutable but is immutable link data | `@dataclass(frozen=True)` |
| `layers/entities/models.py:56` | `ScheduleEntry` is mutable but is read-only data | `@dataclass(frozen=True)` |
| `service/commands_creatures.py:162-184` | Creature spawning uses `.get(key, default)` for hp, ac, speed — silently degrades | Fail fast: require keys or crash |

## Layer Contract
| Layer | Issue |
|-------|-------|
| (all clean) | All 4 layers implement full Layer ABC. No violations. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/action_handlers.py` | `test_rules_action_handlers.py` | **missing** (critical — newest pure-function code) |
| `rules/action_provider.py` | `test_rules_action_provider.py` | **missing** |
| `rules/weapons.py` | `test_rules_weapons.py` | **missing** |
| `rules/conditions.py` | `test_rules_conditions.py` | **missing** |
| `rules/actions.py` | `test_rules_actions.py` | **missing** |
| `core/awareness.py` | `test_awareness.py` | missing |
| `core/items.py` | `test_items.py` | missing |
| `core/world.py` | `test_world.py` | missing |
| `core/turn_budget.py` | `test_turn_budget.py` | missing |
| `core/location.py` | `test_location.py` | missing |
| `service/brain_factory.py` | `test_brain_factory.py` | missing |
| `service/commands_*.py` | `test_commands_*.py` | missing (4 files) |
| `service/session.py` | `test_session.py` | missing |
| `storage/store.py` | `test_store.py` | missing |
| `llm/*.py` | unit tests | missing (LLM-dependent, may be intentional) |

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| (none) | — | No drift detected. All 6 key invariants hold. Roadmap is up to date. |
