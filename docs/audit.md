# Code Audit

> **Date**: 2026-03-25
> **Scope**: full (post Sprint 004 Phase 4)

## Summary
- Dead code: 3 issues
- Code smells: 8 issues
- Security: 9 issues
- Architecture violations: 4 issues
- Convention violations: 5 issues
- Layer contract: 0 issues
- Test gaps: 12 issues
- Vision drift: 0 issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| `rules/movement.py:101` | `move_toward()` — zero callers, superseded by `move_direction()` | remove |
| `rules/movement.py:111` | `move_away_from()` — zero callers, superseded by `move_direction()` | remove |
| `rules/movement.py:136` | `_step_toward()` — private helper only used by dead functions above | remove |

Prior-audit backlog items (still valid, tracked for future sprints):
- `rules/conditions.py:32` `auto_fail_str_dex_saves()` — future saving throw system
- `core/brain.py:59` `move_away_from_target()` — future movement AI
- `core/turn_budget.py:54` `refund()` — future reaction system
- `round.py:302` `check_reactions()` — stubbed reaction system

TODOs (legitimate, keeping):
- `round.py:390` — reaction awareness list
- `rules/modifiers.py:285` — two-handed weapon exclusion

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `layers/entities/layer.py` (1215 lines) | God class — awareness, activation, combat, queries, perception, merchant lookups, squad handling | Extract awareness builder, activation manager, query dispatcher |
| `content_loader.py` (815 lines) | Kitchen-sink loader for all content types | Split by domain: weapons, NPCs, settlements, encounters |
| `layers/politics/layer.py` (609 lines) | Diplomacy, leaders, economy, warfare, trade in one class | Extract subsystem handlers |
| `rules/action_handlers.py` (605 lines) | All action handlers in one module | Split by domain (combat, movement, trade, interaction) |
| `round.py:125-248` | `run_combat_turn` ~121 lines | Extract budget init, awareness building, condition ticking |
| `layers/entities/combat_manager.py` `resolve_attack` | 186 lines — attack roll, sneak attack, damage, logging, events | Extract sneak attack calc, damage calc to helpers |
| `layers/entities/layer.py` `query` method | 125 lines, 13+ `if q is QueryType.X:` branches | Use dispatch dict pattern |
| `service/session.py` `start_round` | 104 lines with nested callback definitions; serialization code duplicated across `on_turn`, `on_action`, `on_round_end` | Extract `_build_turn_message()` helper |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:75-80` | CORS `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]` — any origin can access all API endpoints | high |
| (global) | No authentication/authorization — all REST/WS endpoints open to anyone with session_id; any client can delete sessions, spawn/modify creatures, save/load | high |
| `adapters/api/routes_ws.py:138` | No max WebSocket message size — client can send arbitrarily large JSON to exhaust memory | high |
| `adapters/api/app.py:94-98` | `POST /api/frontend-error` accepts arbitrary JSON, no validation/size limits/auth — log injection vector | medium |
| `adapters/api/routes_ws.py:87-93` | WS origin validation optional (`WS_ALLOWED_ORIGINS` env var, defaults to empty = allow all); case-sensitive comparison | medium |
| (global) | No CSRF protection on state-changing HTTP methods; combined with CORS=* makes browser-based CSRF viable | medium |
| (global) | No rate limiting on REST endpoints (WS has token bucket at 5 req/sec) | low |
| `adapters/api/routes_ws.py:151-155` | Action `params` passed as raw dict from client with no schema validation | low |
| `llm/prompts.py` | Player `say()` text flows into NPC memory → system prompt; system/user separation maintained but prior player utterances in system prompt | low |

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `rules/trade.py:11` | `from dnd_simulator.layers.entities.models import Npc` — rules/ imports from layers/ | rules/ must depend only on core/; extract merchant protocol to core | high |
| `rules/action_handlers.py:519` | Runtime `from dnd_simulator.layers.entities.models import Npc` in `_resolve_merchant()` | Same — rules/ must not depend on layers/ even at runtime | high |
| `round.py:29` | `from dnd_simulator.layers.entities.layer import EntitiesLayer` — Round directly accesses layer bypassing World query validation | Round should use `World.query_layer()` instead of direct layer method calls | medium |
| `layers/entities/npc_behaviors.py:15-50` | Module-level YAML loading with global state mutation (`_load()` mutates globals) | Load data in content_loader.py and inject into layer | low |

Resolved from prior audit:
- `layers/entities/models.py` hardcoded game content — still present but tracked for YAML extraction
- `adapters/api/routes_ws.py` adapter constructing domain Action — still present, low severity

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `layers/entities/models.py:105` | `self.role == "merchant"` — hardcoded string comparison | Use enum for NPC roles (enums over hardcoded strings) |
| `core/models.py:210,217` | `Query.params: dict[str, Any]` and `Answer.value: Any` | Use `object` for strict mypy |
| `adapters/api/routes_player.py:45,52` | Helper functions typed as `Any` | Use proper types |
| `adapters/api/routes_master.py:348,353` | Helper functions typed as `Any` | Use proper types |
| `rules/action_handlers.py:55,60,68,115,191` | `action.params.get("key", default)` pattern — silent fallback on missing params | Use `action.params["key"]` — fail fast |

## Layer Contract
| Layer | Issue |
|-------|-------|
| (all clean) | All 5 layers (Geography, Politics, Settlements, Entities, Ecology) implement full Layer ABC. No violations. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/action_handlers.py` (605 lines) | `test_action_handlers.py` | **missing — CRITICAL** (core combat execution) |
| `rules/action_provider.py` | `test_action_provider.py` | missing (action availability logic) |
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
| (none) | — | Sprint 004 squad events, materialization, perception pipeline, frontend rendering — all follow established patterns. Classic mode works without LLM (materialized squads get RuleBrain). Single global round maintained. Layers independent (EcologyLayer respects hierarchy). Brain swappable. Content is data. All 6 invariants hold. |
