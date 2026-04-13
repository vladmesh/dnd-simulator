# Task: leveling unit tests

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## Description

`rules/leveling.py` (XP-by-CR + level thresholds + `xp_to_next_level` + `can_level_up`) currently has only integration coverage via the kill→XP path. Audit flagged it as a test gap. Add an isolated unit test file.

## Tests First

Create `tests/unit/test_rules_leveling.py`. Cover:

- **xp_for_cr** — table values match DMG p.275 (CR 1/8 → 25, CR 1 → 200, CR 5 → 1800, CR 10 → 5900). Unknown CR (e.g. 11.0) raises `ValueError`.
- **level_for_xp** — boundaries: 0 XP → level 1; 299 → level 1; 300 → level 2; 899 → level 2; 900 → level 3; XP at MAX_LEVEL threshold (355000) → level 20; XP above (1_000_000) → still level 20.
- **xp_to_next_level** — fresh char at 0 XP needs 300; at 100 XP needs 200; at exactly threshold (300) needs 600 (next is 900); at MAX_LEVEL returns 0.
- **can_level_up** — at L1 with 299 XP → False; at L1 with 300 XP → True; at L20 with any XP → False; at L2 with 300 XP → False (already that level).

These are formula tests — small, fast, explicit values pinned to the PHB tables.

## Implementation

Pure test file, no production code changes.

## Acceptance Criteria

- [ ] Tests written and pass against current `rules/leveling.py`
- [ ] Coverage spans XP-by-CR, level_for_xp boundaries, xp_to_next_level, can_level_up
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Added `tests/unit/test_rules_leveling.py` with 20 tests covering xp_for_cr table values + unknown-CR error, level_for_xp boundaries (0/299/300/899/900/max/above), xp_to_next_level (0/100/300/max), can_level_up (below/at/max/already-caught-up). One ruff lint fix: raw string for the CR error regex. Full `make check` green (2158 py + 238 fe).
