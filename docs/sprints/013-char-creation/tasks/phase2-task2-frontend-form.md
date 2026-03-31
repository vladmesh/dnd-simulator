# Task: Frontend — Point Buy UI + Fighting Style + Preview

**Date:** 2026-04-01
**Sprint:** 013-char-creation
**Phase:** 2 — Creation API + Frontend Form

## Description

Rewrite `CharacterForm.tsx` to match the new backend: no manual HP/AC/gold/level, point buy ability scores with interactive +/- controls, fighting style selector for fighters, and a preview panel showing derived stats before submit.

Changes:

1. **Remove fields**: level, hp, ac, gold (server computes these).
2. **Restrict classes**: only `fighter` and `rogue` in dropdown.
3. **Point buy UI**: replace plain number inputs with +/- stepper buttons per ability. Show: current score, modifier (e.g. "+2"), cost. Show remaining points out of 27. Range 8-15 per score. Disable +/- at boundaries. Use D&D 5e cost table: {8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9}.
4. **Fighting style selector**: visible only when class=fighter. Dropdown with Defense, Dueling, Great Weapon Fighting. Optional (fighter can have no style? — actually per D&D 5e L1 fighter gets one, so make it required for fighter).
5. **Preview panel**: below ability scores, before submit. Client-side calculation:
   - HP: `HIT_DIE[class] + floor((con - 10) / 2)`, min 1. Hit die: fighter=10, rogue=8.
   - AC: fighter → chain mail (16) + shield (+2) = 18, +1 if defense style = 19. Rogue → leather (11) + DEX mod (capped at none for light armor) = 11 + DEX mod.
   - Starting equipment: text list per class.
   - Gold: 100.
6. **Update Zod schema**: match new `CreatePlayerRequest` — drop old fields, add fighting_style.
7. **Update API types** (`types/api.ts`): `CreatePlayerRequest` matches backend.
8. **i18n**: add keys for new UI elements (remaining points, modifier, fighting styles, preview labels, equipment names).

## Tests First

Frontend tests in `tests/frontend/` (Vitest + Testing Library):

1. **Point buy interaction**: render form, click STR +, verify score goes from 10→11, remaining points decrease by 1. Click STR + up to 15, verify + button disabled. Click STR - down to 8, verify - button disabled.

2. **Point buy budget enforcement**: set all scores to use exactly 27 points ({15,15,15,8,8,8} = 27), verify no more + buttons work.

3. **Fighting style visibility**: select fighter → fighting style dropdown visible. Select rogue → dropdown hidden.

4. **Preview updates**: set class=fighter, CON=14 → preview shows HP 12, AC 18. Switch to rogue, CON=12 → preview shows HP 9, AC 13 (with DEX=10+2 default... depends on DEX score).

5. **Form submission payload**: submit form, verify API call payload matches new schema (no hp/ac/gold/level, has ability_scores + fighting_style).

## Implementation

After tests are red:

1. Define point buy cost table and helper functions (remaining points, modifier calc) as pure TS functions.
2. Build `AbilityScoreInput` sub-component: score display, +/- buttons, modifier badge, cost display.
3. Build `PointBuyPanel`: 6 × `AbilityScoreInput` + remaining points counter.
4. Build `FightingStyleSelect`: conditional on class=fighter.
5. Build `CreationPreview`: computed HP, AC, equipment list, gold.
6. Rewrite `CharacterForm` composing the above.
7. Update Zod schema, API types, i18n files (en + ru).

Key files:
- `frontend/src/components/setup/CharacterForm.tsx` (rewrite)
- `frontend/src/types/api.ts` (update CreatePlayerRequest)
- `frontend/src/i18n/locales/en/setup.json` (new keys)
- `frontend/src/i18n/locales/ru/setup.json` (new keys)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Point buy: +/- buttons work, budget enforced, scores clamped 8-15
- [ ] Fighting style appears for fighter only
- [ ] Preview shows correct HP, AC, equipment, gold — updates live
- [ ] No level/hp/ac/gold input fields remain
- [ ] Only fighter and rogue available as class choices
- [ ] Form submits new slim payload matching backend schema

## Status

`pending`
