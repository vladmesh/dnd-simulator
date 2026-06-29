# E2E Report: sprint020-phase1

**Date:** 2026-06-30
**Flags:** --no-llm
**Sections tested:** 1, 2.1, 2.2, 2.4, 3.5, 4.1, 10.6, 13 (accessory save/load), 14.1
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 15 tested, 13 passed, 1 failed, 1 partial
- Quick fixes: 1 applied
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Fighter char creation (Долина Мечей, Defense style) | pass | AC 19 (Chain Mail 16 + Shield 2 + Defense 1) ✓ |
| 1.2 | Paladin char creation (level_up_test world) | pass | HP 12, AC 18, no Fighting Style selector at L1 ✓ |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | lira visible in Доки Серебропорта, RU labels ✓ |
| 2.2 | Talk to NPC | pass | "Ты говоришь: «Привет»" / "человек говорит: «Тихая ночка, а?»" in RU ✓ |
| 2.4 | Move between locations | pass | Солёный Якорь → Доки Серебропорта, location/NPCs updated ✓ |

Note: "Silent travel" fix (task 2) was about error return when destination is unreachable, not adding log messages for successful travel.

### Section 3: Level-Up Flow

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.5a | XP granted after kill | pass | "Ты получаешь 500 опыта за победу над человек" in RU ✓ |
| 3.5b | Level-up modal auto-opens | pass | Correct preview: HP+8, 2 spell slots, Fighting Style dropdown ✓ |
| 3.5c | Close modal → "Повысить уровень" button persists | pass | Modal deferred correctly ✓ |
| 3.5d | Reopen modal via "Повысить уровень" | pass | Modal reopened with same content ✓ |
| 3.5e | Select fighting style → OK enables | pass | "Дуэлянт" selected, OK unlocked ✓ |
| 3.5f | Confirm level-up via OK | fail | 400 Bad Request — see Findings |

### Section 4: Fighter Class Features

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 4.1 | Second Wind in combat | pass | "Второе дыхание" fired; Бонус: 1→0; pool button disappeared ✓ |

### Section 10: Combat Mechanics

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.6 | Action budget display | pass | "Действия: 1 / Бонус: 1 / Движение: 30фт / Реакция: 1" ✓ |

### Section 13: Accessories

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 13.1 | Equip Ring of Protection via API | pass | AC 19→20; "Ты экипируешь Ring of Protection" in RU ✓ |
| 13.2 | Save/load round-trip preserves accessory modifier | pass | Save "ring_test" → load → AC 20 preserved ✓ |

### Section 14: Paladin Class Features

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 14.1 | lay_on_hands icon renders in action bar | pass | Icon (gear/⚙) visible in action bar with "1" badge ✓ — task 2 fix verified |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Ring equip KeyError fix | Equip ring → `_perceive_equip` used `d["weapon_name"]` for all slots | fixed | Unified to `"item_name"` in perception.py and handlers/equipment.py |
| HTTP 404 for missing session | Task 2 HTTP status fix | pass | `GET /api/player/sessions/no_such_session/status` → 404 ✓ |
| HTTP 400 for invalid level-up | Task 2 HTTP status fix | pass | No-op pending level-up → 400 ✓ |
| Defense Fighting Style AC | Task 1 area — starting equipment | pass | AC 19 = Chain Mail 16 + Shield 2 + Defense +1 ✓ |
| Unequip action bar i18n | Unequip actions grouped under count badge | partial | "unequip_armor"/"unequip_shield" raw IDs; descriptions in English — see Findings |

## Quick Fixes

- **`_perceive_equip`/`_perceive_unequip` KeyError** (`layers/entities/perception.py:350-370`): The handlers read `d["weapon_name"]` for all equip events, but slot-specific events used per-slot keys (`ring_name`, `armor_name`, etc.). Fixed by unifying all equip/unequip event data to `"item_name"` in `rules/handlers/equipment.py:127,147` and updating perception handlers and `tests/unit/test_perception.py:514`.

## Findings

### Blockers
None.

### Major (pre-existing, not phase 1 regressions)

**1. Level-up fails (400) when session evicted between XP gain and API call**

When the player navigates from character creation to `/play`, the WS connection drops briefly. This triggers `_on_session_empty` → autosave to disk → `_sessions.pop`. The WS coroutine that handles the round loop retains a reference to the old (evicted) session object, while subsequent HTTP API calls (`level-up`, `/status`) reload from disk (old state: experience=0, `level_up_available=False`). The level-up POST returns 400 "No level-up available" even though the in-WS session has the XP and `level_up_available=True`.

Root cause: two live session objects for the same session_id after eviction (WS coroutine holds stale ref; HTTP uses freshly loaded copy). Affects any REST call made after an eviction event within an active combat or XP-gain sequence.

**2. Unequip sub-buttons show raw action IDs and English descriptions**

Unequip actions are grouped under a badge-count button (showing number of currently equipped slots). When expanded:
- Weapon unequip: label "Снять" (RU ✓), description "Put away your equipped weapon. You will fight with fists." (EN ✗)
- Armor unequip: label "unequip_armor" (raw ID ✗), description "Remove your equipped armor." (EN ✗)
- Shield unequip: label "unequip_shield" (raw ID ✗), description "Remove your equipped shield." (EN ✗)

Only the weapon unequip label is translated; armor/shield labels fall back to action type IDs.

### Minor (pre-existing)

**3. Second Wind shows "восстанавливаешь 0 ОЗ" when at full HP**

The log entry always shows the heal amount even when it's 0 (player already at max HP). UX improvement: suppress the message or show "ты уже в полном здравии" when no actual heal occurs.

## Log Analysis

- One backend error from session `4bc01521` (ring equip test): `KeyError: 'weapon_name'` in `_perceive_equip` — fixed during this E2E run.
- No errors in the two primary E2E sessions (`46e8cca3`, `86617286`).
- Session eviction (`session_empty_evict`) fires within ~5 seconds of WS reconnection even when a listener is active — possible timer/async race in session teardown path.
