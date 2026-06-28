# Task: Hide Attack/Talk actions on corpses

**Date:** 2026-06-29
**Sprint:** 019-control-plane-prep
**Phase:** 3 — Visible gaps + backlog reconcile + dead code

## Description

`corpse-nearby-actions` (backlog bug). Out of combat, a dead creature still surfaces in the Nearby panel with Attack / Talk / Inspect buttons. The backend deliberately keeps corpses in the `nearby` list so they can be looted — `awareness_builder.py:256-263` includes them when `is_lootable(e)` is true and sets `lootable=True` on the `NearbyEntity`. Looting goes through the separate `LootPanel`. Attacking a corpse returns a correct "already dead" result so nothing breaks, but Attack/Talk on a corpse are meaningless.

Fix is **frontend-only**: in `frontend/src/components/game/Perception.tsx`, hide the Attack and Talk buttons for entities where `entity.lootable === true`. The `NearbyEntity` type already carries `lootable?: boolean` (`frontend/src/types/game.ts:95`), so no backend/schema change is needed. Inspect can stay (inspecting a corpse is harmless and consistent with the loot card). `lootable` also covers open containers (chests), which likewise shouldn't show Attack/Talk — gating on `lootable` is correct for both.

The Attack/Talk block only renders when `isMyTurn`; keep that guard, just add the `!lootable` condition on top.

## Tests First

Vitest component test for `Perception` (mirror the existing `frontend/src/components/game/__tests__/` patterns — stub the game store `awareness`/`mode`/`isMyTurn`).

- **Corpse shows no Attack/Talk.** Render with one nearby entity `{ id, description, lootable: true }`, `isMyTurn: true`, non-combat mode. Assert the Attack button and the Talk button are absent. (Inspect button may remain.)
- **Living entity still shows Attack/Talk.** Render with one nearby entity `{ id, description, lootable: false }` (or `lootable` undefined), `isMyTurn: true`, non-combat mode. Assert both Attack and Talk buttons are present (regression guard so we don't hide actions on the living).

## Implementation

- `Perception.tsx`: wrap the Attack `<Button>` (and the non-combat Talk `<Button>`) so they only render when `!entity.lootable`. Simplest: compute `const canAct = isMyTurn && !entity.lootable` and gate the action row's interactive buttons on it, or add `{!entity.lootable && ...}` around the Attack/Talk buttons specifically.
- Don't touch the loot flow or `LootPanel`. Don't change the backend `nearby` payload.

## Acceptance Criteria

- [ ] Tests written and RED (corpse test fails before the fix)
- [ ] Attack/Talk hidden for `lootable` nearby entities; shown for living ones
- [ ] Tests GREEN
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Frontend-only as planned. In `Perception.tsx` gated the Attack `<Button>` on `!entity.lootable` and the Talk `<Button>` on `!isCombat && !entity.lootable`. Inspect button left untouched (harmless on corpses/containers, consistent with the loot card). No backend/schema/type change — `NearbyEntity.lootable?: boolean` already existed.

New test file `frontend/src/components/game/__tests__/Perception.test.tsx` (2 tests): corpse (`lootable: true`) hides both buttons; living (`lootable: false`) shows both. Stubs `wsClient` and seeds the game store (`mode: explore`, `isMyTurn: true`, awareness with one nearby entity). RED confirmed before the fix (Attack present on corpse), GREEN after. `make check` green: backend 2278, frontend 240.
