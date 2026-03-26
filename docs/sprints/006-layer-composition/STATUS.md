# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 4 — World Assembly Frontend
**Updated:** 2026-03-26

## Current

Phase 4, Task 1: World Builder Wizard Component — done. Wizard component, API client methods, TS types, i18n strings (en+ru) all implemented. Frontend builds clean.

## Next Steps

- Task 1: World Builder Wizard Component — API client methods, TS types, multi-step wizard for layer selection
- Task 2: Wire into SetupScreen + E2E — integrate wizard into setup flow, i18n, integration tests

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
- Compatibility is declared explicitly via `requires_geography` in metadata.yaml — no runtime ID scanning
- Old create_world/update_world/content_saver flow replaced by assemble + fork
- WorldBuilder wizard is an alternative mode alongside existing WorldPicker ("quick start" vs "custom world")
