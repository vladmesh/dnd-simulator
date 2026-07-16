# Code Audit

> **Date**: 2026-07-16
> **Scope**: full codebase, post-Sprint 024 (playtest-quick-wins, `f74aa18`)

> Transient snapshot. Canonical tracking lives in [BACKLOG.md](BACKLOG.md); known backlog items are marked `known` and should not be duplicated during triage.

## Summary

- Dead code: 1 issue
- Code smells: 4 issues
- Security: 4 issues
- Architecture violations: 0 issues
- Convention violations: 4 issues
- Layer contract: 0 issues
- Test gaps: 0 issues
- Vision drift: 0 issues

**Total: 13 issues.** Sprint 024 (movement-budget unification, log gating, item props payload + details card, i18n) introduces no architecture, security, or test-coverage regression. Two new low-severity maintainability findings; the rest is carried-forward known debt. No sprint blocker.

## Dead Code

| File | Issue | Action |
|------|-------|--------|
| `layers/entities/awareness_builder.py:404` | `new, FIXED in triage`: `check_faction_hostility(query_fn)` lost its last production caller in the sprint 024 relation-fn refactor — both awareness paths now call `_hostility_from_relation` with a prebuilt callback. The public wrapper was exercised only by tests. | fixed 2026-07-16: wrapper removed; tests repointed via a `_check_hostility` helper that mirrors the production path |

`uv run ruff check src/ --select F401` is clean; no `TODO/FIXME/HACK/XXX` in `src/`. New sprint 024 helpers (`item_props`, `item_info`, `build_action_result`, `ItemDetails`) all have production callers.

## Code Smells

| File | Issue | Suggestion |
|------|-------|------------|
| `src/dnd_simulator/service/session.py` (498 lines) | `known, improved`: `on_action` payload assembly moved to `build_action_result` (transport_payloads), dropping the module below 500 lines, but it still owns round lifecycle, listener dispatch, save snapshots, and three locking domains. | Keep `test-gap-session`; extract a lifecycle/locking collaborator before another session-control feature. |
| `layers/entities/perception.py` (591 lines), `round.py` (574), `layers/entities/layer.py` (568), `core/action_defs.py` (565), `service/commands_worldbuilder.py` (535) | `known`: facades over the 400-line audit threshold; perception grew +6 lines (second-wind zero-heal branch). | Keep `entities-layer-regrowth`, `perception-fail-fast`, `round-growing`, `action-defs-growing`; extract only along an existing responsibility boundary. |
| `service/session.py:31` | `new, low, FIXED in triage`: imported underscore-private `_reaction_to_dict` from `transport_payloads` across a module boundary. | fixed 2026-07-16: renamed to public `reaction_to_dict`. |
| `frontend/src/components/game/EventLog.tsx:244`, `frontend/src/components/master/SchemaForm.tsx:62` | `known`: two `eslint-disable react-hooks/exhaustive-deps` suppressions remain. | Keep `event-log-eslint-suppress`, `schema-form-eslint-suppress`; remove only with focused effect tests. |

## Security

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `adapters/api/app.py:151-157` | `known` (`cors-wildcard`): CORS origins are configurable, but `allow_methods`/`allow_headers` stay wildcard. Acceptable for local dev, unsafe for non-local deployment. | low |
| `adapters/api/routes_ws.py:160-166` | `known` (`ws-origin-optional`): WS origin validation is optional and disabled by default; session IDs remain the only access handle. | medium |
| `adapters/api/schemas.py:69-103` | `known` (`item-create-bounds`): item creation fields (`price`, `reach`, `base_ac`, `max_dex_bonus`, `strength_req`, `ac_bonus`) lack bounds. | low |
| `adapters/api/app.py:174-177` | `known` (`frontend-error-endpoint`): `/api/frontend-error` accepts arbitrary JSON without a schema or size limit. | low |

Verified clean or hardened: no hardcoded secrets, `.env` gitignored, no subprocess calls, no `dangerouslySetInnerHTML` (the new `ItemDetails` card renders plain JSX text), WS input keeps token-bucket rate limiting on both player and spectator paths. The new `props` payload is built server-side from typed defs (enums → `.value`), no user-controlled strings.

## Architecture Violations

| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| none | No imports cross between distinct simulation layers (only same-package and `layers/common/rng_state`). `core/` imports neither layers nor service/round/adapters; `rules/` has no I/O or upward imports; adapters import only core enums/schemas and go through the service. `LlmClient` is constructed only in `adapters/api/app.py`. | none | none |

Sprint 024 respects the flow: `item_props`/`item_info` live in `core/awareness.py` beside the dataclasses they build; movement-budget accounting stayed in `rules/handlers/movement.py` (handler-owned, dispatcher keeps MOVE as FREE); player-only gating of `error`/`budget` lives in `service/transport_payloads.build_action_result`, not in the adapter.

## Convention Violations

| File:Line | Violation | Rule |
|-----------|-----------|------|
| `storage/save_schema.py:41`, `layers/*/state.py`, `layers/entities/save_models.py:304`, `layers/common/rng_state.py` | `known, accepted`: RNG state uses `list[Any]` — `random.Random.getstate()` has an implementation-defined nested shape. | Prefer `object` over `Any`; keep the exception localized. |
| `content_loader/monsters.py:129`, `content_loader/refs.py:62`, `service/*` (`dict[str, Any]` transport payloads) | `known`: raw-YAML/dynamic-model helpers and service payload dicts use `Any`. | Existing `any-to-object-sweep` / `any-encounter-entries`. |
| `core/events.py:20-23` | `known`: generic dataclass codec uses `Any` and `cast(Any, value)`. | Tracked as a sub-item of `any-to-object-sweep` (Sprint 023 triage). |
| `service/session.py`, `round.py`, `core/character.py`, `core/combat.py`, `core/resource.py`, layer model files | `known, accepted`: mutable dataclasses model explicit runtime state. | Use `frozen=True` for value objects; document stateful exceptions. |

Line length is clean. New sprint 024 user-visible strings all go through `_()` (backend) / `t()` (frontend); `.po`/`.mo` updated.

## Layer Contract

| Layer | Issue |
|-------|-------|
| none | Geography, politics, settlements, ecology, and entities implement `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. Unchanged since the 2026-07-14 audit. |

## Test Gaps

| Source File | Expected Test | Status |
|-------------|---------------|--------|
| none | Sprint 024 code is covered: `test_item_props.py` (typed-def resolution + JSON guard over all 31 catalog entries), `test_handlers_movement.py`/`test_move_to.py`/`test_action_dispatcher.py` (handler-owned budget, unreachable-vs-blocked errors), `test_awareness_relation_fn_once.py` (O(N²) allocation regression guard), `test_perception.py` (second-wind zero-heal), `test_equip_desc_i18n.py`, frontend `ItemDetails.test.tsx` (8 cases incl. unequip/buy click regressions) + `equipI18n.test.tsx`. No skipped/xfail tests. WS tests cover invalid session, unknown message type, non-object JSON, turn exchange. | — |

Note: the audit-skill naming pattern `tests/unit/test_rules_<mod>.py` does not match this repo's convention (`tests/unit/test_<mod>.py`, e.g. `test_dice.py`, `test_combat.py`); coverage was verified against actual test names.

## Vision Drift

| Change | Invariant Violated | Impact |
|--------|-------------------|--------|
| none | Sprint 024 is UX polish over existing mechanics: movement budget stays inside the single global round; `props` enriches perceived payloads without leaking raw character data; LLM prompt gains `movement_remaining` while RuleBrain paths are untouched (classic mode intact); item prices/props come from YAML catalogs (content is data). | none |
