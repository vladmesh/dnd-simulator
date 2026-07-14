# Code Audit

> **Date**: 2026-07-14
> **Scope**: full codebase, final audit after Sprint 023 Phase 8 (`c820d3c`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary

- Dead code: 0 issues
- Code smells: 3 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 4 issues
- Layer contract: 0 issues
- Test gaps: 0 issues
- Vision drift: 0 issues

**Total: 11 issues.** The Phase 8 Paladin E2E alignment, level-up modal repair, and lair-core lifecycle fix introduce no architecture, transport, or test-coverage finding. No sprint blocker was found; the remaining items are known security, maintainability, and style debt.

## Dead Code

| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` is clean. No `TODO/FIXME/HACK/XXX` remains in `src/`. The new event-runtime, transport, WS-envelope, autosave, and lair-death write-back paths have production callers. | none |

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/session.py` (502 lines) | `known, improved`: Phase 5 extracted transport payload builders and reduced the module from 741 lines, but it still owns round lifecycle, listener dispatch, save snapshots, and three locking domains. | Keep `test-gap-session`; extract a lifecycle/locking collaborator before another session-control feature. |
| `src/dnd_simulator/layers/entities/layer.py` (568 lines), `layers/entities/perception.py` (585 lines), `round.py` (574 lines), `core/action_defs.py` (564 lines), `service/commands_worldbuilder.py` (535 lines) | `known, improved`: trigger runtime, event logging, and world perception moved out, but these facades remain over the audit threshold. | Keep `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, and `action-defs-growing`; extract only along an existing responsibility boundary. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress` and `schema-form-eslint-suppress`; remove only with focused effect tests. |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:151-157` | `known`: CORS origins are configurable, but the default origins, methods, and headers are wildcard. Acceptable for local development, unsafe for non-local deployment. | low |
| `src/dnd_simulator/adapters/api/routes_ws.py:160-166` | `known`: WS origin validation is optional and disabled by default. Session IDs remain the only access handle. | medium |
| `src/dnd_simulator/adapters/api/schemas.py:69-103` | `known`: item creation fields including `price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, and `ac_bonus` lack bounds. | low |
| `src/dnd_simulator/adapters/api/app.py:174-177` | `known`: `/api/frontend-error` accepts arbitrary JSON without a Pydantic schema or size limit. | low |

Verified clean or hardened: no hardcoded secrets, `.env` is gitignored, no subprocess calls, no `dangerouslySetInnerHTML`, and WS input has token-bucket rate limiting. Player and spectator WS paths now reject syntactically valid non-object JSON with a recoverable protocol error.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No imports cross between distinct simulation layers. `core/` imports neither layers nor service/round/adapters; `rules/` has no I/O or upward dependencies; adapters do not import layers directly. | none | none |

The Phase 5 extractions retain the dependency flow: typed event payloads stay in `core`, entity runtime collaborators remain within the entities layer, and WS handling delegates game state to `GameSession`.

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:304`, `layers/common/rng_state.py` | `known, accepted`: RNG state uses `list[Any]` because `random.Random.getstate()` has an implementation-defined nested shape. | Prefer `object` over `Any`; keep the exception localized unless a typed RNG-state codec is introduced. |
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | `known`: raw-YAML and dynamic-model helpers use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/core/events.py:20-23` | `new`: generic dataclass encoding uses `Any` and `cast(Any, value)` in the typed event codec. | Replace the dynamic bridge with an object-safe dataclass encoder or document a narrow exception. |
| `src/dnd_simulator/service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known, accepted`: mutable dataclasses model explicit runtime state. | Use `frozen=True` for value objects; document stateful exceptions. |

Line length is clean.

## Layer Contract

| Layer | Issue |
|-------|-------|
| none | Geography, politics, settlements, ecology, and entities implement `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, and `load_state`. |

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| none | Player and spectator non-object WS JSON are covered; the final shutdown-autosave failure logs once while lifespan exits normally; Master `current_hp=0` depletes a lair without a duplicate roster through save/load and reconnect. | previous gaps fixed in Sprint 023 Phase 5; Phase 8 lifecycle regression covered by integration and targeted E2E |

## Vision Drift

| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Typed events, trigger lifecycle, transport extraction, WS containment, and the Phase 8 service-mediated lair death preserve classic-mode, the single global round, layer independence, service-mediated master controls, swappable brains, and YAML content. | none |
