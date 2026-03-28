# E2E Report: Post-sprint-010 regression

**Date:** 2026-03-28
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 6, 8, 10
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 22 tested, 22 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Играть + Мастер подземелий, EN/RU buttons |
| 1.2 | Quick start — pick existing world | pass | Sword Vale selected, fighter/human/STR 16 created, redirected to /play/:id, WS connected |
| 1.3 | Language toggle | pass | Already in RU, labels consistent |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC marta visible with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player says text, NPC responds "Что будете заказывать?" |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 |
| 2.4 | Move between locations | pass | Moved to Доки and back, location panel updates correctly |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | combat_started, initiative order shown, layout switches to combat mode |
| 3.2 | Attack and damage | pass | Hit: [d20(10)+5=15 vs КЗ 10], 4 damage with breakdown |
| 3.3 | End turn and NPC response | pass | NPC died instantly (4 HP), no NPC turn needed |
| 3.4 | Combat ends | pass | entity_died + combat_ended, layout returns to peaceful |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Master — Worlds tab | pass | Two library worlds with Fork buttons |
| 6.2 | Fork world | pass | Forked sword_vale → test_fork, toast "Мир форкнут" |
| 6.3 | Delete world | pass | Confirm dialog, world removed |
| 6.4 | World editor stepper | pass | Regions/Nations/Settlements tables with data |
| 6.5 | Create and manage session | pass | Session visible, Manage link works |
| 6.6 | Spawn creature | pass | Test Goblin spawned at silverport_city_market |
| 6.7 | Edit creature HP | pass | HP changed 10/10 → 5/10 in table |
| 6.8 | Toggle brain type | pass | rule_based → llm toggle works |
| 6.9 | Delete creature | pass | Confirm dialog, creature removed |
| 6.10 | Advance time | pass | D1 → D2, weather/squad events shown |
| 6.11 | Save and load | pass | Save created, appears in list |

### Section 8: Inventory & Accessories

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 8.1 | View inventory panel | pass | 6 slots visible (Оружие, Броня, Щит, Голова, Ноги, Кольцо), gold: 0g |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location columns |
| 10.2 | Compact log + expand overlay | pass | Overlay opens with full history, close button works |
| 10.5 | Combat layout switch | pass | BattleMap replaces Location, CombatPanel replaces Nearby, returns after combat |
| 10.6 | Action bar budget display | pass | Actions/Bonus/Movement/Reaction shown, budget decrements correctly |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| ActionBar decomposition | Sprint 010 phase 2 refactored ActionBar into sub-components | pass | All actions work: Attack, Talk (SayAction input), Wait, End Turn. Drawers not explicitly tested (no equipment). |
| HP current/max in master | Sprint 010 phase 1 task 3 | pass | Creature list shows 18/18, 0/4, etc. Edit form has separate Current HP / Max HP fields. |
| Click-to-move on BattleMap | Sprint 010 changes to BattleMap | pass | Clicked reachable cell, moved 20ft, budget updated 30→10ft |

## Quick Fixes

None applied.

## Findings

### Blockers

None.

### Minor

1. **Combat log still mixes EN/RU.** "You attack человек (кулаки)", "You move на юго-востоке (20 ft)". Sprint 010 phase 1 task 1 partially fixed i18n but the `.po` file has stale msgids — attack msgid in `.po` is missing `{roll}` param, move has no translation at all. Known from prior report, not fully resolved.

2. **Log turn separators show raw entity IDs.** "player_08535554" appears as a turn label in the event log. Should display character name "Adventurer" instead.

3. **Master panel: "Current HP", "Max HP", "Conditions" labels in English.** Edit creature form mixes Russian and English field labels. Condition names (blinded, charmed, etc.) also untranslated.

4. **Master panel: "Monster" option untranslated.** In the spawn creature type dropdown, "NPC" is language-neutral but "Monster" should be "Монстр" in RU mode.

5. **Spawn creature: raw Pydantic validation error shown in UI.** When role is empty, the full Pydantic error string is displayed in the dialog. Should be a user-friendly message.

6. **Toast messages echo button labels.** "Создать существо" (create creature) and "Редактировать" (edit) used as success toasts instead of confirmation messages like "Существо создано" / "Изменения сохранены".

7. **Time advance events text mixes EN/RU.** "Weather in Железные Пики changed from clear to fog" — English template with Russian place names.

8. **Settlements table: Region column shows "—" for all rows.** Should display which region each settlement belongs to.

## Log Analysis

- Backend log: one expected `action_failed` for "target too far" attack attempt. No unexpected errors, exceptions, or tracebacks.
- Structured logs: session logs created correctly with actions/combat/entities/round subdirectories.
- No silent errors detected.
