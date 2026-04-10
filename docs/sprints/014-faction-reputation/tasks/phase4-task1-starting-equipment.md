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

`pending`
