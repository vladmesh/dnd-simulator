# Task: Integration Tests — Squad Materialization

**Date:** 2026-04-02
**Sprint:** 013-char-creation
**Phase:** 3 — Content Fixes + Polish

## Description

Add integration tests that verify squad materialization produces creatures with correct stats and faction. Currently integration tests only check that squads load and time advances — nothing verifies that materialized creatures match their monster template.

Also update the `squad_world` test fixture to use guard template (matching the library content fix).

## Tests First

Integration tests in `tests/integration/test_squads.py`:

1. **Patrol materializes guards at player location** — create session, place player at patrol route location, advance time until activation triggers. Query entities at location — verify spawned creatures are guards (name="Guard"), not bandits.
2. **Materialized guard has correct stats** — from the spawned guard creature, verify hp=11, ac=16, faction matches squad faction ("kingdom").
3. **Squad strength scaling** — if squad strength < max_strength, fewer creatures spawn (existing behavior, but untested). Damage the squad via time advancement with encounters, verify reduced creature count.

If the entities endpoint doesn't expose enough detail for stat verification, use the creature detail endpoint or world state endpoint.

## Implementation

1. Update `tests/integration/content/worlds/squad_world/ecology/squads.yaml` — change `test_patrol` members from `[bandit, bandit]` to `[guard, guard]`.
2. Add guard to the squad_world's monster catalog references (ensure guard.yaml is discoverable).
3. Write `TestSquadMaterialization` class with the scenarios above.
4. Verify all existing squad tests still pass.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing integration tests still pass (`make test-integration`)
- [ ] Materialized creatures verified to have correct name, hp, ac, faction

## Status

`pending`
