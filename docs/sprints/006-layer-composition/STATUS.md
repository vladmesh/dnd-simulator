# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 4 — World Assembly Frontend (COMPLETE)
**Updated:** 2026-03-26

## Current

Phase 4 complete. WorldBuilder wizard component with 6-step flow (5 layer selections + details), API client methods, TypeScript types, i18n (en+ru), and SetupScreen integration. 2 new integration tests, E2E verified via Playwright — full flow works: build world -> create character -> play.

All phases complete. Ready for sprint closure.

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
- Compatibility is declared explicitly via `requires_geography` in metadata.yaml — no runtime ID scanning
- Old create_world/update_world/content_saver flow replaced by assemble + fork
- WorldBuilder wizard is an alternative mode alongside existing WorldPicker ("quick start" vs "custom world")

## Audit Triage

Triaged on 2026-03-26. Quick-fix: 0 applied. Sprint-relevant: 0. Backlog: 0 new (existing backlog items unchanged).
