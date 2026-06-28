# Task: commands_save round-trip tests + get_world_state fail-fast hardening

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 1 — Session lifecycle test net

## Description

Two small, related control-plane gaps:

1. **`commands_save` coverage.** `load_game` (the meaty one — brain reassignment +
   old/new save-format branch), `list_saves`, and `delete_save` have no dedicated unit
   tests (`load_game` / `list_saves` / `delete_save` → 0 unit refs; `save_game` only via
   integration `test_save_roundtrip.py`). `autosave_all_sessions` is already covered
   (`test_autosave_all.py`) — don't duplicate it.

2. **`get_world_state` fail-fast.** `commands_world_state.py` guards malformed layer
   answers with four `assert isinstance(...)`. Asserts are stripped under `python -O`
   and surface as opaque `AssertionError` / HTTP 500. Replace them with explicit
   fail-fast that raises a descriptive error naming the layer + query. Behaviour change
   is small and local, so this part is genuine TDD (write the red test first).

## Tests First

### commands_save (`tests/unit/test_commands_save.py`)
Use a **real** `JsonFileStore(tmp_path / "saves")` (like `test_game_service_player.py`),
not a mock — a genuine disk round-trip is the point.

- Round-trip: `start_game` → mutate observable state (e.g. `advance_time` a few hours
  so `world.time` moves) → `save_game(sid, "snap")` → mutate again → `load_game(sid, "snap")`
  → assert state restored to the saved snapshot (time matches the save, not the later
  mutation).
- Brain reassignment on load: after `load_game`, NPC brains match their restored
  `ai_type` (a `rule_based` NPC has a `RuleBrain`). Assert via the entities layer, not
  internals.
- `list_saves` returns the names saved for that session's world; `delete_save` removes
  one so a subsequent `list_saves` no longer contains it.

### get_world_state hardening (`tests/unit/test_commands_world_state.py`, extend)
- Start a real session, then monkeypatch `session.world.query_layer` (or the specific
  geography/politics query) to return an `Answer` whose `value` is the wrong type
  (e.g. a string where a list is expected). Assert `get_world_state` raises a clear,
  typed error (`ValueError`/`RuntimeError`) whose message names the offending
  layer/query — **not** a bare `AssertionError`.

## Implementation

- `commands_world_state.py`: replace each `assert isinstance(x, T)` with an explicit
  `if not isinstance(x, T): raise <Error>(f"...{layer}/{query}...")`. Keep the happy
  path identical (existing `test_commands_world_state` tests stay green).
- Save tests are test-only.

## Acceptance Criteria

- [ ] `test_commands_save.py`: load_game round-trip (state restored + brains reassigned), list_saves, delete_save
- [ ] get_world_state raises a descriptive typed error on malformed layer data (red → green after assert→raise swap)
- [ ] Existing `test_commands_world_state.py` happy-path tests still green
- [ ] No duplication of `test_autosave_all.py`
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

- `tests/unit/test_commands_save.py` (5 tests, real `JsonFileStore(tmp_path)`): load_game
  round-trip (advance_time 5h → save → advance 3h → load → `world.time` restored to the
  snapshot, not the later mutation), brain reassignment (null an NPC's brain, load,
  assert the restored NPC has a `RuleBrain`), list_saves, delete_save. `world.load`
  restores `world.time` in place on the existing layer objects, so re-fetching the NPC by
  id from the same `EntitiesLayer` after load is sound.
- `commands_world_state.py`: replaced the 6 `assert isinstance(...)` guards with a single
  `_expect[T](value, expected, *, layer, query)` helper (3.12 type-param syntax, ruff
  UP047) that raises `RuntimeError` naming layer + `QueryType.name`. Happy path unchanged
  (existing world-state tests stay green); chose `RuntimeError` (layer invariant breach,
  not a caller arg error). `region_ids` narrowed once and reused for the settlements loop.
- One red→green: the hardening test (`test_malformed_layer_answer_raises_typed_error`)
  monkeypatches `world.query_layer` to return `Answer(value="not-a-list")` for the
  geography REGIONS query; was `AssertionError` before the swap, now `RuntimeError`.
- No integration touched. `make check` green (backend 2268, frontend 238).
