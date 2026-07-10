# Code Audit

> **Date**: 2026-07-10
> **Scope**: full codebase, post Sprint 021 (`b5cfc5d`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary
- Dead code: 0 issues
- Code smells: 5 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 3 issues
- Layer contract: 0 issues
- Test gaps: 4 issues
- Vision drift: 0 issues

**Total: 16 issues.** Sprint 021 closed the important Sprint 020 audit risk: world randomness is now owned by per-layer RNGs, layer and dice RNG state are in the versioned `SaveGame` envelope, legacy saves are rejected, and periodic autosave logs failures instead of suppressing them. The remaining fresh risk is concurrency around save/load/autosave while a round thread can mutate the same session world.

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` is clean. No `TODO/FIXME/HACK/XXX` in `src/`. | none |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/commands_save.py:18`, `src/dnd_simulator/adapters/api/app.py:50`, `src/dnd_simulator/service/session.py:461` | `fresh`: saves and autosaves snapshot `session.world` without taking a session/world lock, while `Round.run_loop()` can mutate the same world on a background thread. The new periodic autosave makes this path regular, not just shutdown/evict. | Add one session-level save/load critical section or a world snapshot API that coordinates with the round lifecycle. Cover manual save, autosave, periodic autosave, evict autosave, and load. |
| `src/dnd_simulator/service/session.py` (606 lines) | `known`: grew from 521 to 606 lines after spectator/grace/autosave lifecycle hardening. It now owns listener lifecycle, thread lifecycle, payload construction, player status helpers, movement resolution, and eviction timers. | Continue `long-func-start-round` / `test-gap-session`; avoid adding new session behavior until lifecycle and payload builders are split. |
| `src/dnd_simulator/layers/entities/layer.py` (584 lines), `layers/entities/perception.py` (572 lines), `round.py` (548 lines), `core/action_defs.py` (545 lines), `service/commands_worldbuilder.py` (535 lines) | `known`: large modules remain after Sprint 020 decomposition. Sprint 021 added save/load state to the entities layer, but no new god-object boundary was introduced. | Keep existing backlog: `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, `action-defs-growing`. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress` and `schema-form-eslint-suppress`; remove only with targeted tests. |
| `src/dnd_simulator/layers/entities/entity_serialization.py:38`, `layers/entities/save_models.py` | `known/accepted`: entities save models are now authoritative, but `player_to_save_data()` still emits a parse-player compatibility subset. This is not a second save format for `SaveGame`, but it is still a compatibility bridge to watch as schema v1 evolves. | Do not reintroduce hand-written save envelopes. When player parsing moves fully onto save models, remove the bridge. |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:153-160` | `known`: CORS origins are configurable, but default origins, methods, and headers are wildcard. Acceptable for local dev, unsafe for non-local deployment. | low |
| `src/dnd_simulator/adapters/api/routes_ws.py:149-154` | `known`: WS origin validation is optional and disabled by default. Session IDs are still the only access handle. | medium |
| `src/dnd_simulator/adapters/api/schemas.py:69-93` | `known`: `GiveItemRequest` item fields (`price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, `ac_bonus`) still lack bounds. Master-only surface, but impossible game data can be created. | low |
| `src/dnd_simulator/adapters/api/app.py:177-180` | `known`: `/api/frontend-error` accepts arbitrary JSON without a Pydantic schema or size limit. | low |

Verified clean/hardened: no hardcoded secrets, `.env` is gitignored, no `subprocess`, no `dangerouslySetInnerHTML`, WS has token-bucket rate limiting, and autosave errors now log.

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No cross-layer imports across different layers. `core/` imports neither layers nor adapters. `rules/` imports neither layers/service/adapters/storage nor I/O libraries. `adapters/` do not import layers. | none | none |

Accepted boundary imports: API schemas/routes import core enums and creation constants; `app.py` constructs `LlmClient` at the service injection point; `storage/save_schema.py` imports layer state models because the versioned save envelope intentionally lives outside `core`.

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:228`, `layers/common/rng_state.py` | `fresh/accepted`: RNG state uses `list[Any]` because `random.Random.getstate()` is nested tuple/list data with implementation-defined shape. | Prefer `object` over `Any`, but keep this exception localized unless a typed RNG-state codec is introduced. |
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | `known`: raw-YAML/dynamic-model helpers still use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known/accepted`: mutable dataclasses remain for runtime state (`GameSession`, `Round`, creatures, combat state, resource pools, lairs, world models). | Fine for stateful objects; revisit only when a model is meant to be a value object. |

Line length is clean.

## Layer Contract
| Layer | Issue |
|-------|-------|
| none | All concrete layers implement the `Layer` ABC surface: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. Sprint 021 state models preserve the dict-facing Layer interface while validating through Pydantic internally. |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `src/dnd_simulator/service/commands_save.py`, `service/session.py`, `adapters/api/app.py` | Concurrency test for save/autosave/load while a round thread is active and mutating world state. | `fresh`, missing |
| `src/dnd_simulator/service/commands_save.py:65-75`, `service/session.py:461-578` | Load while connected/in combat should pause or restart round lifecycle deterministically before the player reconnects. | `known`: `load-combat-round-resume` |
| `src/dnd_simulator/adapters/api/routes_ws.py` | Malformed non-object JSON from client, not only invalid JSON / unknown message type. | `known`: extends `test-gap-ws-malformed-json` / `action-params-validation` |
| `tests/unit/test_periodic_autosave.py` | Shutdown path where final `service.autosave_all_sessions()` itself raises. | `fresh`, missing; likely low severity because startup/shutdown should expose hard failures, but the behavior is currently unpinned |

No skipped or xfailed tests. The mechanical "rules module name -> test_rules_*.py" script still reports false positives because this repo uses semantic test names (`test_combat.py`, `test_movement.py`, `test_action_provider_isolated.py`, etc.); I did not count those as direct gaps.

## Vision Drift
| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Sprint 021 aligns with simulation-core: save schema v1, seeded layer RNG, RNG state persistence, and periodic autosave all support the "world frozen on a half-step" direction. | none |

Classic mode still works without LLM, time remains a single session timeline, layers remain callback-separated, and master control still goes through service endpoints.

## Sprint 021 Backlog Reconciliation
| Item | Audit Result |
|------|--------------|
| `save-schema` | Substantively closed for v1: `SaveGame(schema_version=1)` is the single envelope, typed layer states are authoritative, legacy saves are rejected. Future simulation-core fields will extend v1/v2 rather than reopening the old manual format. |
| `layer-rng-threading` | Closed: encounter rolls, squad movement, retreat, lair depletion, weather, politics, ecology, and entities use owned RNG streams rather than process-global `random`. |
| `test-gap-world-rng-determinism` | Closed: `tests/unit/test_world_seed.py` pins same-seed full-world replay, different-seed divergence, layer seed streams, and encounter spawn replay. |
| `periodic-autosave-scheduler` | Closed: FastAPI lifespan starts `_periodic_autosave()` with `DND_AUTOSAVE_SECONDS`, cancels it before final shutdown autosave, and tests interval/error/cancel behavior. |
| `silent-failure-autosave` | Closed for the three Sprint 021 targets: create-player autosave, empty-session autosave, and periodic autosave log exceptions. |
| `saved-session-accumulation` | Partially addressed: integration suite cleanup is in place; UX pagination/filter/TTL remains a separate product/debt question. |
| `load-combat-round-resume` | Still known and not duplicated: phase-2 E2E showed save JSON correct, but load/reconnect can advance combat before the UI stabilizes. |
