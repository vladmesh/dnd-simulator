# E2E Report: sprint024-phase2

**Date:** 2026-07-16
**Flags:** --no-llm
**Sections tested:** 5 (Equipment), 8 (equip/unequip i18n), 9 (Trading) + combat regression
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, world `test_vale`, UI language RU

## Summary

- Scenarios: 8 tested, 8 passed
- Quick fixes: 0
- Blockers: 0 (phase deliverables all green)
- Findings: 1 pre-existing correctness bug (AC), 1 minor i18n gap — both out of Phase 2 scope

## Results

### Phase 2 functionality (primary)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| T1.1 | Catalog item shows SRD price | pass | Chain Mail shows `75g` in bag; Health Potion `50g` |
| T1.2 | Buy from merchant | pass | Health Potion 50g: gold 1000→950, merchant 200→250, potion lands in bag |
| T1.3 | Sell starting gear from inventory | pass | Unequip Chain Mail → bag (75g) → Sell: gold 950→1025 (+75 full SRD), item transfers to merchant, gone from bag |
| T2.1 | Equip button i18n (RU) | pass | Bag item shows "Надеть"; potion shows "Использовать" |
| T2.2 | Equip/unequip log descriptions (RU) | pass | "Ты экипируешь Chain Mail" / "Ты убираешь Chain Mail" |
| T2.3 | Slot labels i18n (RU) | pass | Броня / Голова / Ноги / Кольцо / Сумка all localized |

### Regression

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Combat initiate + attack | pass | RU initiative order, attack roll "Ты атакуешь Гоблин (longsword slash) [d20(3)+2=5 vs КЗ 15], промах", combat panel + battle map switch in, RU budget bar (Действия/Бонус/Движение/Реакция) |
| 2.4 | Travel between locations | pass | Tavern ↔ market travel via graph path, Location Panel updates |

## Findings

### Blockers
- None for Phase 2. Prices, sell-from-inventory, and equip/unequip i18n all work end to end.

### Pre-existing (out of scope, not introduced by Phase 2)

- **AC increases when armor is unequipped.** Fighter with Chain Mail + Shield + Defense shows AC 19. Unequipping Chain Mail raises AC to **21** (backend confirmed via `player_status`, not a display glitch). Root cause: `rules/modifiers.py:224` unarmored branch `base = max(creature.ac, 10 + dex_mod)`. At character creation `player.ac` is stored as the *armored* effective AC (`commands_player.py:117`) and never rewritten on equip changes, so `max()` keeps the stale armored value and the shield bonus stacks on top. Monsters/NPCs are unaffected (a plain commoner barkeep correctly showed КЗ 10). Fix touches the "backwards compat" `max()` that also serves stat-block AC creatures — needs care + tests. → BACKLOG.

### Minor
- **Movement log line partially untranslated.** Two enemy-movement renderings coexist: localized "Гоблин перемещается на юго-запад (5 ft)" and English "Гоблин moved (25 ft)". Pre-existing, unrelated to Phase 2 (equip/unequip i18n). → BACKLOG.
- Starting-equipment names remain English in the RU creation preview ("Chain Mail, Longsword, Shield") and item names stay English in-game. Known separate item-name-localization gap, out of scope.

## Log Analysis

- Backend log: 0 tracebacks, 0 exceptions. Clean.
- Enemy technical refusals did not leak to the player log (Phase 1 task 2 holding).
