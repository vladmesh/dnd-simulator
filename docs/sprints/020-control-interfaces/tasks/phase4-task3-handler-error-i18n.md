# Task: i18n sweep of action-failure error strings

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 4 — Save robustness & i18n polish

## Description

Second half of `combat-log-i18n-gaps`, broadening the fix per sprint scope decision (full i18n sweep). ~23 `ActionResult.error` strings across `rules/handlers/` are raw English f-strings/literals, never wrapped in `_()`, so they stay English at `DND_LANGUAGE=ru` when an action is rejected (surfaced to the player as the failure reason). Unlike the combat-log strings in task 2, these were never translatable at all.

Sites (verify exact lines at implementation time — they drift):

- `rules/handlers/action_surge.py`: `"Only characters can use Action Surge"` (29), `"Action Surge not available (requires Fighter L2+)"` (33), `"Action Surge already used"` (35), `"Action Surge requires an active turn"` (38)
- `rules/handlers/items.py`: `"Nothing to say (text is empty)"` (47), `"Cannot use item of type '{...}' — try equipping it instead"` (102, **also has an em-dash**), `"Only Paladins can use Lay on Hands"` (114), `"Amount must be at least 1"` (118), `"No lay_on_hands pool"` (123), `"Insufficient pool: {...} remaining, need {...}"` (127), `"Cannot resolve target"` (135), `"Target '{...}' not found"` (138), `"Only characters can use Second Wind"` (218)
- `rules/handlers/loot.py`: `"Target '{...}' cannot be looted"` (35)
- `rules/handlers/trade.py`: `"Merchant '{...}' not found"` (43, 82), `"Only characters can trade"` (46, 85)
- `rules/handlers/equipment.py`: `"Item {...} not in inventory"` (100), `"Item {...} is not a {...}"` (102), `"Item {...} is a {...} accessory, not {...}"` (107), `"No {...} equipped"` (131)

Reference for the correct shape: `rules/handlers/attack_resolution.py:125,139` and `combat_manager.py` already wrap their errors in `_()` and have catalog entries.

## Tests First

Product-level. Use the existing i18n test setup to assert Russian output:

1. **Rejected action speaks Russian.** With `ru` active, a non-Paladin attempting Lay on Hands gets an `ActionResult(success=False)` whose `error` is the Russian translation of "Only Paladins can use Lay on Hands", not the English literal. Pick 2-3 representative handlers (e.g. lay-on-hands gate, equip "item not in inventory", trade "merchant not found") so the parametrized-message path (`.format(...)`) is exercised, not just bare literals.
2. **No em-dash in the item-type error.** The "cannot use item of type" message contains no `—` (em-dash) — matches the project writing-style rule; use a comma or period.

## Implementation

- Wrap each string in `_()`. For parametrized messages convert the f-string to a gettext template with **named placeholders + `.format()`**, never an f-string (gettext can't extract an f-string's runtime value): e.g. `error=_("Insufficient pool: {remaining} remaining, need {amount}").format(remaining=pool.current_uses, amount=amount)`. Pull attribute access out of the template — `item.item_type` becomes a local var interpolated via `.format(item_type=...)`.
- Fix the em-dash in `items.py:102` while wrapping it.
- Import `_` where missing: `from dnd_simulator.i18n import _`.
- `make messages` → add Russian `msgstr` for every new msgid in the `ru` `.po` → `make compile-messages`.

Gotcha: keep placeholder names stable between msgid and msgstr; don't leave any of the new msgids untranslated (they'd fall back to English and defeat the task).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Every listed handler error string is wrapped in `_()` and has a Russian translation
- [ ] No em-dash remains in the item-type error string
- [ ] `make messages` reports no untranslated handler error msgids; `.mo` recompiled
- [ ] `combat-log-i18n-gaps` marked resolved in `docs/BACKLOG.md` (both halves done across tasks 2-3)

## Status

`done`

## Developer Notes

Implemented as planned. Wrapped 20 `ActionResult.error` strings in `_()` across 5 handler files (action_surge, items, loot, trade, equipment), added `from dnd_simulator.i18n import _` to the 3 that lacked it (action_surge already, items/loot/trade/equipment got it). Parametrized messages converted from f-strings to gettext templates with named placeholders + `.format()` (Insufficient pool, Target not found, merchant not found, item-not-in-inventory, item-not-a-type, accessory-wrong-slot, no-X-equipped, item-type). Attribute access pulled into `.format()` args (`item.item_type.value`, `cfg.item_type.value`, slot `.value`s).

Em-dash in `items.py` item-type error replaced with a comma: `"Cannot use item of type '{item_type}', try equipping it instead"`.

Notes:
- `item.item_type` is a `StrEnum`, so the old f-string already rendered the bare value ("armor") not `ItemType.ARMOR` — switching to `.format(item_type=item.item_type.value)` keeps output identical.
- Added 20 ru `msgstr` entries under a new `rules/handlers/` section in the `.po`; `make compile-messages` regenerated the `.mo`. No duplicate msgids (checked before appending).
- `make format` split the two `Merchant '{merchant_id}' not found` lines (were 121 chars) across lines — auto-applied, no manual edit.

Tests: 4 new in `test_handler_error_i18n.py` (3 RU-rendering — lay-on-hands gate bare-literal path, equip + buy `.format()` paths asserting the interpolated id survives; 1 no-em-dash on the item-type error). No old tests modified — handler-error assertions run under `DND_LANGUAGE=en` (conftest) so wrapping in `_()` left English output unchanged. `make check` green (backend 2317, frontend 260). Closes `combat-log-i18n-gaps` (both halves, tasks 2-3) — marked resolved in BACKLOG.md.
