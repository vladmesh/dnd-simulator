# Code Audit

> **Date**: 2026-07-13
> **Scope**: full codebase, post Sprint 023 Phase 4 (`aa58956`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary

- Dead code: 0 issues
- Code smells: 5 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 3 issues
- Layer contract: 0 issues
- Test gaps: 2 issues
- Vision drift: 0 issues

**Total: 14 issues.** Sprint 023 added typed event payloads, ecology death write-back, activation triggers, GM controls, and action-error containment. No sprint blocker was found. One fresh maintainability finding remains in the event migration bridge; the other findings are known risks or known files that grew during the sprint.

## Dead Code

| File | Issue | Action |
|------|-------|--------|
| none | `uv run ruff check src/ --select F401` is clean. No `TODO/FIXME/HACK/XXX` remains in `src/`. New event, trigger, GM-control, ecology write-back, and action-parameter modules all have production callers. | none |

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/session.py` (741 lines) | `known, worsened`: grew from 726 to 741 lines. It still owns round lifecycle, two locking domains, save snapshots, listener dispatch, transport payloads, player status, movement, eviction, and now trigger fields in creature payloads. | Split lifecycle and locking from transport payload builders before adding more control surfaces. Keep `long-func-start-round` and `test-gap-session` canonical. |
| `src/dnd_simulator/layers/entities/layer.py` (666 lines), `layers/entities/perception.py` (629 lines), `round.py` (572 lines), `core/action_defs.py` (564 lines), `service/commands_worldbuilder.py` (535 lines) | `known, worsened`: the two entities modules grew by 50+ lines for trigger dispatch and typed perception. The other large modules remain above the audit threshold. | Keep `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, and `action-defs-growing`. The next entities change should extract trigger lifecycle and event-location/logging responsibilities instead of extending the facade. |
| `src/dnd_simulator/core/events.py` (489 lines), `core/models.py:268-326` | `fresh`: 44 typed payload classes share a temporary mapping facade, while `Event.__post_init__` still normalizes legacy dictionaries and attack payloads. The public contract therefore has two representations and uses `Any`/casts in the compatibility path after production emitters were migrated. | Migrate remaining tests and callers to typed payload constructors, remove the dictionary normalization and mapping facade, then split payload definitions or codecs from the registry if the taxonomy keeps growing. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress` and `schema-form-eslint-suppress`; remove only with targeted tests. |
| `frontend/src/transport/apiClient.ts` (415 lines) | `known, worsened`: crossed the 400-line threshold after adding activation endpoints. The client contains session, player, content, save, catalog, and master-control operations. | Keep `api-client-growing`; split by transport domain before the next control-interface surface. |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `src/dnd_simulator/adapters/api/app.py:150-154` | `known`: CORS origins are configurable, but the default origins, methods, and headers are wildcard. Acceptable for local development, unsafe for non-local deployment. | low |
| `src/dnd_simulator/adapters/api/routes_ws.py:149-154` | `known`: WS origin validation is optional and disabled by default. Session IDs remain the only access handle. | medium |
| `src/dnd_simulator/adapters/api/schemas.py:69-103` | `known`: item creation fields including `price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, and `ac_bonus` lack bounds. | low |
| `src/dnd_simulator/adapters/api/app.py:174-177` | `known`: `/api/frontend-error` accepts arbitrary JSON without a Pydantic schema or size limit. | low |

Verified clean or hardened: no hardcoded secrets, `.env` is gitignored, no subprocess calls, no `dangerouslySetInnerHTML`, and WS input has token-bucket rate limiting. GM activation mutations go through service methods under the world-mutation gate. Trigger match fields are validated strictly against the typed payload schema at content load.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No imports cross between different simulation layers. `core/` imports neither layers nor adapters; `rules/` imports neither layers, service, adapters, LLM, nor storage; adapters do not import concrete layers. | none | none |

Sprint 023 preserves the dependency flow. Ecology consumes typed core events through `handle_event`; activation triggers live in core plus the entities-layer index; GM routes delegate to `GameService`; action handlers use explicit input-rejection errors instead of transport concerns.

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `src/dnd_simulator/storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:304`, `layers/common/rng_state.py` | `known/accepted`: RNG state uses `list[Any]` because `random.Random.getstate()` has an implementation-defined nested shape. | Prefer `object` over `Any`; keep the exception localized unless a typed RNG-state codec is introduced. |
| `src/dnd_simulator/content_loader/monsters.py:129`, `content_loader/refs.py:62` | `known`: raw-YAML and dynamic-model helpers still use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `src/dnd_simulator/service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known/accepted`: mutable dataclasses remain for explicit runtime state. New `ActivationTrigger` is also intentionally mutable runtime state; definitions and conditions are frozen. | Fine for stateful objects; require `frozen=True` for value objects. |

Line length is clean.

## Layer Contract

| Layer | Issue |
|-------|-------|
| none | Geography, politics, settlements, ecology, and entities implement `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, and `load_state`. Ecology's new death write-back stays inside `handle_event`. |

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `src/dnd_simulator/adapters/api/routes_ws.py:119-124,217-222` | Non-object JSON values such as `[]`, `null`, or a string should return a protocol error instead of reaching `.get()` and closing the socket. | `known`, missing: malformed action parameters are now contained by dispatcher tests and a live missing-parameter regression, but the raw JSON shape is still unvalidated. Keep `test-gap-ws-malformed-json`. |
| `tests/unit/test_periodic_autosave.py` | Shutdown path where final `service.autosave_all_sessions()` raises. | `known`, missing; keep `test-gap-shutdown-autosave-failure`. |

New sprint behavior is otherwise covered: every `EventType` is pinned to a payload contract; trigger parsing, matching, activation, save/load, self-completion, GM overrides, ecology death write-back, REST endpoints, frontend controls, and live action-error recovery have focused tests.

## Vision Drift

| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Typed events and trigger matching work with RuleBrain and without LLM; all creatures use the same event and activation path; ecology write-back crosses layers through events; GM controls cross service endpoints under the world gate; trigger state is brain-independent and persisted. | none |

The new trigger table advances the planned simulation-core chain without adding player-only simulation rules, parallel rounds, hardcoded world-specific behavior, or a required LLM path.
