# Code Audit

> **Date**: 2026-03-22
> **Scope**: full

## Summary
- Dead code: 1 issue
- Code smells: 3 issues
- Security: 4 issues
- Architecture violations: 2 issues
- Convention violations: 2 issues
- Layer contract: 0 issues
- Test gaps: 1 issue
- Vision drift: 0 issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| `round.py:213` | Stale TODO: reaction support placeholder — no implementation progress | backlog (track in roadmap if planned) |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `layers/entities/layer.py` | 681 lines — largest file in codebase | Extract perception/activity helpers into submodules |
| `layers/politics/layer.py` | 587 lines | Consider splitting diplomacy/warfare logic into submodules |
| `adapters/api/static/js/world-builder.js` | 1706 lines — single JS file, no linter | Split into step modules or add eslint |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:70` | CORS `allow_origins=["*"]` — open to any origin | low (local dev OK, lock down before deployment) |
| `adapters/api/routes_ws.py` | No rate limiting or message size limits on WebSocket | medium (client can spam messages) |
| `adapters/api/routes_ws.py` | No origin validation on WS upgrade — any page can connect | medium |
| `adapters/api/static/js/*.js` | Extensive `innerHTML` usage with server data — XSS surface | medium (mitigated by `esc()` helper in most places, but patterns like `innerHTML += \`...\`` with template literals are fragile — one missed `esc()` call is an XSS) |

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `adapters/api/routes_ws.py:35` | Imports `EntitiesLayer` directly from layers | Access via `GameService` or `World` query interface | medium |
| `adapters/cli_loop.py:32-35` | Imports all 4 layer classes directly | Access via `GameService` or `World` query interface | medium |

Note: Both adapters also import heavily from `core.*` (Action, Awareness, Brain, Creature, etc.). Core imports are acceptable per architecture rules, but the adapters contain significant game logic (turn orchestration, awareness formatting, Round creation) that could live in the service layer. This is a "thick adapter" smell rather than a hard violation.

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `core/models.py:168` | `value: Any` in `Answer` dataclass | Use `object` for strict mypy (CLAUDE.md convention) |
| Multiple files (21 files) | `from typing import Any` — widespread `Any` usage in adapters, service, layers, llm | Prefer `object` where possible; `Any` acceptable at serialization boundaries (JSON dicts) but overused in internal signatures like `_get_session() -> Any` |

## Layer Contract
All 4 layers (Geography, Politics, Settlements, Entities) implement the full Layer ABC. No issues found.

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/actions.py` | `tests/test_rules_actions.py` | missing (naming mismatch — tests exist as `test_multi_action.py` but don't follow `test_rules_*` convention; action_cost rules tested indirectly) |

Note: Most rules have tests under alternative names (`test_checks.py`, `test_dice.py`, `test_movement.py`, `test_combat.py`, `test_geography_formulas.py`, etc.). The naming doesn't follow `test_rules_*` convention but coverage exists. WS tests cover connection, turn flow, action handling, unknown messages, and query rejection — reasonable coverage.

## Vision Drift
No drift detected. Recent commits (last 2 weeks) align with vision:
- `a7b7c3b` Split peaceful/combat loops — consistent with round-based design
- `59892d1` Fix double-turn bug — fixes, not new violations
- `c6080c3` Unify entity model — moves toward cleaner entity hierarchy
- `bbeb65e` Added VISION.md/ROADMAP.md — documentation, no code impact
