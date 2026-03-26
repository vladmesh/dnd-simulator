# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 4 — World Assembly Frontend
**Updated:** 2026-03-26

## Current

Phase 4, Tasks 1+2 done. WorldBuilder wizard component with API client, TS types, i18n (en+ru), SetupScreen wiring, and integration tests all complete. Frontend builds clean. All backend tests pass (1172/1172).

## Next Steps

- All tasks in Phase 4 are done. Ready to close phase.

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
- Compatibility is declared explicitly via `requires_geography` in metadata.yaml — no runtime ID scanning
- Old create_world/update_world/content_saver flow replaced by assemble + fork
- WorldBuilder wizard is an alternative mode alongside existing WorldPicker ("quick start" vs "custom world")
