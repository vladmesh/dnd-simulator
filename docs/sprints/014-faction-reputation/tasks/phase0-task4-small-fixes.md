# Task: Small Fixes — Perception, Proficiency, Commands Tests

**Date:** 2026-04-09
**Sprint:** 014-faction-reputation
**Phase:** 0 — Refactor — Prep for Faction Work

## Description

Bundle of three small refactors that don't warrant separate tasks:

### A. Perception fail-fast (8 `.get()` sites)

`layers/entities/perception.py` uses `.get()` with silent defaults for event data fields that should always be present (weapon, critical, is_opportunity_attack, etc.). Replace with `data["key"]` — if an event is malformed, crash immediately instead of rendering garbage.

### B. Proficiency hardcoded weapon strings

`rules/proficiency.py:33-34` has `frozenset({"rapier", "shortsword", ...})` — raw strings that must match YAML catalog weapon IDs. Extract into a constant or verify against catalog at import/test time. At minimum, add a test that asserts every weapon ID in the proficiency map exists in the item catalog.

### C. Commands politics unit tests

`service/commands_politics.py` (35 lines) has zero test coverage. Add unit tests for `patch_nation` and `patch_settlement` — mock the session/layers, verify correct fields are updated.

## Tests First

- **Perception:** test that formatting an attack event WITHOUT the `weapon` key raises KeyError (not returns empty string).
- **Proficiency:** test that every weapon ID in `_CLASS_SPECIFIC_WEAPONS` exists in the SRD item catalog.
- **Commands:** test `patch_nation(nation_id, {"wealth": 100})` updates the nation's wealth. Test `patch_settlement(settlement_id, {"population": 500})` updates population.

## Implementation

1. Perception: replace 8 `.get(key, default)` calls with `data["key"]`. Remove now-unnecessary defaults.
2. Proficiency: add catalog validation test. If weapon IDs are inconsistent with catalog, fix them.
3. Commands: write `tests/unit/test_commands_politics.py` with mocked game session.
4. Verify `make check` green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Zero `.get()` silent defaults in perception for required event fields
- [ ] Proficiency weapon IDs validated against catalog
- [ ] commands_politics has unit test coverage

## Status

`done`

## Developer Notes

- **Perception:** Changed `weapon` and `critical` from `.get()` with silent defaults to `d["key"]` fail-fast. Both are always present in `build_attack_event`. `is_opportunity_attack` kept as `.get()` — genuinely optional (only on OA events). `description` kept as `.get()` — genuinely optional flavor text. Net: 2 of the original `.get()` calls were hiding real contract requirements.
- **Proficiency:** All weapon IDs in `_CLASS_SPECIFIC_WEAPONS` (rapier, shortsword, longsword, hand_crossbow) already match catalog YAML files. Added validation test to catch future drift.
- **Commands politics:** Added 4 tests covering `patch_nation` (single + multi-field) and `patch_settlement` (single + multi-field) using real `GameService` with sword_vale world.
