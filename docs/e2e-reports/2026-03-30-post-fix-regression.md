# E2E Report: Post-blocker-fix regression

**Date:** 2026-03-30
**Flags:** --no-llm
**Sections tested:** 1, 5 (blocker verification), 9 (trading)
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 7 tested, 7 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Play + Dungeon Master, EN/RU toggle |
| 1.2 | Quick start — pick existing world | pass | Sword Vale → fighter/human/STR 16/100g → /play/:id, WS connected, 3-column dashboard |

### Section 5: Equipment

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 5.2 | Equip armor and shield | pass | **FIXED.** Chain Mail equipped → AC 10→16. Shield equipped → AC 16→18. Both items visible in equipment slots. Correct computation: base_ac 16 (heavy, 0 DEX) + shield 2 = 18. |
| 5.3 | Use healing potion | pass | **FIXED.** Bought Health Potion from Gretta (50g). Set HP to 5/10 via master API. Used potion → "Ты используешь Зелье лечения (восстановлено 5 HP)". HP restored to 10/10. Potion consumed from inventory. No crash. |

### Section 9: Trading

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 9.1 | Open trade with merchant | pass | Gretta's Trade panel opens automatically when nearby. Shows merchant gold (550g), buy/sell sections. |
| 9.2 | Buy item | pass | Bought Health Potion for 50g. Gold decreased 100→50. Potion appeared in bag with USE button. Dagger (200g) correctly disabled — insufficient gold. |
| 9.4 | Insufficient gold | pass | Dagger Buy button disabled when player has 50g < 200g price. |

## Findings

### Blockers

None. Both blockers from 2026-03-29 report are resolved.

### Minor (carried over from 2026-03-29, not fixed in this cycle)

1. **Equip log says "оружие" for all item types** — Equipping armor and shield both log "Ты экипируешь оружие" (weapon). Perception function `_perceive_equip` only checks `weapon_name` key in event data; armor/shield events use `armor_name`/`shield_name` keys which fall through to default "a weapon".

## Log Analysis

- 0 errors, 0 tracebacks in backend logs
- 1 WebSocket reconnection warning (expected on page load timing)
