# Task: rules/ purity — i18n handler errors

**Date:** 2026-06-30
**Sprint:** 020-thermo-sweep
**Phase:** 1 — Корректность и инварианты

## Description

Handler error strings bypass gettext, breaking the i18n invariant (English base, Russian default). With `DND_LANGUAGE=ru`, equip/use/trade/loot/Action-Surge failures silently fall back to English. `movement.py` already wraps everything in `_()`; the rest don't. This finishes `combat-log-i18n-gaps` for the handler half (Sprint 019 phase 3 closed the combat-log catalog drift).

Raw (un-`_()`) `ActionResult(error=...)` strings to wrap:
- `rules/handlers/items.py:47,102,114,118,123,127,135,138,218`
- `rules/handlers/equipment.py:100,102,107,131`
- `rules/handlers/trade.py:43,46,82,85`
- `rules/handlers/action_surge.py:29,33,35,38`
- `rules/handlers/loot.py:35`
- (`combat.py` has no error strings; `movement.py` is already compliant.)

## Tests First (RED)

Mirror the existing `TestMoveErrorI18n` pattern (`tests/unit/test_handlers_movement.py:135-168`): `set_language("ru")`, trigger each handler failure, assert the returned `error` is the Russian translation (contains Cyrillic) and not the raw English, and contains no em-dash (writing-style rule). Cover at least one failure per file:
- items: use a non-usable item type (e.g. try to "use" a weapon) → translated error; Lay on Hands by a non-Paladin → translated error.
- equipment: equip an item not in inventory → translated error.
- trade: trade with a non-existent merchant → translated error.
- action_surge: Action Surge without the feature → translated error.
- loot: take from a non-lootable target → translated error.

The tests are RED first because the strings are raw English (no Cyrillic) until wrapped + translated + compiled.

## Implementation (GREEN)

1. `from dnd_simulator.i18n import _` in each handler file (some already import it for other reasons — confirm).
2. Wrap every listed `error=...` string in `_()`. For f-strings, keep interpolation outside the catalog id where possible (e.g. `_("Item {id} not in inventory").format(id=item_id)`) so the msgid is stable and translatable — match how `movement.py` / `perception.py` handle parameterized messages.
3. Replace any em-dash in these strings with a comma/period (writing-style rule; the review flagged one in movement, watch for others).
4. `make messages` to extract new msgids into `messages.pot`.
5. Add Russian translations for the new msgids in `src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.po`.
6. `make compile-messages` to produce the `.mo`.

Gotcha: `_()` alone returns English if the msgid isn't in the compiled `.po`. The test asserts Cyrillic, so the translation + compile steps are required, not optional.

Files: the six handler files above; `locale/messages.pot`; `locale/ru/LC_MESSAGES/dnd_simulator.po` (+ compiled `.mo`).

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] Every listed handler error string wrapped in `_()`, parameterized cleanly
- [ ] New msgids extracted, translated to Russian, and compiled; RU-locale tests show Cyrillic for each handler failure
- [ ] No em-dashes in the touched strings
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
