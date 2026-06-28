# Task: Time-of-day encounters

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 4 — Время суток (Time-of-Day Spawns)

## Description

Encounter-table entries can be tagged with a time of day. A night-tagged entry rolls
only at night, a day-tagged entry only during the day, an untagged entry always (current
behaviour). Day/night is read from the geography layer, which already owns the solar model
(`rules/geography.is_daylight`).

The roll lives in `ActivationManager._roll_encounters` (entities layer), not ecology — the
phase text says "хук в ecology" but the encounter roll has always been in entities.
Entities sits above geography in the stack, so querying geography for day/night is a legal
downward query; no refactor needed.

Scope is **encounters only** — lair rosters stay always-active when the lair is `ACTIVE`.
Lair-by-time-of-day is deferred (`lair-time-of-day`, sprint Deferred section). Gating is a
hard on/off by tag (the simpler of the two the phase offers: "только ночью либо с
повышенной частотой"); a frequency multiplier is out of scope.

Concrete changes:

1. `TimeOfDay(StrEnum)` with `DAY = "day"`, `NIGHT = "night"` in `core/models.py`.
2. `QueryType.IS_DAYLIGHT` in `core/models.py`; handler in `GeographyLayer.query` that
   resolves `location_id → region → latitude` (via the layer's `location_graph` / `_regions`)
   and returns `is_daylight(latitude, month, hour)`. Params: `{location_id, month, hour}`.
   Degrade to `True` (daytime, no gating) when there is no graph / region (so worlds without
   geography are unaffected).
3. `EncounterEntry.time_of_day: TimeOfDay | None = None` (`core/monster.py`).
4. `EncounterEntryContent.time_of_day: TimeOfDay | None = None` (`content_loader/schemas.py`)
   — Pydantic validates the enum, so a typo'd value fails fast at load. `_to_encounter_entry`
   (`content_loader/monsters.py`) carries the field through. JSON Schema for the frontend
   picks it up automatically (generated from the Pydantic model).
5. Pure rule `rules/encounters.py`: `is_active_at_time(time_of_day: TimeOfDay | None, is_day: bool) -> bool`
   — `True` when untagged, else tag matches the current phase.
6. `ActivationManager`: thread `time: GameDateTime` from `update_activation` into
   `_check_encounters` and `_roll_encounters`. Compute `is_day` once per rolled location via a
   small `_is_daylight_at(location_id, time, query_fn)` helper (default `True` when `query_fn`
   is `None` or geography is absent — keeps existing no-geography unit tests green). Filter each
   entry through `is_active_at_time` before the chance roll.

## Tests First

Product-level scenarios (game behaviour, not field presence). The deterministic harness from
`tests/unit/test_region_encounters.py` already mocks `random.random → 0.0` (always clears the
chance gate) and `random.randint → 1` (count fixed at 1); reuse it and vary `session.world.time`
to switch day/night. Test world `test_vale` starts at month 6, hour 10 (day); all its regions
are latitude 45 (daylight ≈ 04:18–19:42), so hour 10/12 = day, hour 0/2/22 = night.

Unit (`tests/unit/test_time_of_day_encounters.py`, in-process via `GameService` + real layers):

1. **A night-only encounter does not spawn during the day.** Player enters a location whose
   table is night-tagged, world at the default day hour → activate → no monster spawns there.
2. **The same night-only encounter spawns once it is night.** Advance `world.time` into the
   night (e.g. to hour 2), player at that location → activate → the night monster spawns.
3. **An untagged encounter still spawns regardless of time.** At night, a location with an
   untagged table (e.g. the existing `crossroads` regional goblin table) still spawns its
   monster — proves the filter only drops mismatched tags, never untagged ones.

Integration (`tests/integration/test_encounters.py`, live backend on `encounter_world`):

4. **A night-only table stays empty during the day.** Create a factionless character at the
   night-tagged location, connect at the default (day) start time, read the first turn → no
   spawn at that location.
5. **A night-only table fires after time is advanced into night.** Same location; before
   connecting, `POST /sessions/{id}/advance_time` enough hours to reach a night hour, then
   connect and read the first turn → the night monster is present. (`advance_time` ticks layers
   but does not roll encounters; the round loop on connect runs activation at the now-night
   time.)

## Implementation

After the tests are red:

- `core/models.py` — add `TimeOfDay(StrEnum)` and `QueryType.IS_DAYLIGHT`.
- `layers/geography/layer.py` — handle `IS_DAYLIGHT` (import `is_daylight` from
  `rules.geography`; resolve region via `self._location_graph.region_of` then `self._regions`).
- `core/monster.py`, `content_loader/schemas.py`, `content_loader/monsters.py` — add and thread
  the `time_of_day` field.
- `rules/encounters.py` (new) — `is_active_at_time`.
- `layers/entities/activation_manager.py` — thread `time`, add `_is_daylight_at`, filter in
  `_roll_encounters`.
- Content (additive, do not disturb existing assertions):
  - `tests/integration/content/worlds/encounter_world/` — add a location (region latitude 45,
    e.g. in `borderlands` so no regional table interferes) with its own night-tagged table
    (`time_of_day: night`, `chance: 1.0`, `count: [1, 1]`); add it to `geography/locations.yaml`.
  - `content/worlds/test_vale/` — add a location with a night-tagged own table for the unit
    tests, kept separate from `crossroads` / `forest_road` / `forest_edge` so their existing
    assertions hold.

Gotchas:
- Untagged entries must keep firing day and night — every existing encounter test/world is
  untagged and must stay green.
- `_check_encounters` currently receives `now: int`; switch it to receive `time` and derive
  `now = time.to_total_seconds()` (it still needs `now` for the cooldown).
- Default `is_day = True` whenever day/night can't be determined (no `query_fn`, no geography,
  unresolved location), so the feature never spuriously suppresses untagged spawns.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Night-tagged encounters roll only at night; day-tagged only by day; untagged always
- [ ] Day/night is sourced from geography (`IS_DAYLIGHT` query), not recomputed in entities
- [ ] Bad `time_of_day` values in content fail fast at load (Pydantic enum validation)

## Status

`pending`
