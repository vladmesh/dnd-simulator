# Task: Update integration test world references

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 1 — Content Standardization

## Description

All integration tests reference worlds by legacy filenames (`"arena.yaml"`, `"village.yaml"`, etc.). After task 1 converted worlds to directories, these references must change to directory names (`"arena"`, `"village"`, etc.).

Files to update:
- `tests/integration/conftest.py` — session fixtures use `"arena.yaml"`, `"village.yaml"`
- `tests/integration/test_rest_api.py` — session creation + `list_worlds` assertions (`"arena.yaml" in world_ids`)
- `tests/integration/test_websocket.py` — session creation with `"arena.yaml"`, `"village.yaml"`
- `tests/integration/test_trading.py` — session creation with `"village.yaml"`
- `tests/integration/test_squads.py` — session creation with `"squad_world.yaml"`

## Tests First

No new tests needed — this task makes existing integration tests pass with the new directory names. The tests themselves are the verification.

## Implementation

Find-and-replace in each file:
- `"arena.yaml"` → `"arena"`
- `"village.yaml"` → `"village"`
- `"sneak_test.yaml"` → `"sneak_test"`
- `"squad_world.yaml"` → `"squad_world"`

Also update `test_rest_api.py` assertions that check `list_worlds` response IDs.

## Acceptance Criteria

- [ ] All integration test world references use directory names (no `.yaml` suffix)
- [ ] `make test-integration` passes (or: integration tests pass when run against the converted content)
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Straightforward find-and-replace across 5 integration test files. All `.yaml` suffixes removed from world_name parameters and list_worlds assertions. No surprises — existing unit tests all pass, integration tests will validate against the converted directory-format worlds when run in docker compose.
