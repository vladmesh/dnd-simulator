# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 3 — World Assembly Backend (COMPLETE)
**Updated:** 2026-03-26

## Current

Phase 3 complete. Library catalog API, world assembly API, and fork API all working. 15 new integration tests covering all new endpoints (catalog listing, compatibility filtering, assemble, fork, error cases). E2E verified: assembled world loads in both API and frontend UI.

Ready for Phase 4 task generation.

## Next Steps

- Phase 4: World Assembly Frontend — step-by-step UI for composing worlds from library templates

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
- Compatibility is declared explicitly via `requires_geography` in metadata.yaml — no runtime ID scanning
- Old create_world/update_world/content_saver flow replaced by assemble + fork
