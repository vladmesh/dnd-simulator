# Task: Session closure dedup + awareness_builder exception narrowing

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 4 — Audit Refactor

## Description

Two related cleanups in the awareness/session pipeline:

### 1. session.py — extract shared event builder from start_round()

`start_round()` (342-456) has 4 closures. Three of them (`on_turn`, `on_action`, `on_round_end`) repeat the same pattern:
- `game_round.get_perceived_events(player)`
- `entities_layer.build_awareness(player, self.world.time, query_fn)`
- Build dict with `_awareness_to_dict()`, `_events_to_list()`, `_player_to_dict()`, `_location_data()`

Extract a `_build_state_message(type, ...)` helper method on `GameSession` that builds the common dict. Each closure calls it and adds its specific fields (error, budget, action name).

### 2. awareness_builder.py — narrow catch-all exceptions

5 `except Exception` blocks in `build_peaceful_awareness()` (lines 57-113) catch any failure from cross-layer queries and log a warning. These queries can genuinely fail (layer not loaded, region doesn't exist), so removing the try/except entirely is wrong. But `except Exception` is too broad.

Narrow to the specific exceptions that layer queries can raise. Check what `query_fn` actually raises on failure — likely `KeyError`, `ValueError`, or a custom `LayerError`. Catch only those.

## Tests First

- **Session dedup:** Add a test that `on_action` and `on_round_end` messages contain the same awareness/events/player/location structure as `on_turn`. Mock the round callbacks to capture messages and compare field sets. This validates the shared builder produces identical output.
- **Awareness exceptions:** Add a test that `build_peaceful_awareness()` raises on unexpected exceptions (e.g. `RuntimeError` from a buggy layer) instead of swallowing them. Add a test that expected query failures (missing region, etc.) are handled gracefully with defaults.

## Implementation

1. **Session:** Extract `_build_round_state(player, game_round, entities_layer) -> dict` on GameSession. Returns the common dict (mode, awareness, events, player, location). Each closure calls it and extends with type-specific fields.
2. **Awareness:** Identify the actual exception types from `query_fn`. Replace `except Exception` with `except (KeyError, SpecificError)`. Let unexpected exceptions propagate.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `start_round()` closures have no duplicated awareness-building code
- [ ] Zero `except Exception` in awareness_builder.py — all catches are specific
- [ ] start_round() line count decreases noticeably

## Status

`done`

## Developer Notes

**Session dedup:** Extracted `_build_round_state()` on `GameSession` — shared builder for `on_action` and `on_round_end` callbacks. `on_turn` could NOT be deduplicated because it receives a richer awareness object from Round (with merchants, etc.) that `entities_layer.build_awareness()` doesn't produce. The dedup still eliminates the main copy-paste between on_action and on_round_end.

**Awareness exception narrowing:** Replaced all 7 `except Exception` blocks in `awareness_builder.py` with `except (KeyError, ValueError, LayerError)`. These are the three exception types that `query_fn` (from `World._make_query_fn`) and individual layer `query()` methods can raise for expected failures (missing key, unknown query type, layer not found/direction violation). Unexpected exceptions (TypeError, AttributeError, RuntimeError) now propagate instead of being silently swallowed.

**Old test updates:** 5 existing tests in `test_awareness_builder.py` used `RuntimeError` to simulate "layer down" — updated to use `LayerError`/`KeyError` since RuntimeError is no longer caught. Also fixed `test_same_faction_not_hostile` which had an overly strict query_fn that didn't handle `FACTION_NAME` queries (previously masked by the broad `except Exception`).
