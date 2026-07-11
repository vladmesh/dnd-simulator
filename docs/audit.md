# Code Audit

> **Date**: 2026-07-12
> **Scope**: full codebase, post Sprint 022 (`eef9303`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary
- Dead code: 0 issues
- Code smells: 5 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 3 issues
- Layer contract: 0 issues
- Test gaps: 3 issues
- Vision drift: 0 issues

**Total: 15 issues.** Sprint 022 closed both lifecycle findings from the previous audit: save/autosave/load share the session world-state gate with round mutations, and a loaded combat stays paused until a player listener reconnects. Anchors and persisted wait/sleep/travel intents follow the single-timeline vision and have focused unit, integration, and browser coverage. The fresh operational risk is an unbounded round-thread join during disconnect and load.

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` is clean. No `TODO/FIXME/HACK/XXX` in `src/`; the replaced `Creature.wake_at_seconds` field and production `WAIT + travel_to` path are gone. | none |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/session.py:653` | `fresh`: `_stop_round()` uses unbounded `thread.join()`. A round callback can block in the WS bridge for up to its own timeout, and any future non-terminating callback would hang disconnect, load, or eviction indefinitely. | Use a bounded join, log/raise a clear lifecycle failure if the thread remains alive, and pin the timeout path with a test. Do not replace the world while the old thread is alive. |
| `src/dnd_simulator/service/session.py` (694 lines) | `known, worsened`: grew from 606 to 694 lines. It now owns listener and round transitions, two locking domains, snapshot construction, payload composition, player status, movement resolution, eviction timers, and journey presentation. | Split lifecycle/locking from transport payload builders before adding trigger activation. Keep `long-func-start-round` and `test-gap-session` as the canonical backlog items. |
| `src/dnd_simulator/layers/entities/layer.py` (616 lines), `layers/entities/perception.py` (572 lines), `round.py` (571 lines), `core/action_defs.py` (554 lines), `service/commands_worldbuilder.py` (535 lines) | `known`: large modules remain. Sprint 022 added intent state and activation traversal to the entities layer and round without creating a new god-object boundary. | Keep `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, and `action-defs-growing`; avoid folding trigger-table logic into the same files. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress` and `schema-form-eslint-suppress`; remove only with targeted tests. |
| `frontend/src/transport/apiClient.ts` (391 lines) | `known`: the client is close to the 400-line audit threshold and contains session, player, content, save, and master operations. | Keep `api-client-growing`; split by domain when the next control-interface surface lands. |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:150-154` | `known`: CORS origins are configurable, but the default origins, methods, and headers are wildcard. Acceptable for local development, unsafe for non-local deployment. | low |
| `src/dnd_simulator/adapters/api/routes_ws.py:149-154` | `known`: WS origin validation is optional and disabled by default. Session IDs remain the only access handle. | medium |
| `src/dnd_simulator/adapters/api/schemas.py:69-103` | `known`: item creation fields including `price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, and `ac_bonus` lack bounds. | low |
| `src/dnd_simulator/adapters/api/app.py:174-177` | `known`: `/api/frontend-error` accepts arbitrary JSON without a Pydantic schema or size limit. | low |

Verified clean/hardened: no hardcoded secrets, `.env` is gitignored, no subprocess calls, no `dangerouslySetInnerHTML`, and WS input has token-bucket rate limiting. Sprint 022 did not add a new externally writable intent endpoint; travel is dispatched through the existing validated action boundary.

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No cross-layer imports across different layers. `core/` imports neither layers nor adapters. `rules/` imports neither layers/service/adapters/storage nor I/O libraries. Adapters do not import layers. | none | none |

Accepted boundaries: intent completion lives in the entities layer because it mutates hosted creatures and delegates only pure resource math to `rules/`; `LocationGraph` remains core data/lookup; `app.py` constructs `LlmClient` at the service injection point.

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:256`, `layers/common/rng_state.py` | `known/accepted`: RNG state uses `list[Any]` because `random.Random.getstate()` has an implementation-defined nested shape. | Prefer `object` over `Any`; keep the exception localized unless a typed RNG-state codec is introduced. |
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | `known`: raw-YAML/dynamic-model helpers still use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known/accepted`: mutable dataclasses remain for explicit runtime state. New intent models themselves are frozen. | Fine for stateful objects; require `frozen=True` for value objects. |

Line length is clean.

## Layer Contract
| Layer | Issue |
|-------|-------|
| none | All concrete layers implement `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, and `load_state`. Intent persistence extends the typed entities state without changing the dict-facing Layer contract. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `src/dnd_simulator/service/session.py:653` | A blocking/stuck round callback must not hang `stop_round()`, disconnect eviction, or `load_game()` indefinitely. | `fresh`, missing |
| `src/dnd_simulator/adapters/api/routes_ws.py` | Malformed non-object JSON and malformed action parameter shapes, not only invalid JSON and unknown message types. | `known`: `test-gap-ws-malformed-json` / `action-params-validation` |
| `tests/unit/test_periodic_autosave.py` | Shutdown path where final `service.autosave_all_sessions()` raises. | `known`, missing; `test-gap-shutdown-autosave-failure` |

No skipped or xfailed tests. Sprint 022 added direct coverage for anchor activation, wait/sleep completion, route calculation, mid-route persistence, session-level interruption, world-state locking, atomic load, and reconnect-driven resume. The mechanical rules-module naming script still produces false positives because tests use semantic names; those were not counted.

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Sprint 022 implements the documented simulation-core invariants: anchors are creature properties, intents are persisted, travel follows graph edges on one global timeline, and interruptions are built-in and idempotent. | none |

Classic mode remains complete without LLM, active creatures share one round, layers remain callback-separated, brains remain swappable, and master mutations still go through service endpoints.

## Sprint 022 Backlog Reconciliation
| Item | Audit Result |
|------|--------------|
| `save-round-concurrency` | Closed: round mutations and save snapshots share the session world-state gate; save/load/autosave/evict paths build the same `SaveGame` snapshot. |
| `load-combat-round-resume` | Closed: load stops the old round, clears callbacks/cache, replaces state under the gate, and resumes only from the player connection path. |
| `anchor-as-property` | Closed: `Creature.is_anchor` is persisted and activation no longer checks `PlayerCharacter`. |
| `intents` | Closed for the Sprint 022 contract: persisted wait, sleep, and graph travel with timer/damage/combat/scene interruption. Declarative brain gate and trigger tables remain separate future work. |
| `wait-no-fastforward-with-npc` | Closed: fast-forward selects the nearest intent wake point even with dormant RuleBrain NPCs present. |
| `travel-action-type` | Closed: travel has its own action and `TravelIntent`; the former `WAIT + travel_to` production path is removed. |
| `attack-buttons-accessible-names` | Closed: attack controls include target-aware names keyed by entity identity, with EN/RU and browser coverage. |
