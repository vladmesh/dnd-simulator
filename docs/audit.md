# Code Audit

> **Date**: 2026-03-26
> **Scope**: full (post Sprint 007 Phase 4)

## Summary
- Dead code: 0 issues
- Code smells: 3 issues (large files)
- Security: 4 issues (1 medium, 3 low)
- Architecture violations: 0 issues
- Convention violations: 1 issue
- Layer contract: 0 issues
- Test gaps: 2 issues
- Vision drift: 0 issues

## Dead Code

No issues. Ruff F401 clean. Two TODOs remain relevant:
- `round.py:387` — reaction awareness (future feature)
- `rules/modifiers.py:285` — two-handed weapon exclusion (future feature)

## Code Smells

| File | Lines | Suggestion |
|------|-------|------------|
| `layers/politics/layer.py` | 609 | Consider extracting diplomacy/warfare tick into sub-modules |
| `service/game_service.py` | 570 | Many command modules already extracted; monitor growth |
| `layers/entities/layer.py` | 560 | Already decomposed (combat_manager, activation_manager, etc.); monitor |

All three have been over 400 lines since sprint 006. No new entrants. `combat_manager.py` (535), `round.py` (507), `routes_master.py` (463), `session.py` (456) are borderline — monitor but no action needed yet.

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/routes_ws.py:150` | `json.loads(raw)` without try/except — malformed JSON from client raises unhandled `JSONDecodeError`, caught only by generic `except Exception` | medium |
| `adapters/api/app.py:79` | `allow_origins=["*"]` — acceptable for local dev, must lock down before any non-local deployment | low |
| `adapters/api/routes_ws.py:139` | No max message size on `ws.receive_text()` — a client can send arbitrarily large payloads | low |
| `adapters/api/routes_ws.py:81` | Session ID in URL without auth — another client can connect to any session by guessing the ID | low |

**Good:** WS rate limiting (token bucket, 5/sec, burst 20) is in place. WS origin check is configurable via `WS_ALLOWED_ORIGINS`. Input bounds on Pydantic schemas (hp, ac, population, wealth, hours) all have `Field(ge=, le=)` constraints. No hardcoded secrets. No subprocess calls. No innerHTML in frontend (React app).

## Architecture Violations

No violations found:
- All cross-layer imports are intra-package (same layer) — clean
- `core/` imports nothing from upper layers — clean
- `rules/` imports nothing from layers/service/adapters — clean
- Adapters import core types (`Action`, `ActionType`, `Ability`, `PlayerCharacter`, `Query`, `QueryType`) only for deserialization/response construction — acceptable thin-adapter pattern
- `LlmClient()` instantiated only in `adapters/api/app.py` — injection point, clean
- `rules/dice.py` imports `os` for `DND_DICE_SEED` env var at module load — one-time seed, acceptable

`rules/action_provider.py` has `BaseActionProvider` and `TradeActionProvider` with `self._` fields. These are parameterized strategy objects (injected at construction, no mutation), not mutable state — acceptable.

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `service/session.py:302` | `*args: Any` in `_fire()` | Use `object` instead of `Any` per CLAUDE.md |

**`Any` usage elsewhere:** 25 files import `Any`. Most are in LLM/JSON/content-loader contexts where the data is genuinely untyped (LLM responses, YAML dicts, JSON state blobs). These are acceptable — `object` would require excessive casting for no safety gain in these boundary modules.

**Mutable `@dataclass`:** 20 classes use `@dataclass` without `frozen=True`. All are legitimately mutable: `Entity/Creature/Character/PlayerCharacter` (HP, position, state changes), `CombatState/BattleMap` (combat progression), `ResourcePool` (uses tracking), `Round/TurnBudget` (turn state), `GameSession` (runtime state), `Settlement/Nation` (world simulation ticks), `Npc/NpcMemory` (behavior state), `Squad` (ecology movement). No violations.

## Layer Contract

All 5 layers implement the full `Layer` ABC: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. No stub implementations found.

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/actions.py` (90 lines) | `tests/unit/test_actions.py` | missing |
| `rules/weapons.py` (48 lines) | `tests/unit/test_weapons.py` | missing — weapon attack logic is partly covered by `test_combat.py` and `test_proficiency.py` but no dedicated test |

**WS test coverage** (`tests/unit/test_ws.py`): 6 tests covering invalid session, no player, turn/end_turn, action+end_turn, unknown message type, query rejection. Missing scenarios:
- Malformed JSON from client (would exercise the `json.loads` issue in Security section)
- Disconnect during active game loop

## Vision Drift

No drift detected. Sprint 007 work (save/load completeness, master controls, world inspector, fork UI, layer editor) is fully consistent with vision invariants:
- Classic mode without LLM: not affected — new features are content/UI tooling
- Single global round: not affected
- Layer independence: layer editor works via manifest.yaml + library templates, no coupling added
- Master controls through endpoints: all new controls go through service layer
- Brain swappable: brain reassignment after load was explicitly fixed (phase 1.5)
- Content is data: layer editor operates on YAML files, reinforcing this principle
