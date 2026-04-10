# Task: Auto-Hostility Combat Initiation

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 3 — Reputation Dynamics + Auto-hostility

## Description

When a creature attacks an NPC outside of combat, combat should start with correct sides: attacker + attacker's allies vs target + target's allies. Currently `resolve_attack` calls `start_combat(location_id, query_fn)` which gathers all creatures at the location and builds sides from their relations. This mostly works, but the auto-hostility scenario has a nuance: the attack itself changes the relationship (attacker is now hostile to target), so sides must reflect that.

The key change: when an attack triggers combat (no existing combat at location), explicitly build the two opposing groups using `effective_relation` from each creature's perspective, ensuring the attacker and target end up on opposing sides even if their faction relations would otherwise make them neutral/friendly.

## Tests First

Scenarios in a new `tests/unit/test_auto_hostility.py`:

1. **Attack peaceful NPC starts combat.** Player (kingdom) attacks a neutral merchant (guild). Combat starts. Player and merchant are on opposing sides.
2. **Allies join correct sides.** Location has: player (kingdom), 2 kingdom guards, merchant (guild), guild bodyguard. Player attacks merchant. Combat: [player, guards] vs [merchant, bodyguard].
3. **Bystanders from unrelated faction stay neutral or pick a side.** A third-faction creature at the location — if friendly to target, joins target's side; if neutral to both, gets its own side.
4. **Already in combat — no side rebuild.** If combat already exists at location, `resolve_attack` doesn't re-trigger combat initiation.
5. **Factionless attacker vs factionless target.** Both get their own sides. Allies (if any) group by effective_relation.
6. **Attack between current allies triggers side split.** Two creatures on the same faction — one attacks the other. They must end up on opposing sides despite being same-faction.

## Implementation

1. In `CombatManager.resolve_attack`, when `attacker.location_id not in self._combats`, before calling `start_combat`:
   - Build a "forced hostility" override: attacker and target are on opposing sides regardless of faction.
   - Pass this to `start_combat` (or to `build_combat_sides`) as a constraint.
2. Extend `build_combat_sides` in `rules/combat_sides.py` to accept an optional `forced_opponents: set[tuple[str, str]]` parameter — pairs of entity IDs that must be on different sides.
3. The greedy algorithm already groups by mutual FRIENDLY. The forced_opponents constraint prevents merging sides that contain forced opponents.
4. Ensure `start_combat` always has `query_fn` available when auto-hostility triggers — it's already passed through `resolve_attack`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Attacking a non-hostile NPC outside combat starts combat with correct sides
- [ ] Allies of attacker and target join the correct sides via effective_relation
- [ ] Attacker and target are always on opposing sides even if same faction
- [ ] No behavior change for attacks within existing combat

## Status

`pending`
