# Code Audit

> **Date**: 2026-03-21
> **Scope**: full

## Summary
- Dead code: 0 issues
- Code smells: 2 issues (1 planned)
- Security: 2 issues (1 fixed, 1 won't fix)
- Architecture violations: 3 issues (2 fixed, 1 won't fix)
- Convention violations: 2 issues
- Layer contract: 0 issues
- Test gaps: 3 issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| — | ruff F401 clean; no unreferenced functions found | — |

No TODOs/FIXMEs found in source.

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `service.py` (850+ lines) | Largest file, well above 400-line threshold | **Planned**: split command handlers into sub-modules (combat, NPC, time) — next task |
| `layers/politics/layer.py` (588 lines) | Second largest, above threshold | Tick logic is inherently complex; lower priority but could extract war-resolution helpers |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| ~~`adapters/api/schemas.py:24-70`~~ | ~~Pydantic request models accept bare `int`/`float` fields with no constraints~~ | **Fixed**: added `Field(ge=, le=)` bounds on all numeric request fields (hp, ac, level, gold, population, hours, wealth, military, stability, prosperity, defenses) | ~~medium~~ |
| `adapters/api/` | No CORSMiddleware configured — fine for local-only use, but flag if a separate frontend is added | low |

No hardcoded secrets, no subprocess calls, no prompt injection risks found. `.env` is gitignored.

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| ~~`core/brain.py:49,74,81`~~ | ~~`RuleBrain` imports from `layers.entities.models`~~ | **Fixed**: moved `NpcTag`/`find_tags`/`has_tag` → `core/tags.py`; added `Creature.memory_tags` + `get_canned_response()` polymorphism; zero layer imports in brain.py now | ~~high~~ |
| ~~`adapters/api/routes_master.py:24,84,125,305`~~ | ~~Route handlers import `Npc` and `EntitiesLayer`, iterate layer internals directly~~ | **Fixed**: added `all_entities`/`all_npcs`/`npc_info` queries to EntitiesLayer; added `list_npcs()`/`get_npc_info()` to GameService; routes now use service only, zero layer imports | ~~high~~ |
| `adapters/cli_loop.py:28-31` | CLI adapter imports all four layer classes and constructs them directly | **Won't fix**: debug-only REPL adapter, not used in production; gameplay goes through API | ~~medium~~ |

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| Multiple files (17 modules) | `from typing import Any` used throughout; `Answer.value: Any` in `core/models.py:167` | CLAUDE.md: use `object` not `Any` in state dicts for strict mypy. `Any` in adapters for session types is lower priority, but `Answer.value` is core |
| Multiple files (17 dataclasses) | `@dataclass` without `frozen=True` on: `Creature`, `Character`, `PlayerCharacter` (core), `World`, `CombatState`, `BattleMap`, `Settlement`, `NpcMemory`, `Npc`, `NpcScheduleEntry`, `Nation`, `NationRelation`, `Region`, `HexCell` | Expected for stateful objects (World, CombatState, creatures). Settlement, Nation, NpcMemory are also mutated in-place by layer ticks — acceptable by design but worth documenting |

Note: Line length is clean (docstring in `llm/__init__.py` fixed).

## Layer Contract
| Layer | Issue |
|-------|-------|
| — | All 4 layers (Geography, Politics, Settlements, Entities) implement the full Layer ABC. No issues found |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/combat.py` | `tests/test_rules_combat.py` | missing (partially covered by `test_combat.py`, `test_attack_resolution.py`) |
| `rules/geography.py` | `tests/test_rules_geography.py` | missing (partially covered by `test_geography_formulas.py`) |
| `adapters/api/routes_master.py` | `tests/test_routes_master.py` | missing (partially covered by `test_api.py`) |
| `adapters/api/routes_player.py` | `tests/test_routes_player.py` | missing (partially covered by `test_api.py`) |
| `service.py` | `tests/test_service.py` | missing |
| `layers/entities/layer.py` | `tests/test_entities_layer.py` | missing (covered by `test_npc_layer.py`) |

Note: Many "missing" test files have equivalent coverage under different names. The main real gap is `test_service.py`.

No skipped or xfail tests found.
