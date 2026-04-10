# Task: Reputation in Awareness, Perception & Frontend

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 3 — Reputation Dynamics + Auto-hostility

## Description

Three connected pieces that make reputation visible to brains and players:

1. **Awareness** — expose faction name and relation in `NearbyEntity` so LLM/rule brains can make reputation-informed decisions (e.g. "this creature is hostile to you because of your low reputation with their faction").
2. **Perception** — add `_perceive_reputation_change` handler so reputation events become human-readable log entries.
3. **Frontend** — add `reputation_changed` to `EventType`, `EVENT_ICONS`, `EVENT_COLORS`, and the test coverage lists.

## Tests First

### Awareness tests (extend `tests/unit/test_awareness.py` or awareness_builder tests):

1. **NearbyEntity includes faction and relation.** Observer sees a bandit. Awareness shows `faction_name: "Bandits"` and `relation: "hostile"`.
2. **Relation reflects personal reputation override.** Observer has personal rep 90 with bandits. NearbyEntity shows `relation: "friendly"` despite faction-level hostility.
3. **Factionless creature shows no faction info.** No faction_name, relation defaults to "neutral".

### Perception tests (extend `tests/unit/test_perception.py`):

4. **REPUTATION_CHANGED event produces readable description.** Event with `{entity_id, faction_id, old_rep: 80, new_rep: 60, delta: -20, reason: "kill"}` → "Your reputation with Bandits decreased (80 → 60)." (or similar).
5. **Other observers see a different message.** Non-involved observer sees: "{Name}'s reputation with Bandits changed."

### Frontend tests (extend `frontend/src/lib/__tests__/logProcessing.test.ts`):

6. **EVENT_ICONS and EVENT_COLORS have `reputation_changed` entry.** Existing test checks all EventType values have mappings — adding the new type to the list is sufficient.

## Implementation

1. **NearbyEntity** (`layers/entities/awareness.py` dataclass): add optional `faction_name: str = ""` and `relation: str = ""` fields.
2. **AwarenessBuilder** (`layers/entities/awareness_builder.py`): in `build_nearby_entities`, populate `faction_name` via `_resolve_faction_name()` (already exists) and `relation` via `check_faction_hostility` result mapped to a string.
3. **Perception** (`layers/entities/perception.py`): add `_perceive_reputation_change(event, observer, get_entity)` handler. Use `_()` for i18n. Register in the dispatch dict.
4. **Frontend types** (`frontend/src/types/game.ts`): add `"reputation_changed"` to `EventType` union.
5. **Frontend logProcessing** (`frontend/src/lib/logProcessing.ts`): add icon (e.g. `"trending-down"` or `"shield-alert"`) and color (e.g. `"text-yellow-400"`) for `reputation_changed`.
6. **Frontend tests**: add `"reputation_changed"` to the `ALL_EVENT_TYPES` arrays in logProcessing tests.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] NearbyEntity exposes faction name and relation string
- [ ] Reputation change events produce localized descriptions
- [ ] Frontend renders reputation events with icon and color
- [ ] `make check` passes (includes frontend tests)

## Status

`pending`
