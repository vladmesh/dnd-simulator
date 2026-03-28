# Task: Structured Dice Results

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown

## Description

Refactor `rules/dice.py` so that every dice roll returns structured data with individual die results. Create core data types in `core/rolls.py`. All callers migrate to `.total` for arithmetic. Add `reroll_below` parameter for GWF-style mechanics (generic: works for any "reroll dice showing N or below" effect).

### New types (`core/rolls.py`)

```python
@dataclass(frozen=True)
class DieRoll:
    """One physical die."""
    sides: int            # d6, d8, d20
    result: int           # final kept value
    original: int | None = None  # before reroll (GWF, Halfling Lucky, ...)

@dataclass(frozen=True)
class DiceResult:
    """Structured result of a dice expression like '2d6+3'."""
    expression: str       # "2d6+3"
    dice: tuple[DieRoll, ...]  # each die individually
    flat: int             # +3 part from expression
    total: int            # sum of dice + flat

@dataclass(frozen=True)
class D20Result:
    """d20 roll with advantage/disadvantage tracking."""
    die: DieRoll                # the kept die
    alt: DieRoll | None = None  # the other die if advantage/disadvantage
    advantage: bool = False
    disadvantage: bool = False

    @property
    def natural(self) -> int:
        return self.die.result
```

### Changes to `rules/dice.py`

- `roll(expr, *, reroll_below=0, rng) -> DiceResult` (was `-> int`)
- `roll_d20(*, advantage, disadvantage, rng) -> D20Result` (was `-> int`)
- `reroll_below`: each die showing <= threshold is rerolled once. New result kept regardless. `DieRoll.original` records the pre-reroll value.

### Caller migration

Every caller that does arithmetic with `roll()` or `roll_d20()` result switches to `.total` / `.natural`:
- `rules/checks.py` — `attack_roll`, `ability_check`, `saving_throw`, `damage_roll`
- `rules/combat.py` — `resolve_attack`, `roll_initiative`
- `rules/handlers/items.py` — `_apply_potion`, `handle_second_wind`
- `layers/entities/combat_manager.py` — `_roll_attack_dice`

## Tests First

**DiceResult structure:**
- `roll("2d6+3", rng=seeded)` returns `DiceResult` with exactly 2 `DieRoll(sides=6)`, `flat=3`, `total` equals sum of dice + 3
- `roll("1d8", rng=seeded)` returns `DiceResult` with 1 `DieRoll(sides=8)`, `flat=0`
- `roll("4")` (constant) returns `DiceResult` with empty dice tuple, `flat=4`, `total=4`
- `roll("0d6+5")` — edge case, no dice, flat only

**Reroll mechanics:**
- `roll("2d6", reroll_below=2, rng=seeded)` — seed RNG so at least one die shows 1 or 2. Verify that die has `original` set and `result` is the rerolled value
- Rerolled die keeps new value even if still <= threshold (no recursive reroll)
- Dies showing > threshold have `original=None`
- `reroll_below=0` (default) — no rerolls, all `original=None`

**D20Result structure:**
- `roll_d20(rng=seeded)` returns `D20Result` with `alt=None`, `advantage=False`, `disadvantage=False`
- `roll_d20(advantage=True, rng=seeded)` — both dice present, `die.result >= alt.result`, `advantage=True`
- `roll_d20(disadvantage=True, rng=seeded)` — both dice present, `die.result <= alt.result`, `disadvantage=True`
- `roll_d20(advantage=True, disadvantage=True)` — cancel out, straight roll, `alt=None`
- `.natural` property returns `die.result`

**Backward compatibility:**
- All existing tests pass after migration to `.total` / `.natural`
- `damage_roll()` still returns `int` (it wraps `roll().total` — internal detail, callers unchanged)

## Implementation

1. Create `src/dnd_simulator/core/rolls.py` with `DieRoll`, `DiceResult`, `D20Result`
2. Refactor `rules/dice.py`:
   - `roll()` — parse expression, roll each die individually into `DieRoll`, apply `reroll_below`, build `DiceResult`
   - `roll_d20()` — roll one or two d20s, build `D20Result`
3. Update `rules/checks.py`:
   - `attack_roll()` — use `d20_result = roll_d20(...)`, arithmetic with `.natural`
   - `damage_roll()` — `return roll(expr, ...).total` (signature unchanged, returns int)
4. Update `rules/combat.py` — `roll_initiative` uses `.natural`
5. Update `rules/handlers/items.py` — `.total` for healing rolls
6. Update `layers/entities/combat_manager.py` — `.total` for bonus dice rolls

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] `core/rolls.py` created with `DieRoll`, `DiceResult`, `D20Result`
- [ ] `roll()` returns `DiceResult` with individual die faces
- [ ] `roll_d20()` returns `D20Result` with both dice when advantage/disadvantage
- [ ] `reroll_below` works correctly (single reroll, records original)
- [ ] All callers migrated, `make check` green
- [ ] No behavior changes in game output (pure refactor + structured data)

## Status

`done`

## Developer Notes

Clean refactor. `roll()` now returns `DiceResult`, `roll_d20()` returns `D20Result` — both carry individual die faces. `reroll_below` parameter added for GWF-style mechanics (single reroll, records original value). All 6 caller sites migrated to `.total`/`.natural`. Existing test_dice.py updated to use structured accessors. No behavior changes — pure data enrichment. 14 new tests, 0 old tests broken.
