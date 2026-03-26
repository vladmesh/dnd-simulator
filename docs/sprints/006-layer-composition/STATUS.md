# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 1 — Library Structure + Manifest + Content Migration
**Updated:** 2026-03-26

## Current

Phase 1 tasks generated. Ready to start task 1.

## Next Steps

- Task 1: Create library structure, extract sword_vale's 5 layers as templates, split settlements from regions.yaml
- Task 2: Define manifest format, convert sword_vale to manifest, create test_vale (all-custom), delete old worlds

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
