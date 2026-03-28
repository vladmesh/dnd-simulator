# Task: Extract co-located components to own files

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 2 — ActionBar Decomposition

## Description

Move ActionDrawer, TargetDropdown, DirectionalDropdown, and utility functions out of ActionBar.tsx into their own files under `components/game/action-bar/`. Pure file extraction — no behavior change, no DOM change.

Target structure:
```
components/game/action-bar/
  utils.ts              — hasParam, getActionLabel, isCostDepleted, getButtonVariant, getCostTypeClass
  ActionDrawer.tsx       — generic drawer shell (button + popup)
  TargetDropdown.tsx     — single/multi-target action dropdown
  DirectionalDropdown.tsx — toward/away directional dropdown
```

ActionBar.tsx imports from these new files instead of defining them inline. Shared types (DropdownProps, etc.) move to the new files or a shared types file.

## Tests First

No new tests needed — this is a pure extraction. The verification is:

- All existing ActionBar.test.tsx tests pass without modification
- `make check` green
- No runtime behavior change (same DOM, same data attributes, same event handling)

If any test breaks, it means the extraction changed something it shouldn't have.

## Implementation

1. Create `components/game/action-bar/` directory
2. Move utility functions to `action-bar/utils.ts`, export them
3. Move `ActionDrawer` component + its props interface to `action-bar/ActionDrawer.tsx`
4. Move `TargetDropdown` + `DirectionalDropdown` + their prop interfaces to own files
5. Update ActionBar.tsx imports to reference the new files
6. Add barrel `action-bar/index.ts` if it helps keep imports clean
7. Verify `make check` passes

## Acceptance Criteria

- [ ] Tests written and RED (before implementation) — N/A, pure extraction
- [ ] All existing ActionBar.test.tsx tests pass unchanged
- [ ] `make check` green
- [ ] ActionDrawer, TargetDropdown, DirectionalDropdown each in own file < 150 lines
- [ ] Utility functions in own file
- [ ] ActionBar.tsx no longer defines any sub-components — only imports them

## Status

`done`

## Developer Notes

Pure file extraction. ActionDrawer (39 lines), TargetDropdown (62 lines), DirectionalDropdown (62 lines), utils (38 lines) — all under `action-bar/`. ActionBar.tsx dropped from 536 → 346 lines. No barrel index needed — direct imports are cleaner with 4 files. All 20 existing tests pass unchanged. No DOM changes.
