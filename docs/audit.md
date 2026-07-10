# Code Audit

> **Date**: 2026-07-10
> **Scope**: full (post Sprint 020, thermo-sweep, phases 1-4 merged)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); sprint close triage decides what is fixed now and what is deferred.

## Summary
- Dead code: 0 issues
- Code smells: 6 issues
- Security: 2 issues
- Architecture violations: 0 issues
- Convention violations: 2 issues
- Layer contract: 0 issues
- Test gaps: 5 issues
- Vision drift: 1 issue

**Total: 17 issues.** Sprint 020 materially improved the thermo targets: `GameService` stayed split, `combat_manager.py` is now a lifecycle facade with `combat_resolution.py`, `activation_manager.py` is down to activation orchestration, `ecology/layer.py` follows the politics-style submodule split, entity serialization is isolated, and the front-end god components were decomposed. No cross-layer dependency violation was found. The main fresh finding is that the new split modules still use process-global `random`, which weakens seeded replay and the simulation-core save/freeze direction.

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` clean. No `TODO/FIXME/HACK/XXX` in `src/`. | none |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/layers/entities/perception.py` (572) | Still the largest layer helper after Sprint 020; perception dispatch and per-event formatting keep growing. | Keep `perception-fail-fast` / future event-payload work in backlog; do not expand this module for simulation-core events. |
| `src/dnd_simulator/layers/entities/layer.py` (552) | Entity host + query/load/state glue remains above 400 lines even after serialization split. | Next split should follow ownership boundaries: load/restore helpers, entity CRUD helpers, query facade. |
| `src/dnd_simulator/round.py` (548) | Improved from ~623, but still owns combat turn loop, peaceful turn loop, fast-forward, reactions, listener coordination. | Backlog remains valid; simulation-core `intents` should replace the peaceful/wait path rather than polishing it locally. |
| `src/dnd_simulator/core/action_defs.py` (545) | Registry still carries 12 equip/unequip action types. Sprint 020 added backend equipment registry but preserved wire compatibility. | Defer full `equip-action-collapse` as coordinated backend/frontend/wire/i18n work. |
| `src/dnd_simulator/service/session.py` (521), `service/commands_worldbuilder.py` (535) | Still large, though cohesive. Session is especially sensitive because it bridges threads, listeners, saves, and round lifecycle. | Track size during next session/WS work; avoid putting new behavior directly in session. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | Two `eslint-disable react-hooks/exhaustive-deps` remain after decomposition. | Already backlogged; consider replacing with stable memoized inputs rather than suppressions. |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:121-128` | CORS origins are configurable, but methods and headers remain wildcard. | low |
| `src/dnd_simulator/adapters/api/schemas.py:69-93` | `GiveItemRequest` item fields (`price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, `ac_bonus`) still lack bounds. Master-only surface, but arbitrary values can create impossible game data. | low |

Verified clean/hardened: no hardcoded secrets, `.env` is gitignored, no `subprocess`, no `dangerouslySetInnerHTML`. WS keeps optional origin allow-list and token-bucket rate limiting in `routes_ws.py:90-157`.

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No cross-layer imports across different layers. `core/` imports neither layers nor adapters. `rules/` imports neither layers nor service/adapters/storage. `adapters/` do not import layers. | none | none |
| none | Fresh split modules keep the intended direction: `layers/*` depend on `core` + pure `rules`; `rules/` stays free of I/O and layer references. | none | none |

Accepted boundary imports: API schemas/routes import core enums and creation constants; `app.py` constructs `LlmClient` at the injection point; these match existing conventions.

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | Raw-YAML/dynamic-model helpers keep `Any` parameters. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/layers/ecology/movement.py:9,83`, `layers/ecology/squad_combat.py:9,106`, `layers/entities/encounters.py:112-123` | Process-global `random` is used in simulation decisions outside the seeded dice RNG. | Use injected RNG or `get_global_rng()` consistently so seeded replay and tests cover world simulation too. |

Line length is clean. Bare mutable dataclasses are still used for runtime state objects (`Creature`, `CombatState`, `TurnBudget`, `ResourcePool`, `Lair`, sessions/round controllers), which is acceptable unless they cross into value-object use.

## Layer Contract
| Layer | Issue |
|-------|-------|
| none | All 5 concrete layers implement the `Layer` ABC surface: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `src/dnd_simulator/layers/ecology/movement.py`, `squad_combat.py`, `layers/entities/encounters.py` | Seeded deterministic replay tests for random encounter count, roam movement, retreat destination. | missing; ties to the fresh RNG finding |
| `src/dnd_simulator/adapters/api/routes_ws.py` | Malformed JSON unit/integration test. | backlogged `test-gap-ws-malformed-json` |
| `src/dnd_simulator/adapters/api/routes_ws.py` / `service/session.py` | Disconnect during active loop and reconnect while NPC turn is in flight. | backlogged `test-gap-ws-disconnect`, known reload race remains out of sprint scope |
| `src/dnd_simulator/round.py` / activation path | Fast-forward wait with co-located rule NPC. | backlogged `test-gap-ws-fastforward`; current backlog has a live repro |
| `frontend/src/components/game/EventLog.tsx`, `SchemaForm.tsx` | Tests that would let the exhaustive-deps suppressions be removed safely. | backlogged `event-log-eslint-suppress`, `schema-form-eslint-suppress` |

No skipped or xfailed tests. The mechanical "rules module name → test_rules_*.py" script reports many false positives because this repo uses semantic test names (`test_action_provider_isolated.py`, `test_combat_pipeline.py`, etc.); I did not count those as direct gaps.

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| Split ecology/entities simulation modules still use process-global `random` for encounter rolls, squad roam movement, and retreat selection. | Simulation-core says the world is frozen on a half-step and should be replayable/testable without hidden external state. Sprint 020 phase 1 already pushed handlers toward injected RNG. | Medium. Not a layer-direction violation and not a current gameplay blocker, but it undercuts deterministic replay/save-schema work. |

No drift found for the larger simulation-core re-scope: activation logic was isolated without polishing, common materialization tracker was intentionally deferred, combat/peaceful loop merge was correctly cancelled, and serialization dedup moves toward the save-schema prerequisite.

## Sprint 020 Backlog Reconciliation
| Item | Audit Result |
|------|--------------|
| `round-growing` | Partially closed by Sprint 020 (awareness builder + movement helper + one activation per loop), but still a large module. Backlog wording updated to 548 lines and simulation-core remaining work. |
| `activation-manager-growing` | Closed as originally scoped: activation is isolated and encounters/materialization are split. Marked fixed in backlog. |
| `god-class-combat-manager` | Closed as originally scoped: combat resolution split out and relation helper extracted. Marked fixed in backlog. |
| `session-serialization-duplication` | Already closed before Sprint 020; no change. |
| `equip-action-collapse` | Still deferred by explicit phase 3 decision. Keep backlog entry. |
| `event-log-eslint-suppress`, `schema-form-eslint-suppress` | Still present after frontend decomposition. Keep backlog entries. |
| `any-to-object-sweep`, `dict-str-object-overuse` | Partially reduced by typed query work, but still present in content/service/adapter/save boundaries. Keep backlog entries. |

## Triage Outcome

Coordinator decision: no blockers. Quick-fix applied: `entity_serialization.py` now returns `dict[str, object]`; `make check-backend` stayed green. New backlog entries added for `layer-rng-threading` and `test-gap-world-rng-determinism`.
