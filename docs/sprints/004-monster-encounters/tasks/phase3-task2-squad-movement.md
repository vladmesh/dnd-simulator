# Task: Squad Movement + Squad-vs-Squad Combat

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 3 — Squad Movement + Materialization

## Description

Implement tick-based squad movement in `EcologyLayer.tick()`. Each squad moves according to its `behavior`:
- **PATROL / TRADE**: follow `route` sequentially, reverse at endpoints
- **ROAM / HUNT / RAID**: pick random neighbor within `territory`
- **GUARD**: stay in place

Each squad has its own `tick_interval` controlling movement frequency. The layer tracks `_last_move_time` per squad and only moves squads whose interval has elapsed.

After movement, detect hostile squads sharing a location. Use existing `resolve_abstract_combat()` from `rules/abstract_combat.py` — model the weaker squad as encounters using its member_templates' CRs. Loser retreats to a random neighbor. Squads at strength 0 are destroyed (removed).

Emit events for movement and combat so upper layers (and eventually frontend) can report them.

## Tests First

1. **Patrol squad follows route and reverses** — squad with route [A, B, C], starts at A. After 3 ticks: A→B→C→B. Verify `current_location_id` at each step.

2. **Roam squad picks random neighbor within territory** — squad with territory [A, B, C], location graph has edges A↔B, B↔C. After tick, squad moves to a neighbor that's in its territory. Inject deterministic random.

3. **Guard squad never moves** — squad with GUARD behavior, tick 10 times → still at start location.

4. **Hostile squads in same location trigger abstract combat** — two squads from hostile factions end up at same location. After tick: combat resolves, both lose strength, loser retreats to a neighbor. Query PoliticsLayer for faction relations.

5. **Destroyed squad (strength 0) is removed** — squad with strength 1 loses combat → strength drops to 0 → squad no longer appears in queries.

6. **Squad movement respects per-squad tick_interval** — two squads, one with interval 3600, one with 7200. After 3600 seconds: first moves, second doesn't. After 7200: both have moved.

## Implementation

1. Add `_last_move_time: dict[str, int]` to EcologyLayer (squad_id → last move game-time in seconds).
2. Add `_route_direction: dict[str, int]` for patrol squads (+1 forward, -1 reverse).
3. In `tick()`:
   - For each squad, check if `elapsed >= squad.tick_interval` since last move.
   - Compute next location based on behavior (use `query_fn("geography", CONNECTIONS)` for neighbors).
   - Update `squad.current_location_id`.
   - After all moves, find locations with multiple squads → check faction relations via `query_fn("politics", FACTION_RELATION)`.
   - Hostile squads → `resolve_abstract_combat()`. Model opposing squad as `TriggeredEncounter` entries from its `member_templates` CRs (need monster_templates reference or pass CRs in squad model).
   - Loser retreats, destroyed squads removed.
4. Add `EventType.SQUAD_MOVE` and `EventType.SQUAD_COMBAT` to `core/models.py`.
5. Emit events via `emit_fn()`.
6. Serialize `_last_move_time` and `_route_direction` in `get_state()` / `load_state()`.

**Open question:** EcologyLayer needs MonsterTemplate CRs to model squad-vs-squad combat. Options:
- (a) Store `member_crs: list[float]` on Squad (derived from templates at load time) — simpler, no cross-layer query needed.
- (b) Pass monster_templates dict to EcologyLayer — it's static data, not a layer violation.

Option (a) is cleaner. Add `member_crs` field to Squad, populate in content_loader alongside `member_templates`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Patrol squads follow routes and reverse at endpoints
- [ ] Roam squads stay within territory
- [ ] Guard squads don't move
- [ ] Hostile squads fight when colocated, loser retreats
- [ ] Destroyed squads are removed
- [ ] Movement and combat events emitted

## Status

`done`

## Developer Notes

Added `member_crs: list[float]` field to Squad (default empty list, populated in GameService from MonsterTemplate CRs at load time). Added `location_graph` param to EcologyLayer for neighbor lookups during movement. Movement logic: PATROL/TRADE follow route with reversal, ROAM/HUNT/RAID pick random neighbor in territory, GUARD stays put. Per-squad tick_interval controls movement frequency. Squad-vs-squad combat reuses `resolve_abstract_combat()` — both squads fight simultaneously, loser retreats, destroyed squads removed. Added EventType.SQUAD_MOVE and SQUAD_COMBAT. Serialization extended for route_index, route_direction, last_move_time.
