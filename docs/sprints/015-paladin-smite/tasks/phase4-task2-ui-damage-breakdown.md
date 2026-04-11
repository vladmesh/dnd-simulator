# Task: UI Damage Type Breakdown Polish

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 4 — Multi-Damage Weapons + UI Breakdown

## Description

Polish the frontend damage breakdown to visually distinguish damage types at the component card level, not just individual dice. Currently `DamageComponentRow` in `AttackCardModal.tsx` uses generic `border-border/20 bg-muted/30` for all non-crit cards. With multi-damage weapons, two "weapon" cards sit side-by-side looking identical except for a small type label. Apply damage-type coloring to the card border/background (using existing `DAMAGE_TYPE_COLORS` from `DiceVisual.tsx`) so the damage breakdown is visually scannable.

Key files:
- `frontend/src/components/game/DiceVisual.tsx` — `DAMAGE_TYPE_COLORS` map (all 13 types)
- `frontend/src/components/game/AttackCardModal.tsx` — `DamageComponentRow` (line 269)
- `frontend/src/i18n/locales/{en,ru}/game.json` — `dmg_*` keys (all 13, both languages)

## Tests First

1. **Component card renders type color**: `DamageComponentRow` with `type: "fire"` renders with fire-colored border/background classes (not generic `border-border/20`).

2. **Multiple components show different colors**: Render a `DamageSection` with slashing + fire components — verify visually distinct card styling (red-tinted for slashing, orange-tinted for fire).

3. **Crit component keeps sky highlight**: A crit component (`source: "weapon_crit"`) should keep its sky-blue styling regardless of damage type — crit indication takes priority.

4. **Unknown damage type falls back gracefully**: A component with an unrecognized type gets default styling (no crash, no broken CSS).

## Implementation

1. Export `DAMAGE_TYPE_COLORS` from `DiceVisual.tsx` (or extract to a shared `damageColors.ts` util) so `AttackCardModal.tsx` can import it.

2. In `DamageComponentRow`, apply damage-type coloring to the component card border/background. Use a softer version than the die colors — the card wraps multiple dice, so the color should be subtle (lower opacity on border/bg). Crit styling (`border-sky-400/40 bg-sky-950/20`) takes priority over damage-type styling.

3. Verify visually with the dev server: start a combat with a Paladin wielding a flaming longsword, attack, and confirm the damage breakdown shows distinct colored cards per damage type.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Damage component cards colored by damage type (fire=orange, cold=blue, etc.)
- [ ] Crit cards keep sky-blue styling (priority over damage type)
- [ ] Visual verification in browser with multi-damage weapon attack

## Status

`pending`
