# E2E Report: Post-sprint-011 regression

**Date:** 2026-03-29
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 5, 6, 8, 10 (partial)
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 28 tested, 22 passed, 4 failed, 2 partial
- Quick fixes: 0 applied
- Blockers: 2 found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Play + Dungeon Master, EN/RU toggle |
| 1.2 | Quick start — pick existing world | pass | Sword Vale → fighter/human/STR 16 → /play/:id, WS connected, 3-column dashboard |
| 1.3 | Language toggle | pass | EN→RU on master page: all labels translated correctly (Мастер подземелий, Миры, Долина Мечей, Форк) |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC marta visible with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player says text, NPC responds "Что будете заказывать?" |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 |
| 2.4 | Move between locations | pass | Moved to Silverport Docks, new NPC lira visible, path back shown |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | combat_started, initiative order, CombatPanel + BattleMap visible, budget bar |
| 3.2 | Attack and damage | pass | Crit! d20(20)+5=25 vs КЗ 15, 4 damage (1 bludgeoning + 3 STR). Clickable roll entry (attack card modal). Actions consumed correctly. |
| 3.3 | End turn and NPC response | partial | Round advanced to 2, budget refreshed. But NO NPC turn entries in log — Lira took no visible action across 7 rounds. No player feedback for NPC turns. |
| 3.4 | Combat ends | pass | entity_died + combat_ended in log. Sidebar returned to peaceful. "Nobody around." |

### Section 5: Equipment

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 5.1 | Equip weapon | pass | Longsword equipped, visible in slot, removed from bag |
| 5.2 | Equip armor and shield | **fail** | **BUG:** AC shows 0 after equipping Chain Mail (should be 16), then 2 after adding Shield (should be 18). Backend confirms AC: 2, equipped_armor: None — equip not persisting correctly. Also: equip log says "оружие" (weapon) for armor and shield. |
| 5.3 | Use healing potion | **fail** | **BLOCKER:** KeyError: 'heal_dice' in rules/handlers/items.py:70. Potion params missing heal_dice key. Round loop crashes → GAME OVER displayed even though character is alive (5/12 HP). |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Master — Worlds tab | pass | Library worlds with Fork only |
| 6.2 | Fork world | pass | Toast "World forked", new world with Fork + Delete |
| 6.3 | Delete world | pass | Confirm dialog, world removed |
| 6.4 | World editor stepper | pass | 5 tabs (Geography → Entities), tables with data, Back/Next/Close |
| 6.5 | Create and manage session | pass | Sessions tab, existing sessions listed with Manage buttons |
| 6.6 | Spawn creature | pass | Grak spawned at market, toast "Creature spawned" |
| 6.7 | Edit creature HP | pass | HP updated to 5/10, toast "Creature updated" |
| 6.8 | Toggle brain type | pass | rule_based → llm, toast "Set Brain" |
| 6.9 | Delete creature | pass | Confirm dialog, creature removed |
| 6.10 | Advance time | pass | D1 → D2, weather + squad movement events reported |
| 6.11 | Save and load | pass | Save "test" created, visible in list |

### Section 8: Inventory & Accessories

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 8.1 | View inventory panel | pass | 6 equipment slots + Bag with items + gold display |

### Section 10: Dashboard Layout (partial — observed during other tests)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby (left), Character+Inventory (center), Location (right) |
| 10.2 | Compact log + expand overlay | pass | Expand button opens overlay, close button works |
| 10.4 | Click-to-move on BattleMap | pass | Click reachable cells → creature moves, movement budget decreases |
| 10.5 | Combat layout switch | pass | BattleMap replaces LocationPanel in combat, restores after |
| 10.6 | Action bar budget display | pass | Actions/Bonus/Movement/Reaction with numbers, buttons disappear after use |
| 10.7 | Click occupied cell → creature inspect | **fail** | Clicking NPC cell on battle map did not open inspect modal |

### Sections not tested

| Section | Reason |
|---------|--------|
| 4 (Class Features) | Blocked by equipment/potion bugs — can't properly test Second Wind, Fighting Styles without working equip |
| 7 (Conditions) | Skipped due to time — requires master-applied conditions + combat |
| 9 (Trading) | Skipped — merchant interaction not reachable in test session |
| 10.3 (NPC inspect modal) | Not tested from Nearby panel |
| 6.12-6.13 (Give item) | Skipped due to time |
| 8.2-8.3 (Equip/unequip accessories) | Blocked by equip bugs |
| 11 (LLM) | Skipped (--no-llm) |

## Findings

### Blockers

1. **Healing potion crash (GAME OVER)** — `KeyError: 'heal_dice'` in `rules/handlers/items.py:70`. Potion created via master API has params without `heal_dice` key. The round loop crashes and the frontend shows "GAME OVER" even though the character is alive. This blocks potion usage entirely.

2. **AC calculation broken after equip** — Equipping Chain Mail (base_ac=16, dex_cap=0) shows AC 0. Adding Shield (+2) shows AC 2. Backend API confirms `equipped_armor: None`, `equipped_shield: None` — the equip actions fire events but don't persist to creature state. The AC uses only shield bonus, ignoring armor entirely. This blocks all armor/shield gameplay.

### Minor

1. **Mixed language in game UI** — Backend serves strings in Russian (DND_LANGUAGE=ru default) while frontend is in English. Affects: NPC race labels ("человек"), log messages ("Ты говоришь", "Бой начался"), damage types ("дробящий"), AC label ("КЗ"). Everything backend-generated is RU while frontend chrome is EN.

2. **"КЗ" still appears in attack logs** — Sprint 011 explicitly fixed КЗ→КД (commit 4c7bccd), but attack logs still show "vs КЗ 15". Either a different code path or the fix didn't cover the combat manager's attack format string.

3. **Equip log says "оружие" for all item types** — Equipping armor and shield both log "Ты экипируешь оружие" (weapon). Should say "броню" (armor) or "щит" (shield) respectively.

4. **Death message uses perception description** — "человек, выглядит раненым погибает" instead of using the creature's name. Grammatically awkward.

5. **NPC turns produce no log entries** — In 7 rounds of combat, Lira (rule-based NPC) produced zero visible log entries. Player gets no feedback about what the NPC did on their turn. Either NPCs with no weapons do nothing, or NPC actions aren't logged to the player.

6. **No language toggle on game screen** — EN/RU buttons only available on landing and master pages. Once in-game, language can't be switched.

7. **Forked world shows same name** — After forking Sword Vale, both the original and fork show "Sword Vale". No indication which is the fork. Should append the fork ID or "(fork)" to distinguish.

8. **Spawn form shows raw Pydantic error** — Empty Role field triggers: "1 validation error for NpcContent role Input should be 'commoner', 'blacksmith'...". Should be a user-friendly message.

9. **Longsword display in bag** — Shows as `Longsword (weapon: , reach 5ft)` with empty weapon damage info. The parenthetical is malformed.

10. **Click occupied cell in combat (10.7)** — Clicking NPC cell on battle map does not open creature inspect modal as specified in playbook.

## Log Analysis

- 1 traceback: `KeyError: 'heal_dice'` in potion handler (blocker #1)
- 2 info-level "action_failed" for out-of-range attacks (expected)
- No other warnings or errors in backend logs
- Frontend console: 1 warning (WebSocket reconnection), 1 error (failed POST on creature spawn with empty role)
