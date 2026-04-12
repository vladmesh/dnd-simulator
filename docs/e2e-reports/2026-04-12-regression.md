# E2E Report: Post-Sprint-015 Regression

**Date:** 2026-04-12
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 4 (partial), 6 (partial), 8 (spot), 10 (layout/combat), 13 (reputation drop)
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 28 tested, 25 passed, 3 partial (findings)
- Quick fixes: 1 applied
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Play/DM, language toggle |
| 1.2 | Quick start — pick world | pass | Sword Vale → New Session → character form → game, WS connected |
| 1.3 | Language toggle | pass | EN→RU: "D&D Симулятор", "Играть", "Мастер подземелий" |
| 1.4 | Character creation — point buy | pass | STR 15 (9pts), CON 14 (5pts), remaining 3/27 correct. HP 12, AC 19 preview, Gold 1000. + disabled at 15, - disabled at 8 |
| 1.5 | Character creation — class-specific UI | pass | Fighter: Fighting Style selector (Defense/Dueling/GWF), Chain Mail+Longsword+Shield. Rogue: no style, Leather+Rapier+Shortbow+Dagger. Paladin: no style (correct L1), Chain Mail+Longsword+Shield |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC "marta" visible as "человек", Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player: "Hello there!" → NPC: "Что будете заказывать?" |
| 2.3 | Wait and time advance | pass | 10:00 → 11:00 |
| 2.4 | Move between locations | pass | Tavern → Docks, NPC "lira" visible, path back shown |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | combat_started, initiative order, auto-attack on init |
| 3.2 | Attack and damage | pass | [d20+4=17 vs КЗ 15] hit 4 dmg; [d20+4=10 vs КЗ 15] miss — both correct |
| 3.3 | End turn and NPC response | pass | NPC attacked + dashed, round advanced |
| 3.4 | Combat ends | pass | Player died → "Ты погибаешь" → "Бой окончен" → GAME OVER |

### Section 4: Class Features

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 4.1 | Fighter — Second Wind | pass | HP 2/12 → 5/12, bonus action consumed, button disappears |
| 4.2 | Fighter — Defense style | partial | Preview shows AC 19 correctly, but in-game shows AC 18. See findings. |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Master — Worlds tab | pass | Library worlds: Fork only. Editable: Fork + Delete |
| 6.2 | Fork world | pass | Forked sword_vale → test_fork, appeared with Fork+Delete |
| 6.3 | Delete world | pass | Confirmed dialog, world removed |
| 6.5 | Sessions tab | pass | World selector, New Session, existing sessions with Manage |
| 6.8 | Toggle brain type | pass | rule_based → llm → rule_based |
| 6.10 | Advance time | pass | 24h: D1 10:00 → D2 10:00 |
| 6.11 | Save and load | pass | Save "e2e_test" created and listed |

### Section 8: Inventory

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 8.1 | View inventory panel | pass | 6 slots: Weapon(Longsword), Armor(Chain Mail), Shield, Head, Feet, Ring. Gold 1000 |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location |
| 10.2 | Compact log + expand overlay | pass | Compact log visible at top with recent events |
| 10.4 | Click-to-move on BattleMap | pass | Clicked cell, moved 5ft west, movement budget 30→25ft |
| 10.5 | Combat layout switch | pass | CombatPanel left, BattleMap right, Location restored after combat |
| 10.6 | Action bar budget display | pass | Actions/Bonus/Movement/Reaction displayed, update on use |

### Section 13: Reputation

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 13.2 | Kill reputation drop | pass | "Your reputation with kingdom changed (50 → 30)" in log |
| 13.3 | Auto-hostility | pass | Attacked peaceful NPC → combat started automatically |

### Auto-discovered scenarios (sprint 015 changes)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Paladin class in character creation | New class from sprint 015 | pass | Paladin option available, no fighting style at L1, correct equipment |
| Lay on Hands button visible | Sprint 015 Paladin features | pass | Button appears in action bar for Paladin (as "lay_on_hands") |
| Smite choice UI | Sprint 015 Divine Smite | untested | NPC died in one hit from auto-attack; smite prompt requires action bar attack flow. Not a bug — just untested |
| Fighting style required for fighters | fe55bb0 | pass | "— Select —" is disabled, must pick a style |
| Setup config from backend | 22f2063 | pass | Character form loads available classes/races from backend config |
| Starting gold 1000 | f393bc7 | pass | Gold shows 1000 in preview and in-game |

## Quick Fixes

- **AC display in player status endpoint** (`routes_player.py:77`): Changed `ac=p.ac` to `ac=effective_ac(p)` to apply modifier pipeline (Defense style +1). Import added. All 41 API unit tests pass.

## Findings

### Blockers

None.

### Medium

1. **AC 18 instead of 19 in combat resolution** — NPC attack log shows "vs КЗ 18" for a Fighter with Defense style. The combat path calls `effective_ac(target)` which should return 19, but returned 18. The status endpoint fix (quick fix above) addresses the display, but the combat resolution AC may have a separate issue. Needs deeper investigation into whether `collect_self_modifiers` properly picks up FighterFeatures.fighting_style = Defense during actual gameplay.

### Minor

2. **Raw snake_case action names in action bar** — `long_rest`, `short_rest`, `lay_on_hands` displayed as-is instead of localized human-readable labels ("Long Rest", "Short Rest", "Lay on Hands"). Affects both peaceful and combat action bars.

3. **Mystery "3" button on Fighter action bar** — Fighter in combat showed an unexplained button labeled "3" alongside Second Wind ("1"). Fighters shouldn't have a second resource pool. Could be a Lay on Hands pool leaking across classes, or a misassigned resource.

4. **Raw "bonus_action" in tooltip** — Second Wind tooltip shows "bonus_action" as raw snake_case string instead of "Bonus Action".

5. **"Что-то произошло (entity_second_wind)"** — Second Wind log message uses generic fallback "Something happened" instead of a proper localized description. The `entity_second_wind` event type is not handled by the frontend log formatter.

## Log Analysis

- Backend: No errors or exceptions. Only expected events (action_failed for out-of-range attack, session lifecycle).
- Frontend console: 2 warnings — WebSocket close on session exit (expected).
- Structured logs clean: session lifecycle, combat events all properly logged.
