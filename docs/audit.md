# Code Audit

> **Date**: 2026-07-12
> **Scope**: full codebase, post Sprint 022 Phase 5 (`9f84fd4`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary
- Dead code: 0 issues
- Code smells: 4 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 3 issues
- Layer contract: 0 issues
- Test gaps: 2 issues
- Vision drift: 0 issues

**Total: 13 issues.** Phase 5 closed the previous audit's only fresh operational risk: round shutdown now uses a bounded deadline, preserves live lifecycle references after timeout, and prevents disconnect, load, or eviction from continuing an unsafe operation. Focused unit tests cover timeout, retry, reconnect, load, and deferred eviction; Phase 5 E2E is green. No new sprint blocker was found.

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` is clean. No `TODO/FIXME/HACK/XXX` in `src/`; no Phase 5 lifecycle branch is orphaned. | none |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/session.py` (726 lines) | `known, worsened`: grew from 694 to 726 lines. It owns listener and round transitions, two locking domains, snapshot construction, payload composition, player status, movement resolution, eviction timers, journey presentation, and bounded-stop policy. | Split lifecycle/locking from transport payload builders before adding trigger activation. Keep `long-func-start-round` and `test-gap-session` as the canonical backlog items. |
| `src/dnd_simulator/layers/entities/layer.py` (616 lines), `layers/entities/perception.py` (572 lines), `round.py` (571 lines), `core/action_defs.py` (554 lines), `service/commands_worldbuilder.py` (535 lines) | `known`: large modules remain. Phase 5 did not increase these files. | Keep `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, and `action-defs-growing`; avoid folding trigger-table logic into the same files. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress` and `schema-form-eslint-suppress`; remove only with targeted tests. |
| `frontend/src/transport/apiClient.ts` (391 lines) | `known`: the client is close to the 400-line audit threshold and contains session, player, content, save, and master operations. | Keep `api-client-growing`; split by domain when the next control-interface surface lands. |

The former unbounded `thread.join()` finding is closed. `_stop_round()` waits at most `DND_ROUND_STOP_TIMEOUT_SECONDS`, retains the same round, brain, and thread on timeout, and clears them only after that thread exits.

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:150-154` | `known`: CORS origins are configurable, but the default origins, methods, and headers are wildcard. Acceptable for local development, unsafe for non-local deployment. | low |
| `src/dnd_simulator/adapters/api/routes_ws.py:149-154` | `known`: WS origin validation is optional and disabled by default. Session IDs remain the only access handle. | medium |
| `src/dnd_simulator/adapters/api/schemas.py:69-103` | `known`: item creation fields including `price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, and `ac_bonus` lack bounds. | low |
| `src/dnd_simulator/adapters/api/app.py:174-177` | `known`: `/api/frontend-error` accepts arbitrary JSON without a Pydantic schema or size limit. | low |

Verified clean/hardened: no hardcoded secrets, `.env` is gitignored, no subprocess calls, no `dangerouslySetInnerHTML`, and WS input has token-bucket rate limiting. Phase 5 changed internal thread lifecycle only and added no external input surface.

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No cross-layer imports across different layers. `core/` imports neither layers nor adapters. `rules/` imports neither layers/service/adapters/storage nor I/O libraries. Adapters do not import layers. | none | none |

The bounded-stop policy remains in `GameSession`, where round lifecycle and locks are owned. Load still crosses the boundary through `replace_world_state()` and fails before invoking the loader when the old round cannot stop.

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:256`, `layers/common/rng_state.py` | `known/accepted`: RNG state uses `list[Any]` because `random.Random.getstate()` has an implementation-defined nested shape. | Prefer `object` over `Any`; keep the exception localized unless a typed RNG-state codec is introduced. |
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | `known`: raw-YAML/dynamic-model helpers still use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known/accepted`: mutable dataclasses remain for explicit runtime state. | Fine for stateful objects; require `frozen=True` for value objects. |

Line length is clean.

## Layer Contract
| Layer | Issue |
|-------|-------|
| none | All concrete layers implement `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, and `load_state`. Phase 5 did not change a layer contract. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `src/dnd_simulator/adapters/api/routes_ws.py` | Malformed non-object JSON and malformed action parameter shapes, not only invalid JSON and unknown message types. | `known`: `test-gap-ws-malformed-json` / `action-params-validation` |
| `tests/unit/test_periodic_autosave.py` | Shutdown path where final `service.autosave_all_sessions()` raises. | `known`, missing; `test-gap-shutdown-autosave-failure` |

The former round-stop gap is closed. Tests now cover a blocked callback, bounded failure, lifecycle-reference preservation, idempotent start, successful retry, parked-player happy path, disconnect logging, deferred eviction, and load fail-fast with unchanged world/RNG/cache.

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Bounded shutdown preserves the single global round: a live old thread blocks replacement and a second round cannot start. | none |

Classic mode remains complete without LLM, active creatures share one round, layers remain callback-separated, brains remain swappable, and master mutations still go through service endpoints.

## Sprint 022 Phase 5 Reconciliation
| Previous Finding | Audit Result |
|------------------|--------------|
| Unbounded round-thread join | Closed: bounded join with `RoundStopTimeoutError`, structured logging, and preserved lifecycle references. |
| Missing stuck-round lifecycle tests | Closed: unit coverage spans stop, reconnect, disconnect, load, eviction, recovery, and the normal parked-player path. |
| Unsafe continuation after stop timeout | Closed: load does not replace world state; eviction does not autosave or remove the session; reconnect does not create a second loop. |
