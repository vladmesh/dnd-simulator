# Task: Squad Materialization + Dematerialization

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 3 — Squad Movement + Materialization

## Description

When a squad and an active character occupy the same location, the squad "materializes" — its `member_templates` spawn as concrete `Creature` instances with `squad_id` set, managed by `EntitiesLayer`. When the active character leaves (or goes dormant), materialized creatures are removed and the squad's strength is updated based on survivors.

**Materialization flow:**
1. `EntitiesLayer.update_activation()` queries `EcologyLayer` for squads at active character locations.
2. For each squad not already materialized: spawn creatures from `MonsterTemplate.spawn()`, set `squad_id`, `faction_id`, `temporary=True`, assign `RuleBrain`.
3. Track which squads are currently materialized (to avoid double-spawning).

**Dematerialization flow:**
1. When no active character remains at a materialized squad's location (checked during `update_activation()`).
2. Remove all creatures with that `squad_id`.
3. Update squad strength: `new_strength = (alive_count / spawned_count) * original_strength` (proportional to survivors).
4. Emit event to EcologyLayer to update the squad's strength.

## Tests First

1. **Squad materializes when active character arrives** — player at location A, squad at location A. After `update_activation()`: creatures spawned with correct `squad_id`, `faction_id`, `temporary=True`, and `RuleBrain`. Number of creatures matches `member_templates` length (scaled by strength ratio if needed).

2. **Already materialized squad doesn't double-spawn** — player at location A with materialized squad. Run `update_activation()` again → no new creatures spawned.

3. **Squad dematerializes when active character leaves** — player moves from A to B, squad stays at A. After `update_activation()`: all creatures with that `squad_id` removed. Squad strength updated proportionally to survivors.

4. **Dematerialization after combat updates squad strength** — squad materializes with 3 creatures (strength 6). Player kills 1 creature, then leaves. Dematerialization: 2/3 survived → squad strength = 4.

5. **Squad in combat doesn't dematerialize** — materialized squad creatures are in_combat. Player leaves location. Creatures stay until combat ends, then dematerialize on next activation check.

6. **Multiple squads at same location materialize independently** — two friendly squads at player's location. Both materialize with correct squad_ids. Player leaves → both dematerialize.

## Implementation

1. Add `_materialized_squads: dict[str, MaterializedSquad]` to `EntitiesLayer` — tracks `squad_id → {creature_ids: list[str], original_strength: int, spawn_count: int}`.
2. In `update_activation()`, after computing active locations:
   - Query `EcologyLayer` via `query_fn("ecology", SQUADS_AT_LOCATION)` for each active location.
   - For new squads: materialize (spawn creatures, add to `_materialized_squads`).
   - For squads no longer at active locations AND not in combat: dematerialize (remove creatures, compute new strength, emit event).
3. Add `EventType.SQUAD_MATERIALIZED` and `EventType.SQUAD_DEMATERIALIZED` to `core/models.py`.
4. Dematerialization emits event with `{squad_id, new_strength}` — EcologyLayer handles this in `handle_event()` to update squad strength.
5. Serialize `_materialized_squads` in `get_state()` / `load_state()`.

**Creature count scaling:** If `len(member_templates) = 3` and `strength = 6, max_strength = 6`, spawn all 3. If strength is reduced (e.g. 4), scale: `count = max(1, round(len(templates) * strength / max_strength))`. Pick first N templates.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Squads materialize into creatures at active character locations
- [ ] No double-spawning of already materialized squads
- [ ] Squads dematerialize when active character leaves
- [ ] Squad strength updated proportionally on dematerialization
- [ ] Creatures in combat prevent dematerialization
- [ ] Materialization state survives save/load

## Status

`pending`
