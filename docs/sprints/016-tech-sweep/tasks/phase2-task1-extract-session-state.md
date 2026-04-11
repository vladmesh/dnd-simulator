# Task: Extract get_session_state() to GameService

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 2 — Adapter & Routes

## Description

`routes_master.py:290–334` contains `get_session_state()` — the only thick route in the adapter layer. It directly queries 4 world layers (geography, politics, settlements, entities), loops over regions/nations, and assembles a composite WorldStateResponse. This business logic belongs in GameService, not in the adapter.

Move the aggregation logic into a new `GameService.get_world_state(session_id)` method. The route handler becomes a one-liner delegating to the service. Follow the existing mixin pattern — create `commands_world_state.py` with a `WorldStateCommands` mixin, add it to `GameService`.

The method should return a dict (or typed structure) that the route maps to `WorldStateResponse`. The adapter stays thin — just schema conversion.

## Tests First

1. **Unit test: GameService.get_world_state returns all layer data** — create a session with a known world (arena), call `service.get_world_state(session_id)`, verify the result contains regions with weather, nations, settlements, and entities. This exercises the full query chain through World → layers.

2. **Unit test: get_world_state raises on unknown session** — call with a bogus session_id, expect a clear error (not a 500 from a missing attribute).

3. **Integration test: GET /sessions/{id} still returns correct WorldStateResponse** — the existing `test_get_world_state` in `test_rest_api.py` already covers this. Verify it still passes after the refactor (no new test needed, just don't break it).

## Implementation

1. Create `src/dnd_simulator/service/commands_world_state.py` with `WorldStateCommands` mixin containing `get_world_state(session_id) → dict[str, object]`.
2. Move the layer-query logic from `routes_master.py:297–325` into this method.
3. Add `WorldStateCommands` to `GameService`'s bases in `game_service.py`.
4. Reduce `get_session_state()` route to: call `service.get_world_state(session_id)`, wrap in `WorldStateResponse`.
5. Remove now-unused imports from `routes_master.py` (`Query`, `QueryType`).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `get_session_state()` route body is ≤ 5 lines (pure delegation + response construction)
- [ ] No `Query`/`QueryType` imports remain in `routes_master.py`
- [ ] `WorldStateCommands` mixin follows existing pattern (like `CreatureCommands`)

## Status

`done`

## Developer Notes

Straightforward extraction. The `get_world_state()` method moved into `WorldStateCommands` mixin following the existing pattern (CreatureCommands, etc.). Route body is now 4 lines: validate session exists (for 404), call service, return model. Time formatting moved into the service method since it's part of the state payload. The route still calls `_get_session()` first to preserve the ValueError→404 conversion at the adapter boundary.
