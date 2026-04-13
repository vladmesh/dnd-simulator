# Task: Level-aware class features (dataclass + modifiers)

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 2 — Level-up mechanics + Paladin L2 fix

## Description

Make `FighterFeatures`, `RogueFeatures`, `PaladinFeatures` level-aware so they can
contribute modifiers and costs that come online only at specific class levels.

- Add `level: int` field to each dataclass (default `1`).
- `PaladinFeatures.collect_self_modifiers` / `collect_attack_modifiers` must return
  the fighting-style contribution only when `level >= 2` (L1 Paladin = no FS).
- `FighterFeatures` keeps FS at L1 (unchanged by level gate for FS itself), but the
  dataclass field is needed so Action Surge / Action pool can be gated later.
- `RogueFeatures.sneak_attack_dice` does not change at L2 (stays 1), but the `level`
  field is needed for future scaling; no behavior change required.
- Update `content_loader/creatures.py` to pass the character's level into the
  features dataclass when constructed.
- `validate_smite` (rules/divine_smite.py) must reject with a clear message when
  the Paladin's level is < 2, before checking spell slots. Message uses `_()`.

Do **not** touch resource pools or add Action Surge yet — that's task 2 and task 3.
This task is the pure-rules layer.

## Tests First

Product-level scenarios in `tests/unit/`:

- **Paladin L1 gets no Fighting Style bonus**: A Paladin L1 with Dueling equipped
  (one-handed weapon, shield), STR 16, longsword. Attack damage roll should equal
  `1d8 + 3 (STR)`, NOT include `+2 Dueling`. Advance to L2 (construct a L2 features
  instance) → damage now includes +2.
- **Paladin L1 cannot Divine Smite**: `validate_smite(paladin_l1, slot_level=1)`
  returns an error string mentioning level 2. `validate_smite(paladin_l2_with_slot,
  1)` returns None. Use the translation key plainly (assert substring `level 2` or
  equivalent — align with chosen wording).
- **Fighter L1 fighting style still works**: Fighter L1 with Defense still gets +1
  AC (no regression). A Fighter instance built from content with level=1 has
  `FighterFeatures(level=1, fighting_style=DEFENSE)`.
- **Rogue features carry level**: Rogue L1 → `RogueFeatures(level=1)`. Behavior
  unchanged (Cunning Action cost overrides still present).

## Implementation

1. Edit `core/class_features.py`:
   - Add `level: int = 1` to `FighterFeatures`, `RogueFeatures`, `PaladinFeatures`.
   - In `PaladinFeatures.collect_self_modifiers` / `collect_attack_modifiers`:
     if `self.level < 2`, return `[]` / `_empty_attack_contribution()` respectively.
2. Edit `content_loader/creatures.py` — the branches that build each features
   dataclass: pass `level=<character level>` from `CharacterContent`.
3. Edit `rules/divine_smite.py` `validate_smite`: after the class check, look up
   the Paladin's level via `creature.level` and return an error if `< 2`. Place
   the check before the spell-slot lookup so the user sees the correct reason.
4. Adjust any existing tests that assumed `PaladinFeatures()` without a level — pass
   `level=2` explicitly where the test expects L2 behavior (e.g. existing smite and
   FS tests from sprint 015).

## Acceptance Criteria

- [ ] New tests written and RED before implementation
- [ ] Implementation makes new tests GREEN
- [ ] `make check` passes — existing FS/smite tests updated to declare Paladin
      level=2 where they assume L2 behavior
- [ ] `PaladinFeatures(fighting_style=Dueling, level=1)` contributes zero
      modifiers/damage; `level=2` contributes +2
- [ ] `validate_smite` rejects Paladin L1 with a clear message (no silent fall-through)

## Status

`pending`
