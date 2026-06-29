# Task: Backend lens-scoping primitives

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 2 — Three-lens projection of `/api/master/*`

## Description

The three lenses (worldbuilder / DM / admin) differ by **scope of visibility**, not by access enforcement (per the sprint's "creator = attribution, not access" and "role not enforced yet" decisions). This task adds the two backend scoping primitives the lenses need. Both are additive and unenforced — anyone may still request the full god-mode view.

1. **Worlds scoped by creator.** `list_worlds` gains an optional `creator` filter; `GET /api/master/worlds` gains a `creator` query param. When set, the result includes only worlds whose `creator` matches the value (so the worldbuilder lens can request just its own). Base/system worlds (`creator: system`) are excluded from a personal-creator filter but returned when `creator=system` or no filter is given. Unfiltered behavior is unchanged.

2. **Session list enriched with attribution + clock.** `list_sessions` adds `created_by` and `time` to each entry. For in-memory sessions: `created_by` from `session.created_by`, `time` from the formatted in-game clock. For saved-but-not-loaded sessions: `created_by` from save meta when cheaply available, else `""`; `time` `""`. The DM lens filters sessions to its own `created_by`; the admin park-view shows attribution + clock across all sessions.

No write route changes, no 403s — projection only.

## Tests First

Product-level, exercising the real service against a temp content/store root:

- **Worlds creator filter.** Create one world as creator `"alice"`, one as `"bob"` (via `create_empty_world` / `assemble_world` with `creator=`). `list_worlds(creator="alice")` returns exactly alice's world(s) and excludes bob's world and the base/system worlds. `list_worlds()` (no filter) still returns all of them including base worlds. Mirror at the REST layer: `GET /api/master/worlds?creator=alice` returns only alice's worlds (assert ids).
- **Session attribution + clock.** Start a session with `created_by="dm_dana"`. The `list_sessions()` entry for that session id has `created_by == "dm_dana"` and a non-empty `time` string. A header-driven path is already covered by `test_identity_seam`; here assert the *listing* surfaces the stamp.
- **Backward-compat.** A session started with no `created_by` lists `created_by == ""` and still appears (no crash, no filtering-out).

## Implementation

- `service/commands_worldbuilder.py::list_worlds` — add `creator: str | None = None`; filter the returned dicts on their `creator` key. Keep base-world exclusion logic consistent with how `base_worlds` is used in the route.
- `adapters/api/routes_world.py::list_worlds` — add `creator: str | None = None` query param, thread it into `service.list_worlds(...)`. `WorldListItem` already carries `creator`; no schema change.
- `service/game_service.py::list_sessions` — add `"created_by"` and `"time"` keys to each dict. Add a small private clock-formatter (or reuse the same `GameDateTime` fields as `routes_session._format_time`) so the adapter stays thin. For saved sessions, read `created_by` from meta if the store exposes it cheaply, else default to `""`.
- `adapters/api/schemas.py` / route: `/sessions` returns `list[dict[str, str]]` with no response_model, so the new keys pass through. Add `created_by: string` to the frontend `SessionListItem` type in task 2 (consumed there).

Gotchas: keep the `creator` filter purely a query helper — do not reject or 403 on mismatch. Don't break the existing `list_worlds(lang=...)` callers (param is keyword-optional).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `list_worlds(creator=...)` filters by creator; unfiltered call unchanged
- [ ] `GET /api/master/worlds?creator=alice` returns only alice's worlds
- [ ] `list_sessions()` entries include `created_by` and `time`; no enforcement added

## Status

`pending`
