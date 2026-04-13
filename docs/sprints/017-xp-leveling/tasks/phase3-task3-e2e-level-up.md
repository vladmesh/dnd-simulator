# Task: E2E — dedicated level-up world + full cycle

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 3 — Level-up UI + E2E

## Description

Build a dedicated test world under `content/worlds/level_up_test/` (or similar slug) that deterministically exercises the full level-up loop, then run a Playwright E2E against it.

### World design

- **Player:** Paladin L1, placed adjacent to the test monster. Starting equipment: one-handed weapon (so Dueling fighting style is observable) + shield, not two-handed.
- **Monster:** bespoke creature with `xp_reward` (or CR) set so that **one kill** lifts the player from level 1 straight over the L2 threshold (300 XP). Intentional overshoot is fine — the point is to land on L2 in a single hit without multi-fight setup. Keep HP low so the fight is 1-2 rounds. Faction: hostile.
- **Second monster:** another hostile adjacent after the first is dead, used for the *post-level-up* sanity fight. This one must survive long enough for the player to demonstrate new mechanics:
  - Spell slot pool visible and spendable (Divine Smite on a hit).
  - Dueling +2 damage present in the attack breakdown.
  - HP bump from level-up visible on the character panel.
- Tiny map (3×3 or so), everything in one location to avoid movement/activation distractions.

### E2E scenario (Playwright)

1. Start session, select the `level_up_test` world, create Paladin with a simple stat array (point buy helper if needed).
2. Attack the first monster until it dies. Confirm XP goes from 0 → ≥ 300, `level_up_available` becomes true.
3. Level-up modal auto-opens. Verify:
   - Title shows "Level 2".
   - Fighting-style dropdown is present with three options.
   - Confirm is disabled until an option is picked.
4. Pick **Dueling**, confirm.
5. Assert post-level-up state in `PlayerStats` and action bar:
   - Level = 2, HP max increased.
   - Spell slot resource pool visible with at least 1 slot.
   - Divine Smite is now an available action.
6. **Second fight:** attack the second monster. On a hit:
   - Attack breakdown shows +2 damage from Dueling fighting style.
   - Use Divine Smite once — slot decrements, damage log reflects smite dice.
7. End fight. Scenario passes only if all assertions above hold.

### Secondary: Fighter Action Surge check

Optional companion scenario (same world can host a Fighter-variant manifest or add a toggle): Fighter L1 kills the first monster → modal opens with no dropdown → confirm → `action_surge` action appears in the bar and is usable. Only add if the primary scenario is green and there's time.

## Tests First

No unit tests. Pre-flight checks before writing the Playwright script:

- World loads via content_loader without validation errors (run `uv run python -c "from dnd_simulator.content_loader.world_assembly import load_world; load_world('level_up_test')"` or similar sanity).
- XP award from the test monster lands on L2 (quick integration test in `tests/integration/` or manual Swagger hit is fine — document which).

Only after both are confirmed, write the Playwright scenario.

## Implementation

- New: `content/worlds/level_up_test/manifest.yaml` + layer files (copy structure from `content/worlds/test_vale/`). Keep it minimal — one region, one settlement, one location.
- New: `content/worlds/level_up_test/entities/monsters.yaml` (or reuse catalog `ref:`) with the high-XP mob. If no existing monster fits, add a one-off entry with hand-tuned `xp_reward`.
- Playbook update: add **3.5 Level-up full cycle** to `docs/e2e-playbook.md` (Russian, matching existing style) naming the world and expected assertions.
- Scenario report → `docs/e2e-reports/017-phase3-level-up-<date>.md`.
- Use Playwright MCP per project rule (hard blocker — if MCP isn't available, stop and restart session; do not skip).

## Acceptance Criteria

- [ ] `content/worlds/level_up_test/` loads cleanly (sanity-check logged)
- [ ] Single kill in that world crosses the L2 XP threshold
- [ ] Playbook scenario 3.5 added
- [ ] Playwright scenario executed end-to-end with full debug; report written
- [ ] All primary assertions above (modal content, post-level state, second-fight mechanics) verified
- [ ] Existing regression scenarios in the playbook still green
- [ ] Any discrepancy logged as blocker in the report — no silent patches

## Status

`done`

## Developer Notes

- Built the world as a single `arena_floor` location (3×3 conceptually, actual battle map is the default 13×13 — sufficient for the scenario). Player and both hostile NPCs are placed via `combat_position` at session start, no master-spawn scripting needed.
- Had to extend `NpcContent` with `xp_value: int = 0` (and propagate through `_to_npc`). NPCs previously always granted 0 XP — only monster templates rolled XP from CR. Cleanest fix: a single optional field, default 0, no breakage for existing worlds.
- Player point-buy ceiling is 27. First payload attempt (`STR 15 / CON 14 / CHA 15`) cost 29 and was rejected — confirmed via REST. Final spread (`STR 15 / CON 14 / CHA 14`) is what the playbook documents.
- The scenario was driven through Playwright MCP against the live `make serve` + `make frontend` stack. Player creation went via REST (avoids a long ability-score click loop in the wizard); world selection, combat, level-up modal, and Smite were all driven through the UI.
- Damage breakdown line confirmed both Dueling and Divine Smite simultaneously: `1d8 рубящий + 2d8 divine_smite + +2 str + +2 дуэлянт = 18`. Slot 1 decremented 2 → 1 in the same swing.
- Pre-flight script (`uv run python -c "..."` against `start_game` with `level_up_test`) used as the sanity check instead of writing a new integration test — phase 1 unit tests already cover `xp_for_cr` and the level threshold; phase 2 integration covers the level-up endpoint. Adding a third near-duplicate test would be redundant.
- E2E report at `docs/e2e-reports/017-phase3-level-up-2026-04-13.md`, screenshot at `docs/sprints/017-xp-leveling/e2e/level_up_post_smite.png`. Playbook scenario 3.5 added.
- Optional Fighter Action Surge companion scenario was skipped (not in primary AC, the time was better spent on the Paladin path documentation).
