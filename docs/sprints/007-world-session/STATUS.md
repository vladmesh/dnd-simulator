# Sprint 007 Status

**Sprint:** 007-world-session
**Phase:** 5 — Partial Worlds + World Management API (PLANNED)
**Updated:** 2026-03-26

## Current

Phase 5 tasks generated. Ready to start task 1.

## Next Steps

- Task 1: Partial manifest support — `resolve_manifest()` handles missing layers, `complete` flag in list_worlds, `create_empty_world` endpoint
- Task 2: World fork + delete — fork world with optional layer truncation, delete with safety checks, `LAYER_ORDER` constant
- Task 3: Layer scaffold — create minimal valid custom layers from scratch, full pipeline test

## Audit Triage

Triaged on 2026-03-26. Quick-fix: 2 applied (session.py `Any→object`, routes_ws.py JSON error handling). Sprint-relevant: 0. Backlog: 8 added (6 already tracked, 2 new test-gap items).
