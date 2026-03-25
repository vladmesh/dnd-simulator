# Code Audit

> **Date**: 2026-03-25
> **Scope**: full

## Summary
- Dead code: 4 issues (1 prior backlog, 3 continuing)
- Code smells: 6 issues
- Security: 5 issues
- Architecture violations: 5 issues
- Convention violations: 5 issues
- Layer contract: 0 issues
- Test gaps: 11 issues
- Vision drift: 0 issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| `rules/conditions.py:32` | `auto_fail_str_dex_saves()` — zero callers | backlog (future saving throw system) |
| `core/brain.py:59` | `move_away_from_target()` — zero callers | backlog (future movement AI) |
| `core/turn_budget.py:54` | `refund()` — zero callers | backlog (future reaction system) |
| `round.py:302` | `check_reactions()` — stubbed, zero callers | backlog (future reaction system) |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `layers/entities/layer.py` (832 lines) | God class — 30+ methods covering awareness, activation, combat, queries, perception, merchant lookups | Extract awareness builder, activation manager, query handler |
| `layers/politics/layer.py` (588 lines) | God class — diplomacy, leaders, economy, warfare, trade in one class | Extract subsystem handlers |
| `rules/action_handlers.py` (604 lines) | Large module accumulating handlers for all action types | Consider splitting by domain (combat, movement, trade, interaction) |
| `round.py:125-248` | `run_combat_turn` is ~124 lines | Extract sub-phases |
| `layers/entities/combat_manager.py:206-311` | `resolve_attack` is ~106 lines | Extract damage calculation, condition application |
| Service command mixins (27 occurrences) | `# type: ignore[attr-defined]` proliferation | Add a `Protocol` or ABC for the shared mixin interface |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:76-79` | CORS `allow_origins=["*"]` — any origin can access API | medium |
| (global) | No authentication/authorization — all endpoints open to anyone with session ID | medium |
| `adapters/api/routes_ws.py:137` | No max WebSocket message size configured — client can send arbitrarily large payloads | low |
| `adapters/api/routes_ws.py:151-155` | Action `params` passed as raw dict from client with no schema validation | low |
| `llm/prompts.py` | Player `say()` text flows into NPC memory → system prompt. System/user separation maintained but system prompt contains prior player utterances | low |

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `rules/trade.py:11` | `from dnd_simulator.layers.entities.models import Npc` — rules/ imports from layers/ at module level | rules/ must depend only on core/; extract `is_merchant` to a protocol or move merchant check to core | high |
| `rules/action_handlers.py:519` | Runtime `from dnd_simulator.layers.entities.models import Npc` in `_resolve_merchant()` | Same as above — rules/ must not depend on layers/ even at runtime | high |
| `layers/entities/models.py:126-252` | ~130 lines of game content hardcoded in Python (schedules, flavor text, canned dialogue) | Move to YAML data files under `content/` per "content is data" principle | medium |
| `adapters/api/routes_ws.py:152-155` | Adapter constructs domain `Action` from raw JSON (knows `ActionType`, field names) | Move parsing to service layer | low |
| `adapters/api/routes_player.py:52-75` | `_player_status()` maps `Ability` enum to strings — presentation logic in adapter | Use Pydantic schema with `from_player()` classmethod | low |

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `layers/entities/models.py:105` | `self.role == "merchant"` — hardcoded string comparison | Use enum for NPC roles (CLAUDE.md: enums over hardcoded strings) |
| `core/models.py:210,217` | `Query.params: dict[str, Any]` and `Answer.value: Any` | Use `object` for strict mypy (deferred from prior audit — cascading changes) |
| `adapters/api/routes_player.py:45,52` | Helper functions typed as `Any` | Use proper types (`GameSession`, `PlayerStatusResponse`) |
| `adapters/api/routes_master.py:348,353` | Helper functions typed as `Any` | Use proper types |
| `rules/action_handlers.py:55,60,68,115,191` | `action.params.get("key", default)` pattern — silent fallback on missing params | Use `action.params["key"]` — crash on missing keys per fail-fast convention |

## Layer Contract
| Layer | Issue |
|-------|-------|
| (all clean) | All 4 layers implement full Layer ABC. No violations. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
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
| `rules/trade.py` | dedicated unit tests | covered by `test_trade.py` (14 tests) — OK |

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| (none) | — | Sprint 003 trading system works without LLM (RuleBrain path), goes through service layer, no parallel time. All 6 key invariants hold. |
