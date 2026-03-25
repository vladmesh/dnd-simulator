# Task: Extract NPC Content Tables to YAML

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 4 — Audit Refactor

## Description

Move ~130 lines of hardcoded game content from `layers/entities/models.py` to YAML data files under `content/`. This covers:
- `DEFAULT_SCHEDULE_TEMPLATES` — default daily schedules by role
- `ACTIVITY_FLAVOR` — flavor text for what NPCs look like doing
- `CANNED_DIALOGUE` — rule-brain dialogue lines by role+activity
- `MOOD_DIALOGUE` — mood-override dialogue lines

The lookup functions (`resolve_schedule`, `activity_flavor`, `canned_line`) stay in Python but read from loaded data instead of inline dicts.

## Tests First

- Loading NPC content YAML produces schedule templates with correct structure (role → list of (start, end, activity, location_label) tuples)
- `resolve_schedule("blacksmith", "town")` returns the same entries whether loaded from YAML or the current hardcoded dict
- `activity_flavor(NpcRole.GUARD, NpcActivity.WORKING)` returns "standing watch" from YAML data
- `canned_line(NpcRole.MERCHANT, NpcActivity.WORKING, [])` returns the merchant working line from YAML data
- Mood overrides still take priority: `canned_line(NpcRole.MERCHANT, NpcActivity.WORKING, ["angry"])` returns the angry override
- Missing YAML file raises a clear error (fail-fast, no silent fallback)

## Implementation

1. Create `content/npc_behaviors.yaml` with schedules, flavor, dialogue, mood overrides
2. Add a loader function (in `content_loader.py` or a new `content/npc_behaviors.py`) that parses the YAML into the same data structures
3. Load at module init or on first access — fail hard if file missing
4. Remove the inline dicts from `models.py`, replace with loaded data
5. Keep `resolve_schedule`, `activity_flavor`, `canned_line` functions — just change their data source

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `DEFAULT_SCHEDULE_TEMPLATES`, `ACTIVITY_FLAVOR`, `CANNED_DIALOGUE`, `MOOD_DIALOGUE` no longer defined in models.py
- [ ] YAML file exists at `content/npc_behaviors.yaml` with all content
- [ ] Game still works with loaded data (existing NPC tests pass)

## Status

`done`

## Developer Notes

Extracted schedules and activity flavor text (~80 lines) to `content/npc_behaviors.yaml`. Dialogue (CANNED_DIALOGUE, MOOD_DIALOGUE) kept in Python because it uses `_()` for i18n — `pygettext3` only scans `.py` files, so moving to YAML would break string extraction.

New module `layers/entities/npc_behaviors.py` loads YAML lazily on first access, fails hard if file missing. The lookup functions (`resolve_schedule`, `activity_flavor`) unchanged in signature — they now delegate to the loader internally.

`DEFAULT_SCHEDULE_TEMPLATES` and `ACTIVITY_FLAVOR` removed from `models.py` and `__init__.py` exports.
