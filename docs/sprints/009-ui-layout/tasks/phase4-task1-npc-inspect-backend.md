# Task: NPC Description Field + Structured Inspect Data

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 4 — NPC Inspect Card

## Description

Add a `description` localized field to NPC content models and YAML, and expose structured NPC data for the inspect action. Currently inspect sends a text log event via `_perceive_inspect()` — instead, the backend should return structured data the frontend can render in a modal card.

**Design constraint: all inspect data flows through `AwarenessBuilder`, not via a separate endpoint or direct entity read.** This ensures a single choke point for future perception-based filtering (e.g. perception checks gate how much info the player sees, conversation history unlocks name, etc.). Today we send all fields; tomorrow AwarenessBuilder filters them based on knowledge/perception — frontend code stays unchanged.

Changes:

1. **Content model:** Add `description: LocalizedText = {}` to `NpcContent` in `schemas.py`
2. **Runtime model:** Add `description: str = ""` to `Npc` in `entities/models.py`
3. **Monster model:** Add `description: str = ""` to `MonsterTemplate` in `core/monster.py`
4. **Content loader:** Wire description from YAML → Npc during assembly
5. **YAML content:** Add descriptions to all existing NPCs (sword_vale library + test_vale)
6. **Awareness:** Enrich `NearbyEntity` with structured fields: `name`, `race`, `role`, `faction_id`, `npc_description`, `is_merchant`. The current `description` field (perceive output) stays as-is for the compact Nearby panel display. All fields populated in `AwarenessBuilder.build_nearby_entities()` — the single point where future perception gating will be added.
7. **No separate inspect endpoint.** The frontend gets all the data it needs from the enriched `NearbyEntity` in the awareness payload. Clicking "inspect" opens a modal client-side from data already received — no additional server round-trip needed.

## Tests First

- An NPC loaded from YAML with `description` field has that description accessible on the runtime `Npc` object
- An NPC without `description` in YAML gets empty string (backward compat)
- `build_nearby_entities()` returns `NearbyEntity` with the new structured fields populated from the Npc data
- Spawned monsters from `MonsterTemplate` with description carry it through to the creature
- Enriched `NearbyEntity` for a merchant has `is_merchant: true`
- Enriched `NearbyEntity` in combat includes hp/max_hp (via `CombatEntity` or equivalent)

## Implementation

- `NpcContent` in `content_loader/schemas.py`: add `description: LocalizedText = {}`
- `Npc` in `layers/entities/models.py`: add `description: str = ""`
- `MonsterTemplate` in `core/monster.py`: add `description: str = ""`
- Content loader assembly (`content_loader/assembly.py` or wherever NpcContent → Npc happens): pass description through
- `NearbyEntity` in `core/awareness.py`: add optional fields `name: str = ""`, `race: str = ""`, `role: str = ""`, `faction_id: str = ""`, `npc_description: str = ""`, `is_merchant: bool = False`
- `AwarenessBuilder.build_nearby_entities()`: populate the new fields from the entity — this is the single choke point for future perception gating
- Remove or simplify the old `idle` + `inspect_target` action handler — no longer needed since inspect is now client-side from awareness data
- YAML: add `description` to sword_vale NPCs (Edgar, Marta, etc.)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] NPC descriptions visible in YAML and loaded at runtime
- [ ] NearbyEntity carries structured NPC metadata
- [ ] Inspect returns structured data for frontend modal rendering

## Status

`pending`
