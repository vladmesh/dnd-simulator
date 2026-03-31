# Task: Backend — Derive Stats + Equip Starting Gear

**Date:** 2026-04-01
**Sprint:** 013-char-creation
**Phase:** 2 — Creation API + Frontend Form

## Description

Rework `CreatePlayerRequest` and `GameService.create_player()` so the server computes HP, AC, gold, and starting equipment from class + ability scores. The client sends only: name, race, class, alignment, ability_scores, fighting_style (optional).

Changes:

1. **Schema** (`adapters/api/schemas.py`): drop `hp`, `ac`, `gold`, `level`, `attacks`, `items` from `CreatePlayerRequest`. Add `fighting_style: str | None = None`. Make `ability_scores` required (not optional). Restrict documentation but actual enum validation happens in service.

2. **Service** (`service/game_service.py :: create_player`):
   - Parse `ability_scores` dict keys to `Ability` enum, validate via `validate_point_buy()`.
   - Validate `char_class` ∈ {fighter, rogue} — raise ValueError otherwise.
   - Validate `fighting_style`: required for fighter if provided must be valid `FightingStyle`, forbidden for rogue.
   - Compute `max_hp` via `calculate_max_hp(class, level=1, con_modifier)`.
   - Get `starting_equipment(class)` → list of ref IDs → resolve via item catalog → `parse_items` with catalog.
   - Set `gold = STARTING_GOLD` (100).
   - Build player dict with computed values, pass to `parse_player` with `item_catalog`.
   - After parse, compute effective AC via `effective_ac(player)` and set `player.ac`.

3. **Item catalog access**: load catalog once per session (it's already loaded in `create_session`), store on `GameSession` or reload in `create_player`. Simplest: reload in `create_player` (same pattern as `create_session`).

## Tests First

Tests in `tests/unit/test_create_player_api.py` (or extend existing API tests):

1. **Fighter full flow**: POST create character with name, race=human, class=fighter, point buy {str:15, dex:10, con:14, int:8, wis:12, cha:8}, fighting_style=defense. Verify response: HP=12 (d10+2), gold=100, equipment includes chain_mail/longsword/shield. AC should reflect chain mail (16) + shield (+2) + defense (+1) = 19.

2. **Rogue full flow**: POST with class=rogue, point buy {str:8, dex:15, con:12, int:13, wis:10, cha:14}. Verify: HP=9 (d8+1), gold=100, equipment includes leather/rapier/shortbow/dagger. AC = leather (11+DEX cap) = 11+2=13.

3. **Invalid point buy rejected**: scores that exceed 27 points → 400 error.

4. **Score out of range rejected**: ability score 16 → 400 error.

5. **Invalid class rejected**: class=wizard → 400 error.

6. **Fighting style validation**: rogue with fighting_style → 400. Fighter without fighting_style → OK (no style selected). Fighter with invalid style → 400.

7. **Missing ability scores rejected**: request without ability_scores → 400 (field is required).

## Implementation

After tests are red:

1. Update `CreatePlayerRequest` schema — slim it down.
2. Add a `build_player_data()` function in service (or inline in `create_player`) that:
   - Validates inputs (point buy, class, fighting style)
   - Computes derived values
   - Builds the dict that `parse_player` expects
   - Passes item catalog for ref resolution
3. Update `create_player` to use the new flow.
4. Ensure `effective_ac` is called after player construction to set correct AC (the model stores AC as a field, but `effective_ac` computes it from equipment + modifiers).

Key files:
- `src/dnd_simulator/adapters/api/schemas.py`
- `src/dnd_simulator/service/game_service.py`
- `src/dnd_simulator/rules/character_creation.py` (existing, no changes expected)
- `src/dnd_simulator/content_loader/creatures.py` (may need minor adjustments)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Fighter creation returns correct HP (d10 + CON mod), AC (chain mail + shield + optional defense), gold (100), and starting equipment
- [ ] Rogue creation returns correct HP (d8 + CON mod), AC (leather + DEX), gold (100), and starting equipment
- [ ] Invalid point buy, invalid class, bad fighting style all return 400
- [ ] Old fields (hp, ac, gold, level, attacks, items) no longer accepted in request

## Status

`pending`
