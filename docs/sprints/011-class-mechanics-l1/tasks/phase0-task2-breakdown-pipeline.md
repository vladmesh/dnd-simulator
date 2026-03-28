# Task: Attack & Damage Breakdown Pipeline

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown

## Description

Thread structured dice results through the attack/damage resolution chain so that event data carries full roll provenance: individual die faces, rerolls, and modifier breakdown. The frontend will receive everything it needs to render a detailed clickable breakdown.

### Enriched types

**`CheckResult`** — add `d20: D20Result` field. Keep `roll` and `total` as-is for now (widely used). The `d20` field carries the full advantage/disadvantage story.

**`DamageResult`** — add `dice_result: DiceResult | None` field. On hit, each damage component carries its individual die faces. `None` for flat-only bonuses.

**`AttackResult`** — no structural change. But `damage` entries now carry `dice_result`, and `attack_check` carries `d20`.

### Event serialization

`combat_manager._build_attack_event()` enriches event data:

```python
"attack_roll": {
    "natural": 14,
    "d20": {"result": 14, "sides": 20},              # always present
    "d20_alt": {"result": 7, "sides": 20},            # only with advantage/disadvantage
    "components": [...],                                # unchanged
    "total": 19,
    "advantage": true,
    "disadvantage": false,
}

"damage_components": [
    {
        "source": "weapon",
        "dice": "1d8",
        "dice_detail": [{"sides": 8, "result": 6}],
        "amount": 6,
        "type": "slashing"
    },
    {
        "source": "sneak_attack",
        "dice": "2d6",
        "dice_detail": [
            {"sides": 6, "result": 5, "original": 1},   # GWF reroll example
            {"sides": 6, "result": 4}
        ],
        "amount": 9,
        "type": "piercing"
    },
    {
        "source": "dueling",
        "dice": "",
        "dice_detail": [],
        "amount": 2,
        "type": "slashing"
    }
]
```

### resolve_attack threading

`resolve_attack()` needs to pass `DiceResult` through damage resolution. Currently `damage_roll()` returns `int`. Options:

- **Option A:** `resolve_attack` calls `roll()` directly (not `damage_roll()`), captures `DiceResult`, uses `.total` for arithmetic, stores `DiceResult` in `DamageResult`.
- **Option B:** `damage_roll()` returns `DiceResult` instead of `int`.

Option A keeps `damage_roll()` simple (backward compat) and gives `resolve_attack` full control over reroll parameters. Preferred.

### Healing events

`handle_second_wind` and `handle_use_item` also emit dice. Add `dice_detail` to their event data for consistency. Not clickable in Phase 0 Task 3, but the data is there for future use.

## Tests First

**CheckResult with D20Result:**
- `attack_roll(modifier=5, ac=15, rng=seeded)` → `CheckResult` with `d20.natural == seeded_value`, `d20.alt is None`
- `attack_roll(modifier=5, ac=15, advantage=True, rng=seeded)` → `d20.alt is not None`, `d20.die.result >= d20.alt.result`

**DamageResult with DiceResult:**
- `resolve_attack()` on hit → each `DamageResult` has `dice_result` with correct die faces
- `resolve_attack()` on miss → empty damage tuple (no dice_result to check)
- Extra damage (Sneak Attack "2d6") → `dice_result` has 2 `DieRoll(sides=6)`
- Critical hit → `dice_result` has doubled dice count (2d6 crit → 4 `DieRoll`s)

**Event data serialization:**
- `_build_attack_event()` output includes `attack_roll.d20` with `result` and `sides`
- `_build_attack_event()` with advantage includes `attack_roll.d20_alt`
- `_build_damage_components()` output includes `dice_detail` list for each component
- `dice_detail` entries have `original` field when reroll occurred
- Flat-only damage components have empty `dice_detail`

**Healing event data:**
- Second Wind event data includes `dice_detail` for 1d10 roll
- Use Item (potion) event data includes `dice_detail` for heal dice

**Perception formatting unchanged:**
- `_format_roll()` still produces correct text output
- `_format_damage()` still produces correct text output

## Implementation

1. **`rules/checks.py`** — `attack_roll()` stores `D20Result` on `CheckResult.d20`. `damage_roll()` unchanged (returns int).
2. **`rules/combat.py`** — `DamageResult` gains `dice_result: DiceResult | None = None`. `resolve_attack()` calls `roll()` directly for damage, stores `DiceResult` on each `DamageResult`. Accepts `reroll_below: int = 0` parameter for GWF.
3. **`combat_manager.py`** — `_build_attack_event()` serializes `d20`/`d20_alt` from `CheckResult.d20`. `_build_damage_components()` serializes `dice_detail` from `DamageResult.dice_result`. `_roll_attack_dice()` stores `DiceResult` on rolled components.
4. **`rules/handlers/items.py`** — `handle_second_wind` and `_apply_potion` capture `DiceResult` from `roll()`, include `dice_detail` in event data.
5. **`perception.py`** — no changes needed (reads existing fields that are preserved).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] `CheckResult` carries `D20Result` with both dice on advantage
- [ ] `DamageResult` carries `DiceResult` with individual die faces
- [ ] Event data includes `d20`, `d20_alt`, `dice_detail` fields
- [ ] `dice_detail` entries include `original` when rerolled
- [ ] Healing events include `dice_detail`
- [ ] Perception text formatting unchanged
- [ ] `make check` green

## Status

`pending`
