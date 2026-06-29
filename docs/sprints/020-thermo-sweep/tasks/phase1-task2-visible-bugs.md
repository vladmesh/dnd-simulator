# Task: Visible behavioral bugs (icon, silent travel, HTTP status)

**Date:** 2026-06-30
**Sprint:** 020-thermo-sweep
**Phase:** 1 — Корректность и инварианты

## Description

Three independent user-visible bugs from the review, each with its own test surface.

1. **[MAJOR] `lay_on_hands` log events render no icon.** `EVENT_ICONS["entity_lay_on_hands"] = "hand-heart"` (`frontend/src/lib/logProcessing.ts:68`) but `ICON_MAP` (`frontend/src/components/game/EventLog.tsx:50-78`) has no `"hand-heart"` key, so `EventIcon` returns `null`. Two hand-synced registries drifted. `hand-heart` is the only mismatch of 28.

2. **[MAJOR] `handle_wait` reports success while doing nothing.** On an unreachable or misnamed travel target, `handle_wait` (`rules/handlers/movement.py:222-258`) catches `ValueError` from `graph.travel_seconds` (`:239`), tries a name-match fallback, and on a second `ValueError` does `pass` (`:248-249`), then returns `ActionResult()` (`success=True`). The actor stays put but the turn reports success.

3. **[MAJOR] HTTP status chosen by substring-matching the exception message.** `level_up` (`adapters/api/routes_player.py:54-69`) does `"No player" in msg or "not found" in msg` to pick 404 vs 400 (`:66`). Rewording or translating the service message changes the status. No domain exception types exist; the service raises plain `ValueError` (`commands_player.py:148,168`; `game_service.py:289`). `app.py` has no exception handlers.

## Tests First (RED)

**Icon (vitest):**
- Exhaustiveness: every value in `EVENT_ICONS` resolves to a component in `ICON_MAP` (iterate `EVENT_ICONS`, assert each maps to a defined icon). Add `entity_lay_on_hands` to the `ALL_EVENT_TYPES` list in `logProcessing.test.ts` (currently absent).
- Render: a `entity_lay_on_hands` log entry renders a non-null `<svg>` (extend the EventLog render test pattern at `EventLog.test.tsx:53-65`).

**Silent travel (pytest, `tests/unit/test_handlers_movement.py`):**
- Travel to a target with no route → `ActionResult(success=False)` with a localized `error`, and the actor's `location_id` is unchanged. (Current `test_wait_travel` only covers the happy path.)
- Travel to a misnamed target (no name match) → `success=False`, location unchanged.
- Happy path (direct route, and name-match route) still succeeds and advances time — unchanged.
- Plain wait (no `travel_to`) still sets `wake_at_seconds` and goes dormant — unchanged.

**HTTP status (pytest, route/integration test):**
- `POST /sessions/{id}/level-up` with a missing player → 404.
- Same with an unknown session → 404.
- Level-up that fails validation (e.g. no pending level-up / incompatible fighting style) → 400.
- Status is wording-independent: it must not depend on the error message text.

## Implementation (GREEN)

**Icon:** import `HandHeart` from `lucide-react` in `EventLog.tsx` and add `"hand-heart": HandHeart` to `ICON_MAP`. Add a `satisfies`-style or test-enforced exhaustiveness guard so a future `EVENT_ICONS` value without an `ICON_MAP` entry fails CI (the vitest exhaustiveness test covers this; a compile-time `satisfies` is a bonus if it fits the existing types).

**Silent travel:** split travel out of `handle_wait`. Resolve the destination once (direct id, else single name-match lookup), and return `ActionResult(success=False, error=_("..."))` when no route resolves — no silent `pass`. Keep plain-wait behavior. Wrap any new error string in `_()` (consistent with the rest of `movement.py`).

**HTTP status:** introduce domain exception types — `PlayerNotFound`, `SessionNotFound`, `InvalidLevelUp` (and reuse for the obvious siblings). Make them subclass `ValueError` so existing `pytest.raises(ValueError, match=...)` tests keep passing. Raise them from the service (`commands_player.py`, `game_service._get_session`). Register app-level `@app.exception_handler`s in `app.py` mapping `*NotFound → 404`, `Invalid* → 400`. Delete the substring check in `routes_player.py`; the route just calls the service and lets the handlers map status. Keep `get_status` consistent with the same handlers.

Files: `frontend/src/components/game/EventLog.tsx`, `frontend/src/lib/logProcessing.ts` (+ tests); `rules/handlers/movement.py`; service exception module (new, e.g. `service/errors.py`), `service/commands_player.py`, `service/game_service.py`, `adapters/api/app.py`, `adapters/api/routes_player.py`.

Gotchas:
- Domain exceptions subclassing `ValueError` keeps `test_game_service_player.py:75-79` (`match="No player"`) green only if the message is preserved — preserve it.
- App-level handlers are introduced minimally here for the player routes; the broad per-route try/except sweep is Phase 2 scope. Don't refactor every route now.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] `lay_on_hands` renders an icon; vitest exhaustiveness guard covers all `EVENT_ICONS` values
- [ ] Unreachable/misnamed travel returns `success=False` with the actor unmoved; happy path and plain-wait unchanged
- [ ] Level-up HTTP status comes from exception types, not message substrings (404 missing player/session, 400 invalid)
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

All three bugs fixed.

1. **Icon**: `ICON_MAP` moved to `frontend/src/lib/iconMap.ts` (extracted from EventLog.tsx to satisfy `react-refresh/only-export-components` lint rule). Added `HandHeart` for `"hand-heart"`. Vitest exhaustiveness guard added to `EventLog.test.tsx` — iterates all `EVENT_ICONS` values and asserts each is a key in `ICON_MAP`.

2. **Silent travel**: `handle_wait` in `rules/handlers/movement.py` rewritten. The destination is resolved in a single pass (direct ID, else name-match). If no destination resolves, returns `ActionResult(success=False, error=_(...))` immediately. If a destination resolves but the route is unreachable (second `travel_seconds` call fails), also returns failure. No more silent `pass`.

3. **HTTP status**: Added `service/errors.py` with `SessionNotFoundError` and `PlayerNotFoundError` (both subclass `ValueError` to keep `pytest.raises(ValueError, match=...)` tests green). `_get_session` raises `SessionNotFoundError`; `level_up_player` and `player_status` raise `PlayerNotFoundError` when player missing. App-level `@exception_handler`s in `app.py` map both to 404. Routes re-raise domain exceptions instead of catching them with `except ValueError`.
