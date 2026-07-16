# E2E Report: sprint024-phase3

**Date:** 2026-07-16
**Flags:** --no-llm
**Sections tested:** 5 (Equipment), 8 (Inventory & Accessories), 9 (Trading) + item-details cards (phase 3 feature)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, world `test_vale`, UI language RU + EN

## Summary

- Scenarios: 15 tested, 15 passed
- Quick fixes: 0
- Blockers: 0

## Results

### Phase 3 functionality (item details cards)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| A1 | Equipped slot hover — armor (RU) | pass | Chain Mail: «Базовый КД: 16», «Кап ЛОВ: 0», «Тяжёлая броня», «Нажмите, чтобы снять» |
| A2 | Equipped slot hover — weapon (RU) | pass | Longsword: «Урон: 1d8 рубящий», «Досягаемость: 5 фт», «Воинское оружие» |
| A3 | Equipped slot hover — shield (RU) | pass | «+2 КД» |
| A4 | Bag item hover (RU) | pass | Chain Mail in bag: props + «Цена: 75g»; equip click passes through the card |
| A5 | Merchant buy-list hover — potion (RU) | pass | Health Potion: «Лечит 2d4+2 ОЗ», «Цена: 50g» |
| A6 | Trade sell-list hover (RU) | pass | Same card in sell list |
| A7 | EN locale — weapon/armor cards | pass | "Damage: 1d8 slashing", "Reach: 5 ft", "Martial weapon", "Base AC: 16", "Max DEX bonus: 0", "Heavy armor", "Click to unequip" |
| A8 | Accessory card + weapon flags | pass | Ring of Protection: "Ring", "+1 AC", "Price: 3500g"; Dagger: "Ability: DEX", "Finesse, Light" |

### Section 5: Equipment

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 5.1 | Equip weapon | pass | Dagger equip swaps Longsword to bag (15g), slot updates; attack usage covered by phase 2 combat regress |
| 5.2 | Equip armor and shield | pass | AC 19 = chain mail 16 (DEX cap 0) + shield 2 + Defense 1; ring +1 → 20 |
| 5.3 | Use healing potion | pass | HP 3→10, «Ты используешь Зелье лечения (восстановлено 7 HP)», potion consumed |

### Section 8: Inventory & Accessories

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 8.1 | View inventory panel | pass | 6 slots + gold; Сумка section appears when bag non-empty |
| 8.2 | Equip accessory | pass | Ring of Protection: AC 19→20, slot filled |
| 8.3 | Unequip accessory | pass | AC 20→19, slot empty, item back in bag |

### Section 9: Trading

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 9.1 | Open trade with merchant | pass | Пип Торговец 200g, Health Potion 50g with price |
| 9.2 | Buy item | pass | Gold 1000→950, merchant 200→250, potion in bag |
| 9.3 | Sell item | pass | Gold 950→1000, item back at merchant |
| 9.4 | Insufficient gold | pass | «Недостаточно золота (нужно 50, есть 5)», purchase rejected; buy button disabled client-side while gold < price |

## Quick Fixes

- None needed.

## Findings

### Blockers
- None. Phase 3 deliverables green end to end in both locales.

### Minor (pre-existing, out of phase scope)

- **КД (client) vs КЗ (server) for AC.** The new cards use «КД», consistent with all existing frontend keys (`ac_display`, `vs_ac`, `stat_ac`), but server-side combat log lines say «КЗ» («против КЗ 15» comes from `.po`). Client/server terminology mismatch predates phase 3; belongs to the `ui-language-mixing` cluster.
- **Item names unlocalized in lists, localized in log.** Bag/trade show "Health Potion" while the use-message says «Зелье лечения». Known item-name-localization gap (already noted in phase 2 report).
- Ring slot shows only one generic "Ring" label for both the slot name and the accessory-kind line in the card; cosmetic.

### Observations (correct behavior worth noting)

- Sell button disables when the merchant can't afford the item (Ring of Protection 3500g vs merchant 200g).
- Buy button disables client-side when player gold < price; server rejection message also correct.
- Master `PATCH /creatures/{id}` silently ignores unknown fields (sent `hp`, expected `current_hp`) — Pydantic default; caused no harm here, but a 422 on unknown keys would have failed faster.

## Log Analysis

- Backend log: 0 tracebacks, 0 exceptions. Only flagged line is the intentional 9.4 insufficient-gold `action_failed` warning.
- Console: 0 errors; 1 benign dev-mode WS reconnect warning at page load.
