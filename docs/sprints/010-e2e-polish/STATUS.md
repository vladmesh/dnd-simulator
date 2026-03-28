# Sprint 010 Status

**Sprint:** 010-e2e-polish
**Phase:** 2 — ActionBar Decomposition
**Updated:** 2026-03-28

## Current

Phase 2 tasks generated. ActionBar.tsx (536 lines) → decompose into subcomponents under `components/game/action-bar/`. Three tasks: extract co-located components, extract drawer sections, extract ActionButton + finalize orchestration. Target: ActionBar.tsx < 150 lines, each subcomponent < 150 lines, visually identical, all tests green.

## Next Steps

- Task 1: Extract ActionDrawer, TargetDropdown, DirectionalDropdown, utils to own files
- Task 2: Extract ConsumableDrawer, ClassFeatureDrawer, InventoryDrawer
- Task 3: Extract ActionButton + SayAction, slim ActionBar to orchestration
