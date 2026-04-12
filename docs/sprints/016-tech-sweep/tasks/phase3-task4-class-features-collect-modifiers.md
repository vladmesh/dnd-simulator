# Task: ClassFeatures.collect_modifiers() — push fighting style logic into classes

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 3 — Core Boundaries

## Description

`rules/modifiers.py` hardcodes `FighterFeatures` and `PaladinFeatures` checks for fighting styles:

- Lines 100–105 (`collect_self_modifiers`) — Defense style → +1 AC when armored.
- Lines 288–300 (`attack_modifiers`) — Dueling → +2 damage (one-handed only), GWF → reroll 1s/2s on two-handed.

Adding a new class with a fighting style (Ranger) requires editing `modifiers.py` — the Paladin Defense AC bug (already fixed in phase 1) is exactly this class of failure.

Fix: each `ClassFeatures` subclass declares its own modifiers via a method. `rules/modifiers.py` iterates `creature.class_features` and calls the method — no knowledge of concrete types.

Proposed API on `ClassFeatures` (add to all subclasses):

```python
def collect_self_modifiers(self, creature: Creature) -> list[Modifier]: ...
def collect_attack_modifiers(self, creature: Creature, weapon: Weapon | None) -> AttackContribution: ...
```

Where `AttackContribution` carries damage bonus + roll components + flags like `gwf_reroll`. Shared fighting-style logic (Defense/Dueling/GWF) lives in a helper module `rules/fighting_style.py` or a mixin — Fighter and Paladin both call it with their own `fighting_style` field; Rogue returns empty.

## Tests First

1. **Product test: Paladin with Defense style in plate armor has +1 AC** — assert `effective_ac(paladin)` == base AC + 1. Covers the regression that already bit us.

2. **Product test: Fighter with Dueling + longsword + shield gets +2 to damage** — attack a dummy with AC 0, assert damage rolled includes +2 from Dueling (inspect roll components).

3. **Product test: Fighter with Great Weapon Fighting rerolls 1s and 2s on 2H weapon** — stub randomness so first d10 rolls land on 1, confirm reroll happens; with a one-handed weapon, confirm no reroll even if GWF selected.

4. **Product test: Rogue's class features contribute no fighting-style modifiers** — spawn a Rogue, assert `collect_self_modifiers(rogue)` contains no `fighting_style_*` source and no Dueling damage added on attacks.

5. **Architecture test:** `grep -n "get_feature(FighterFeatures)\|get_feature(PaladinFeatures)" src/dnd_simulator/rules/modifiers.py` → empty.

## Implementation

1. Define `AttackContribution` dataclass (in `core/modifiers.py` or a new `core/class_contribution.py`) with fields: `damage_bonus: int`, `damage_components: list[RollComponent]`, `gwf_reroll: bool` (extend as needed).
2. Add two methods to each `ClassFeatures` subclass (`FighterFeatures`, `RogueFeatures`, `PaladinFeatures`) in `core/class_features.py`:
   - `collect_self_modifiers(creature) -> list[Modifier]`
   - `collect_attack_modifiers(creature, weapon, weapon_def) -> AttackContribution`
3. Create `rules/fighting_style.py` with two pure helpers that take a `FightingStyle` + creature + weapon and return the appropriate modifiers / contribution. `FighterFeatures` and `PaladinFeatures` both call them.
4. `rules/modifiers.py`:
   - `collect_self_modifiers()`: iterate `creature.class_features`, extend with each's `collect_self_modifiers(creature)`. Remove the FighterFeatures/PaladinFeatures-specific block.
   - `attack_modifiers()`: iterate `creature.class_features`, merge `AttackContribution`s. Remove the hardcoded block.
5. Remove unused imports (`FighterFeatures`, `PaladinFeatures`, `FightingStyle` if no longer referenced).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `grep -n "FighterFeatures\|PaladinFeatures" src/dnd_simulator/rules/modifiers.py` → empty
- [ ] Each `ClassFeatures` subclass implements both `collect_self_modifiers` and `collect_attack_modifiers`
- [ ] Fighting style logic not duplicated between Fighter and Paladin — shared helper exists
- [ ] Adding a new `ClassFeatures` subclass requires zero edits to `rules/modifiers.py`

## Status

`done`

## Developer Notes

- Added `AttackContribution` dataclass in `core/modifiers.py` carrying `damage_bonus`, `damage_components`, `gwf_reroll`.
- Added `collect_self_modifiers(creature)` + `collect_attack_modifiers(creature, *, melee)` methods on `FighterFeatures`, `RogueFeatures`, `PaladinFeatures`.
- Shared fighting-style logic lives in `rules/fighting_style.py` (`self_modifiers_for_style`, `attack_contribution_for_style`). Fighter and Paladin methods both delegate; Rogue returns empty.
- `rules/modifiers.py` no longer imports `FighterFeatures`/`PaladinFeatures`/`FightingStyle` — it just iterates `creature.class_features` and calls the protocol methods.
- `core/class_features.py` uses lazy imports for the `rules/fighting_style` helpers to avoid a core→rules module-level dependency while still centralizing the logic.
- Added 7 product tests (Paladin Defense/Dueling/None, Rogue no fighting-style contribution, architecture test that rules/modifiers.py doesn't reference feature subclasses). All 92 tests in test_modifiers.py and full `make check` green (2057 backend + 220 frontend).
