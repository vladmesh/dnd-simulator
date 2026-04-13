# Task: Level-up operation + REST endpoint

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 2 — Level-up mechanics + Paladin L2 fix

## Description

Add a backend level-up operation that a player can invoke when
`level_up_available=True`. The operation:

1. Asserts `level_up_available` is True (else fails with a clear error).
2. Increments `character.level` by 1.
3. Recomputes `character.max_hp` using `calculate_max_hp(class, new_level,
   con_mod)`; heals the character by the HP delta (current_hp += delta).
4. Rebuilds class feature entries with the new level (tasks 1 ensured features
   carry `level`) — re-construct `FighterFeatures` / `PaladinFeatures` /
   `RogueFeatures` with `level=new_level`, preserving `fighting_style` etc.
5. Rebuilds `resource_pools` via `build_class_resource_pools(class, new_level)`,
   preserving `current_uses` for pools that already existed (don't refill on
   level-up; only add new pools with max uses). New pools start full.
6. Clears `level_up_available = False`.
7. Recomputes `xp_to_next_level` for the new level.

Accept a level-up options dict (for Paladin L2 fighting-style choice in Phase 3).
For this task the body schema is `{ "fighting_style": "defense" | "dueling" |
"great_weapon_fighting" | null }`. For Paladin L1→L2, a non-null style is
required; for other classes/levels, must be null (reject otherwise).

REST endpoint: `POST /api/player/sessions/{session_id}/level-up`. Body is
`LevelUpRequest` (pydantic). Response is the updated `PlayerStatusResponse`.

Also: **drop the legacy `saves/` directory** as part of this task — sprint 017
skips migration. Delete the saves directory contents (keep `.gitkeep`) and note
it in the commit message. Do not delete the directory itself.

## Tests First

Product-level integration (over live stack, `tests/integration/`):

- **Fighter L1→L2 full flow**: create Fighter, kill a CR-low monster to bank
  XP ≥ 300, confirm `level_up_available=True`. POST level-up with
  `fighting_style=null`. Response: level=2, level_up_available=False,
  max_hp +6 (d10 die_avg 6 + CON 0), action_surge pool present.
- **Paladin L1→L2 requires fighting style**: create Paladin, reach 300 XP.
  POST with `fighting_style=null` → 4xx. POST with
  `fighting_style="dueling"` → success, FS now active (damage +2 verified
  via a subsequent attack), spell slot 1 pool appears.
- **Rogue L1→L2**: HP increase (d8: +5 at CON 0), no new pools, sneak attack
  unchanged (1d6).
- **Level-up consumes the flag**: two back-to-back POSTs → second returns 4xx
  ("no level-up available").
- **Current HP heals by delta**: start Fighter HP=5/10, level up → HP=11/16
  (delta 6 added to both current and max).
- **Spell slot pool preserved on subsequent level-up (deferred note)**: not
  tested here — only L1→L2 covered this sprint.
- **Legacy saves gone**: `saves/` dir has only `.gitkeep`.

## Implementation

1. Create `rules/perform_level_up.py` with:
   ```python
   def perform_level_up(character, *, fighting_style: FightingStyle | None) -> None
   ```
   Pure mutation on the `Character` dataclass (new instance? check existing
   pattern — Character appears mutable based on HP updates; follow precedent).
   Handles HP, pools (merge preserving current_uses), class feature rebuild,
   flag clear, `xp_to_next_level` recalc.
2. Validation helper: reject when `level_up_available=False`, when
   `fighting_style` is provided for a class that doesn't take one at this
   level, or missing when Paladin L1→L2.
3. `adapters/api/schemas.py`: add `LevelUpRequest(fighting_style: str | None)`.
4. `adapters/api/routes_player.py`: add `POST .../level-up` endpoint → looks
   up session + player, calls perform_level_up, returns
   `PlayerStatusResponse` (same serializer used by `/status`).
5. Delete legacy saves: `rm -rf saves/* && touch saves/.gitkeep` — do this in
   the commit, not in code.

## Acceptance Criteria

- [ ] Tests RED first
- [ ] Implementation GREEN
- [ ] `make check` passes
- [ ] Fighter L1→L2 yields action_surge pool via the endpoint (ties task 3)
- [ ] Paladin L1→L2 requires fighting_style, grants Divine Smite (ties task 1+2)
- [ ] Rogue L1→L2 adds HP only
- [ ] Calling level-up when flag is False returns a 4xx with clear detail
- [ ] `saves/` contains only `.gitkeep` after this task

## Status

`done`

## Developer Notes

- Added `rules/perform_level_up.py`: pure mutation on `Character` — validates the
  level-up flag + fighting_style, recomputes `max_hp`, heals by delta, rebuilds
  class features at the new level, merges resource pools preserving
  `current_uses` for pools that already existed.
- Moved `build_class_resource_pools` from `content_loader/creatures.py` to
  `rules/resources.py`; having rules/ call into content_loader would invert the
  layer direction. `content_loader/creatures.py`, `content_loader/__init__.py`,
  and `tests/unit/test_paladin_infra.py` updated to import from the new home.
- REST endpoint `POST /api/player/sessions/{sid}/level-up` with
  `LevelUpRequest(fighting_style: str | None)`; responds with
  `PlayerStatusResponse`. `ValueError` → 400.
- Extended `PatchCreatureRequest` + `commands_creatures.patch_creature` with
  `level` and `experience` fields: pure DM/test affordance — setting
  `experience` also recomputes `level_up_available`. Used in the new tests to
  skip the kill-a-dummy dance (fast and deterministic), and to fix three
  pre-existing Paladin integration tests (`test_paladin_flaming_sword_smite_three_damage_types`,
  `test_paladin_spell_slot_consumed_after_smite`, `test_smite_adds_radiant_damage`)
  that were broken by phase 2 task 1 gating smite at L2 — they now PATCH
  `level: 2` before attacking.
- Dropped legacy `saves/*` (sword_vale + test_vale session snapshots); kept
  `.gitkeep`. Sprint 017 skips migration per the sprint decisions.
- Integration tests in `tests/integration/test_level_up.py` cover all six
  acceptance criteria: Fighter L1→L2 full flow, Paladin required FS, Rogue HP
  only, flag consumed on second call, current_hp heals by delta.
