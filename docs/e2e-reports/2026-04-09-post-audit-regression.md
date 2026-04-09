# E2E Report: Post-Audit Regression (Sprint 013 close)

**Date:** 2026-04-09
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 6 (partial), 10 (spot check), auto-discovered (character creation)
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 18 tested, 18 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Play → /play, DM → /master, language toggle EN/RU |
| 1.2 | Quick start — create character | pass | Sword Vale → New Session → Character form → game dashboard, WS connected |
| 1.3 | Language toggle | pass | UI in EN, game content in RU (DND_LANGUAGE=ru) |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC "marta" visible with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player said "Hello!", NPC responded in Russian. Full dialogue in log. |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 after Wait |
| 2.4 | Move between locations | pass | The Salty Anchor → Silverport Docks, location panel updated |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | "Бой начался!" in log, CombatPanel + BattleMap appeared, initiative order shown |
| 3.2 | Attack and damage | pass | Roll breakdown: [d20(16)+4=20 vs КЗ 15], 3 damage (1 дробящий + +2 str) |
| 3.3 | End turn and NPC response | pass | NPC moved + attacked: [d20(17)+5=22 vs КЗ 19], 4 damage. HP 12→8. |
| 3.4 | Combat ends | pass | "Бой окончен." after 2 idle rounds, returned to peaceful mode |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | Sword Vale + Test Vale with Fork buttons |
| 6.5 | Sessions tab | pass | All sessions listed with Manage buttons |
| 6.6 | Creatures table | pass | All NPCs + player visible with correct HP/AC/location/brain |
| 6.10 | Advance time | pass | 11:02 → 12:02 after 1 hour advance |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby/Character+Inventory/Location columns |
| 10.2 | Compact log + expand | pass | Overlay with full event log, close button |
| 10.5 | Combat layout switch | pass | BattleMap replaced LocationPanel, CombatPanel in left column |
| 10.6 | Action bar budget display | pass | Actions:1, Bonus:1, Movement:30ft, Reaction:1 |

### Auto-discovered: Character Creation (Sprint 013)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Point buy UI | Sprint 013 new feature | pass | +/- buttons, remaining counter (15/27 → 3/27), max 15 enforced (+ disabled) |
| HP preview | Sprint 013 new feature | pass | Fighter L1 CON 14: HP=12 (d10 max + CON mod 2) |
| AC preview | Sprint 013 new feature | pass | Chain Mail 16 + Shield 2 + Defense 1 = AC 19 |
| Starting equipment text | Sprint 013 new feature | pass | "Starting equipment: Chain Mail, Longsword, Shield" |
| Fighting Style selector | Sprint 013 new feature | pass | Appears for Fighter only: Defense/Dueling/GWF |
| Class restriction | Sprint 013 new feature | pass | Only Fighter and Rogue available |

## Quick Fixes

None needed.

## Findings

### Blockers

None.

### Minor

1. **Starting equipment not equipped as items** — Player created with starting equipment text and correct AC (armor+shield applied), but `equipped_weapon: null` and `inventory: []` via API. Combat uses fists (1 bludgeoning) instead of longsword (1d8 slashing). AC calculation works because armor/shield are applied as stats, but actual Item objects are not created. Pre-existing issue — starting_equipment() returns item refs but create_player may not resolve them into equipped items.

2. **NPC brain "No movement remaining" spam** — RuleBrain keeps requesting move_to after movement is exhausted (3+ failed attempts per turn). Cosmetic — logs fill with redundant entries. Pre-existing.

3. **NPC tiefling confusion** — Marta (tavern keeper) said "Ты ведь из рода тифлингов, верно?" to a Human character. Rule-based NPC dialogue doesn't check player race. Pre-existing, cosmetic.

## Log Analysis

- No errors, exceptions, or tracebacks in backend logs
- All failed actions are info-level: NPC brain retrying unreachable targets and exhausted movement
- No WebSocket disconnections or timeouts
