# Task: Combat-log i18n + encounter-spawned perceiver

**Date:** 2026-06-29
**Sprint:** 019-control-plane-prep
**Phase:** 3 — Visible gaps + backlog reconcile + dead code

## Description

Close the visible RU combat-log dirt in one catalog pass. Two code changes plus a single locale regen.

1. **`combat-log-i18n-gaps` (code bug + catalog drift).**
   - `rules/handlers/movement.py` returns raw English `error=...` strings never wrapped in `_()`, so they never localize. Wrap every user-facing `error=` in the movement handlers in `_()`:
     - line 42 `"Move requires a direction"`
     - line 52 / 112 `"Not on the battle map"`
     - line 56 `"Cannot move there — blocked"` — also **drop the em-dash** (use `"Cannot move there, blocked"` or a comma per the house style)
     - line 103 `"No movement remaining"`, 107 `"Not in combat"`, 119 `"Already at that position"`, 124 `"No path to target"`, 152 `"Cannot move — insufficient budget"` (em-dash here too → comma), 187 `"Dash requires a turn budget"`
     - Import `from dnd_simulator.i18n import _` (mirror how other modules do it).
   - **Catalog drift:** the attack perceiver msgids in code carry a `{oa}` placeholder (`perception.py:141,145,148`) that the `.po` entries lack (`.po:245,248,251` — `"You attack {target}{weapon}{roll}{outcome}"`), so attack lines fall back to untranslated English. Regenerate the catalog so msgids match, then translate.
   - The `direction_label` and reputation strings the backlog item also named are **already** `_()`-wrapped — they only need the regen + RU translation to render, no code change.

2. **`encounter-spawned-perceiver`.** `EventType.ENCOUNTER_SPAWNED` has no `_DISPATCH` entry in `perception.py`, so every regional/locational spawn logs the fallback `Something happened (encounter_spawned)` (perception.py:565). Add `_perceive_encounter_spawned` and register it. Event data is `{"location_id": str, "names": list[str]}` (see `activation_manager.py:231`). Output a vague flavor line — **do not spoil the monster names** (danger-by-place is intentional, [[world-does-not-adapt-to-player]]). Something like `_("Something stirs nearby")`. Wrap in `_()`.

3. **Single locale pass** (do this last, after the code changes above so the new/changed msgids exist):
   - `make messages` — re-extract `.pot` (picks up the `{oa}` msgids, the now-wrapped movement errors, the encounter flavor line).
   - Update `src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.po` — translate every new/changed/fuzzy msgid to Russian (attack lines with `{oa}`, all movement errors, encounter flavor, any untranslated reputation/move strings the merge surfaces). Clear `#, fuzzy` markers after fixing.
   - `make compile-messages` — rebuild the `.mo`.

**Scope guard:** wrap errors only in `rules/handlers/movement.py` (the file the backlog item named). If you notice raw `error=` strings in other handlers, note them for backlog, don't sweep them here.

## Tests First

Product-level, run under a Russian session (use `set_language("ru")` from `dnd_simulator.i18n`; reset to the default in teardown so other tests aren't affected — the contextvar leaks across tests otherwise).

- **Blocked move localizes (movement handler).** Drive `handle_move` into the "blocked" branch (mover on the battle map, target cell blocked) with `set_language("ru")`. Assert the returned `ActionResult.error` is the Russian translation, not the English literal `"Cannot move there, blocked"`, and contains no em-dash. Add one more for an English session asserting the plain English string still comes back (regression guard on `_()`).
- **Attack line localizes (catalog drift fixed).** With `set_language("ru")`, `perceive_event` an `ENTITY_ATTACK` where the observer is the attacker. Assert the result is the Russian rendering (not the English `"You attack ..."`) and contains no literal `{oa}`/`{weapon}` placeholder text. This fails today because the msgid mismatch falls back to English.
- **Encounter spawn perceives to flavor, not fallback.** `perceive_event` an `ENCOUNTER_SPAWNED` event (`data={"location_id": "loc1", "names": ["Goblin", "Goblin"]}`). Assert the result does **not** contain `"Something happened"` and does **not** leak the monster names (`"Goblin"` not in output). Under `set_language("ru")`, assert it's the Russian flavor string.

## Implementation

- `rules/handlers/movement.py`: add the i18n import, wrap each `error=` literal. Keep messages terse, no em-dashes.
- `layers/entities/perception.py`: add `_perceive_encounter_spawned(event, observer, get_entity) -> str` near the other squad/world perceivers; register `EventType.ENCOUNTER_SPAWNED: _perceive_encounter_spawned` in `_DISPATCH`.
- Locale: run the three `make` targets; hand-translate the `.po`. Gotcha — `msgmerge` may mark drifted entries `#, fuzzy`; the runtime ignores fuzzy translations, so they must be de-fuzzed after translating or the RU string still won't render.

## Acceptance Criteria

- [ ] Tests written and RED (attack-line and encounter tests fail before the fix)
- [ ] Movement handler errors wrapped in `_()`, no em-dashes
- [ ] `_perceive_encounter_spawned` added and registered in `_DISPATCH`
- [ ] `.po` regenerated and RU translations filled (no fuzzy/untranslated for the affected msgids), `.mo` recompiled
- [ ] Tests GREEN
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

- Wrapped all 9 user-facing `error=` literals in `rules/handlers/movement.py` with `_()`; dropped both em-dashes (`"Cannot move there, blocked"`, `"Cannot move, insufficient budget"`). Added the `from dnd_simulator.i18n import _` import.
- Added `_perceive_encounter_spawned` (returns `_("Something stirs nearby")`, roster hidden per world-does-not-adapt-to-player) and registered `EventType.ENCOUNTER_SPAWNED` in `_DISPATCH`.
- Catalog drift fix: the 3 attack msgids in the `.po` were updated to carry the `{oa}` placeholder so they match the code msgids (`perception.py`) and now render RU instead of falling back to English.
- Locale: the project has no `msgmerge` target — the `.po` is hand-maintained, `make messages` only regenerates `messages.pot` (a build artifact; pygettext3 prints harmless "unexpected token" warnings on f-strings). Hand-added RU translations for the 9 movement errors, the encounter flavor, the 2 reputation strings (named in the backlog item, previously missing), plus adjacent combat-log strings that were untranslated and render right beside the attack line: the OA marker `" (opportunity attack)"`, the 3 "seize the opening" variants, and disengage. Recompiled the `.mo` with `make compile-messages`.
- Out of scope, noted for backlog: `_perceive_take` (loot) strings are still untranslated in the RU `.po` — not named by this task's backlog item, left for a future i18n sweep.
- Tests: 5 new (3 in test_perception.py: attack-line RU render, encounter not-fallback + no name leak, encounter RU flavor; 2 in test_handlers_movement.py: blocked-move RU + EN). All use `set_language` with an `set_language("en")` teardown to avoid contextvar leak.
