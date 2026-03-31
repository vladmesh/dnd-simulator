# Task: Perception dispatch dict + fail-fast

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 4 — Audit Refactor

## Description

Two related cleanups in `layers/entities/perception.py`:

1. **Dispatch dict.** Replace the 24-branch if/elif chain (lines 44-93) with a `dict[EventType, Callable]` lookup. Fallback for unknown event types stays the same ("Something happened ({type})").

2. **Fail-fast on event data.** Replace ~30 `.get("key", "")` / `.get("key", "?")` calls with `data["key"]` across all `_perceive_*()` handlers. If event data is missing a required field — crash with KeyError. Silent defaults mask bugs upstream.

Both changes are in the same file and should be done together.

## Tests First

Existing tests in `tests/unit/test_perception.py` cover all event types. Before refactoring:

- Add a test that an unrecognized `EventType` produces the fallback message (dispatch dict handles this via `.get()` with default).
- Add a test that an event with missing required data (e.g. `ENTITY_SAY` without `"text"`) raises `KeyError` — this validates the fail-fast behavior after refactoring.

## Implementation

1. Build `_DISPATCH: dict[EventType, Callable[[Event, Character, GetEntityFn], str]]` mapping each EventType to its handler function. Keep `ROUND_START` and `COMBAT_ENDED` inline as lambdas or small functions.
2. Replace the if/elif chain in `perceive_event()` with `handler = _DISPATCH.get(event.event_type)` → call or fallback.
3. Special case: `CUSTOM` with `inspect_target` — handle before the dispatch lookup (it's a sub-type check on data, not event_type).
4. Replace `.get("key", default)` with `["key"]` in every `_perceive_*` handler. The only exception: optional fields that genuinely may be absent (check each one — most are required).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] No if/elif chain in `perceive_event()` — dispatch dict only
- [ ] Zero `.get()` calls on `event.data` for required fields
- [ ] perception.py line count decreases

## Status

`pending`
