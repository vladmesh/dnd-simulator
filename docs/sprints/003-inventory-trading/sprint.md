# Sprint 003 — Inventory & Trading

**Goal:** Полноценная система инвентаря с экипировкой в расширенные слоты, торговля с NPC-торговцами за золото.

**Started:** 2026-03-25

## Context

Sprint 001 заложил фундамент предметов: WeaponDef, ArmorDef, ShieldDef, equip/unequip экшены, потионы. Но экипировка ограничена тремя слотами (weapon, armor, shield), нет панели инвентаря на фронте, нет золота и торговли. Этот спринт добивает инвентарную систему до играбельного состояния: аксессуары с модификаторами, UI для управления экипировкой, торговцы.

**В скоупе:**
- Новые слоты: head, feet, ring (поверх weapon, armor, shield)
- Аксессуары с модификаторами через существующий modifier pipeline
- Золото на существах (начальное из YAML), фиксированные цены на предметах
- Merchant-флаг на NPC, инвентарь торговца
- Buy/sell экшены
- Фронт: панель инвентаря (equipped slots + сумка), trade UI
- YAML-контент: базовые аксессуары, торговец в деревне

**Вне скоупа:**
- Лут с монстров, наценки, торг
- Слоты hands, cloak, amulet
- Двуручное оружие, ограничения по весу
- Магические эффекты за пределами modifier pipeline

**Ссылки:** [ROADMAP.md](../../ROADMAP.md), [BACKLOG.md](../../BACKLOG.md), [Sprint 001](../001-class-mechanics/sprint.md)

---

## Phase 1: Accessory Slots + Modifiers ✓

Новые типы предметов (AccessoryDef), 3 новых слота на Creature (head, feet, ring), equip/unequip экшены, интеграция с modifier pipeline. Пара аксессуаров в YAML. Юнит-тесты.

**Верификация:** equip кольцо → AC растёт, equip ботинки → speed растёт. `make test-unit` зелёный.

**Tasks:**

1. [Generic Equip/Unequip Mechanism](tasks/phase1-task1-generic-equip.md)
2. [Accessory Slots with Modifier Effects](tasks/phase1-task2-accessory-slots.md)

## Phase 2: Inventory UI + Gold ✓

Золото на Creature + цена на Item. Awareness отдаёт полное состояние экипировки и инвентаря. Фронт: панель с 6 слотами + сумка + золото. Equip/unequip кликом из панели.

**Верификация:** в браузере видно инвентарь, можно надеть/снять предмет из панели, золото отображается.

**Tasks:**

1. [Inventory & Equipment Awareness](tasks/phase2-task1-inventory-awareness.md)
2. [Frontend Inventory & Equipment Panel](tasks/phase2-task2-inventory-panel.md)

## Phase 3: Trading

Merchant-флаг на NPC, инвентарь торговца, buy/sell экшены + хендлеры. Trade UI на фронте. YAML-контент: торговец в деревне с товарами.

**Верификация:** игрок открывает торговлю, покупает предмет, золото уменьшается, предмет в инвентаре.

**Tasks:**

1. [Merchant Model + Trade Rules](tasks/phase3-task1-merchant-model-trade-rules.md)
2. [Buy/Sell Action Handlers + Dispatch](tasks/phase3-task2-buy-sell-handlers.md)
3. [Trade UI](tasks/phase3-task3-trade-ui.md)

---

## Status

**Current:** Phase 3 tasks generated. Ready to start task 1.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
