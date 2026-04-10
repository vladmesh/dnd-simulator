# Task: Starting Equipment as Real Items

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 4 — Bug Fixes

## Description

Player character is created with correct AC (chain mail + shield applied as stats) but fights with "fists" in combat. The E2E shows "Weapon: fists (1)" in the combat panel and attack logs show "кулаки" instead of longsword.

The `create_player` flow in `game_service.py:810-842` loads the item catalog, builds `items_data` with `{"ref": ref, "equipped": True}` dicts, passes to `parse_player` which resolves refs and populates `equipped_weapon`, `equipped_armor`, `equipped_shield`. Direct Python testing confirms the objects are created correctly.

However, in E2E the combat awareness shows "fists". The gap is somewhere between player creation and the first combat turn's `get_weapon_attack(creature)` call. Possible causes:
- Save/load cycle strips equipment (save serialization → load doesn't restore Item objects)
- Session setup path resets equipment fields
- WS turn message built before equipment is fully wired

## Tests First

1. **Integration test: created player has weapon in combat** — Create a session, create a fighter, connect WS, start combat (attack an NPC). The first attack event in WS messages should contain the weapon name (e.g. "longsword slash"), NOT "fists" or "кулаки". The combat awareness `self_weapon` field should show the weapon name.

2. **Unit test: round-trip save/load preserves equipment** — Create a PlayerCharacter with equipped longsword via `parse_player`. Save state via `get_state()`, load via `load_state()`. Verify `equipped_weapon` is still a valid Item with weapon_def.

## Implementation

1. Reproduce the bug: add a targeted integration test that checks `self_weapon` in the WS combat turn message.
2. Trace the actual value: add debug logging in `get_weapon_attack()` to see what `creature.equipped_weapon` is at attack time.
3. Fix the root cause once identified — likely in save/load serialization or session initialization.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] E2E: combat shows actual weapon name, not "fists"
- [ ] Attack rolls use weapon damage dice (1d8 for longsword), not unarmed (1)

## Status

`done`

## Developer Notes

Root cause: two bugs in the save/load cycle that together strip ALL equipment from players.

**Bug 1 — `to_full_save_data()` (player.py):** Equipped items were serialized into
top-level keys (`equipped_weapon`, `equipped_armor`, etc.) but NOT included in the
`items` list. When `parse_player()` restored from save data, it only read `items`
(which contained only inventory), so all equipment slots came back as None.

**Bug 2 — `load_state()` (entities/layer.py):** The player branch used `continue`
after `parse_player`, skipping the equipment restoration loop at lines 550-553.
NPCs didn't have this bug — they fell through to the restoration code. Changed
player path to match the NPC pattern: set `entity = parse_player(edata)` and
fall through.

**Fix:** `to_full_save_data` now builds a unified `items` list containing both
inventory AND equipped items (with `equipped: True`). The `load_state` player
branch now falls through to restore equipment from top-level keys as well (belt
and suspenders).

AC was correct because `create_player` computes `effective_ac()` at creation and
stores it as a static `ac` field. The weapon loss only surfaced when `get_weapon_attack()`
checked `creature.equipped_weapon` at combat time — by which point a save/load
cycle had cleared it.
