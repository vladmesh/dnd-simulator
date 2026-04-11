# Task: Fix 26 pre-existing frontend test failures

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 1 — Bug Sweep

## Description

26 frontend tests fail due to two unrelated issues introduced in prior sprints:

### A) CharacterForm mock missing `getSetupConfig` (25 tests)

Commit 22f2063 added `api.player.getSetupConfig()` call in `CharacterForm.tsx:91`, but the test mock in `CharacterForm.test.tsx:8-14` only mocks `createCharacter`. All 24 CharacterForm tests + 1 SetupScreen test crash with `api.player.getSetupConfig is not a function`.

Fix: add `getSetupConfig` to the mock, returning `{ starting_gold: 1000, point_buy_budget: 27 }`.

### B) Depleted spell slots not shown in smite panel (1 test)

`ActionButton.test.tsx:430` — "depleted spell slots are shown but disabled" fails because `getSpellSlots()` in `SmiteChoice.tsx:15` filters out pools with `current_uses === 0`. When all slots are depleted, `hasSmiteOption` is false and the smite panel never renders.

Fix: split `getSpellSlots()` into two concerns — filtering for display (include depleted) vs filtering for usability (only non-depleted are clickable). Or pass all slots and mark depleted ones as disabled in the UI.

## Tests First

These ARE the tests — they already exist and fail. Goal is to make them GREEN.

## Implementation

### A) CharacterForm mock
In `frontend/src/components/setup/__tests__/CharacterForm.test.tsx`, update mock:
```typescript
vi.mock("@/transport/apiClient", () => ({
  api: {
    player: {
      getSetupConfig: vi.fn().mockResolvedValue({
        starting_gold: 1000,
        point_buy_budget: 27,
        available_classes: ["fighter", "rogue", "paladin"],
        available_races: ["human", "elf", "dwarf", "halfling"],
      }),
      createCharacter: vi.fn(),
    },
  },
}))
```

Check SetupScreen.test.tsx for same issue.

### B) Depleted smite slots
In `SmiteChoice.tsx`: change `getSpellSlots()` to not filter by current_uses. In the TargetDropdown rendering, mark depleted slots with `disabled` attribute. Update SmiteChoice component to accept and render disabled slots.

## Acceptance Criteria

- [ ] All 26 previously failing frontend tests pass
- [ ] `make check` frontend section green (or no new failures)
- [ ] Depleted spell slots shown but disabled in smite choice panel

## Status

`done`

## Developer Notes

Three fixes applied:

**A) CharacterForm mock (25 tests):** Added `getSetupConfig` mock returning `{ starting_gold: 100, point_buy_budget: 27 }` to both `CharacterForm.test.tsx` and `SetupScreen.test.tsx`. The SetupScreen test also needed the mock because it renders CharacterForm which calls `getSetupConfig` in useEffect.

**B) "does not include level, hp, ac, gold in payload" test:** This test was already broken (crashed on missing mock before reaching submit). After fixing the mock, it failed because it submits a fighter without selecting a fighting style — form validation blocks the submit. Added `selectOptions("defense")` before clicking submit.

**C) Depleted spell slots (1 test):** `getSpellSlots()` in `SmiteChoice.tsx` filtered out pools with `current_uses === 0`, so depleted slots never reached the UI. Removed the filter — now all spell slot pools are returned. Updated both `SmiteChoice` component and `TargetDropdown` inline smite panel to render depleted slots with `disabled` attribute and `opacity-50` styling instead of hiding them.
