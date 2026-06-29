# Task: rules/ purity — determinism (structlog, rng, lair)

**Date:** 2026-06-30
**Sprint:** 020-thermo-sweep
**Phase:** 1 — Корректность и инварианты

## Description

Restore the VISION invariant "rules are pure functions — no state, no I/O" on three fronts. Behavior unchanged.

1. **structlog out of pure rules.** `rules/sneak_attack.py:22,138` logs from `check_sneak_attack()` (caller: `combat_manager.py:295`). `rules/rule_brain.py:28` logs decision traces from many `_try_*` methods + `_log_turn_start` (callers: `round.py:332,411,456`). Pure modules must not do I/O.

2. **Thread `rng` via `ActionContext`.** `ActionContext` (`rules/validation.py:31-39`) has no `rng` field. Healing (`rules/handlers/items.py:71`, `_apply_potion`) and Second Wind (`:221`, `handle_second_wind`) call `roll(...)` with no threaded rng, so they fall back to the module global (`dice.py:_rng`). Attack resolution can take an `rng` (`rules/combat.py`), so reproducibility under seeded replay is inconsistent. Thread one rng through `ActionContext` into the item handlers.

3. **Lair depletion → pure rule.** `ecology/layer.py:141-149` (`_apply_lair_dematerialize`) rolls `get_global_rng().random() < lair.depletion_chance` and mutates `lair.state` inline. The decision belongs in `rules/`, with the roll injected.

## Tests First (RED)

**Seeded heal reproducibility (pytest):**
- Drink the same healing potion twice under two `random.Random(seed)` instances seeded identically, threaded via `ActionContext.rng`; assert the healed amounts are identical across the two runs. Then with a different seed, assert the amount can differ (proves the threaded rng is actually used, not a constant). Do the same for Second Wind (`1d10 + level`).

**sneak_attack returns reason, doesn't log:**
- `check_sneak_attack(...)` returns the trigger reason (`advantage` / `ally_adjacent`) to the caller alongside the extra damage; assert the reason is correct for an advantage hit and for an ally-adjacent hit. Assert `rules/sneak_attack` imports no `structlog` / `logging` (module-level check, or simply no logger attribute).

**Lair depletion pure fn (pytest):**
- `rules/lairs.should_deplete(lair, roll)` truth table: core lair with core dead → `True`; core lair with core alive → `False`; coreless lair with empty roster, `depletion_chance>0`, `roll < chance` → `True`; same with `roll >= chance` → `False`; coreless lair with surviving members → `False`; `depletion_chance == 0` → `False`. Then an ecology-layer test: a full wipe of a coreless lair with the injected roll below the chance transitions `ACTIVE → DEPLETED` and survives a layer save/load (existing lair tests show the pattern).

## Implementation (GREEN)

**structlog:**
- `sneak_attack.py`: drop the logger; return the reason (e.g. extend the return to include `reason: str | None`, or a small result type). `combat_manager.resolve_attack` (the impure caller) logs it.
- `rule_brain.py`: drop the module logger and the per-`_try_*` debug logs (low-value decision tracing; pure rules shouldn't emit). Preserve the two useful traces — turn-start state and the chosen action — by logging them in the caller (`round.py`, where `choose_action` is invoked), using data already available there (creature, returned action). Don't change the `Brain.choose_action` signature if avoidable; if a reason is genuinely needed, return it rather than logging inside the brain.

**rng:**
- Add `rng: random.Random | None = None` to `ActionContext`.
- Populate it where `ActionContext` is built in `round.py` (combat `:260-266`, peaceful `:384-388`, reaction `:462`) from the threaded/seedable rng (use `get_global_rng()` so seeding once stays reproducible).
- In `handlers/items.py`, pass `ctx.rng` to the heal `roll(...)` (`_apply_potion`, and its `handle_use_item` caller) and to `handle_second_wind`'s roll. `dice.roll`/`roll_d20` already accept `rng or _rng`.
- (Related but optional: `combat_manager` could pass `rng` to `resolve_attack` too — note it, don't expand scope unless trivial.)

**lair:**
- New `rules/lairs.py` with `should_deplete(lair: Lair, roll: float) -> bool` — pure, no RNG inside. Encodes: core-died OR (coreless AND no survivors AND `depletion_chance > 0` AND `roll < depletion_chance`).
- `ecology/layer.py` rolls (`get_global_rng().random()`), calls `should_deplete(lair, roll)`, then sets `lair.state = LairState.DEPLETED`. The mutation stays in the layer; only the decision moves to rules.

Files: `rules/sneak_attack.py`, `rules/rule_brain.py`, `layers/entities/combat_manager.py`, `round.py`, `rules/validation.py`, `rules/handlers/items.py`, `rules/lairs.py` (new), `layers/ecology/layer.py`, `core/lair.py` (read-only reference).

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] `rules/sneak_attack.py` and `rules/rule_brain.py` import no logging; trace moved to callers or returned
- [ ] `ActionContext.rng` threaded; heal + Second Wind reproducible under a seeded rng
- [ ] `rules/lairs.should_deplete(lair, roll)` exists and is pure; ecology injects the roll; depletion behavior + save/load unchanged
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
