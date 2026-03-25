# Sprint 003 Status

**Sprint:** 003-inventory-trading
**Phase:** 4 — Audit Refactor
**Updated:** 2026-03-25

## Current

Phase 4, Task 1: NpcRole Enum + Fix rules→layers Dependency — done. rules/ has zero imports from layers/. All role strings replaced by NpcRole enum.

## Next Steps

- Task 2: Extract NPC content tables (schedules, flavor, dialogue) from models.py to YAML

## Audit Triage

Triaged on 2026-03-25. Quick-fix: 3 applied (fail-fast params, Any→proper types in routes_player, routes_master). Sprint-relevant: 3 (→ Phase 4 refactor). Backlog: 30 added/updated.
