# Sprint 024 — Playtest Quick Wins

**Goal:** Быстрые UX-победы из живой партии 2026-07-15 — чинит боевое движение и чистоту лога/боевого UI, полирует торговлю и i18n снаряжения, добавляет панель свойств предметов в магазине и инвентаре.

**Started:** 2026-07-16

## Context

Активного эпика simulation-core этот спринт не двигает. Запрос оператора — быстрые выигрыши пользовательского опыта без архитектурных переделок и крупного контента: мелкие фиксы и фичи с ясным эффектом на качество игры. Живая партия 2026-07-15 оставила плотный кластер таких находок в [BACKLOG](../../BACKLOG.md); спринт снимает с него сливки по критерию «максимум эффекта на минимум кода».

Отобраны восемь айтемов: боевые баги (`combat-move-budget-not-consumed`, `npc-action-errors-leak-to-log`, `faction-hostility-check-cost`, `hide-world-travel-in-combat`, `second-wind-zero-heal`), полировка снаряжения (`catalog-item-prices`, `action-bar-equip-i18n`, `action-bar-unequip-i18n`) и одна средняя фича — панель свойств предметов (`item-properties-ui`).

За границей спринта: `flee-scene-separation` (нужен /grilling), `combat-status-single-source` (зонтик-хардеринг), `combat-pathfinding-avoidance` (умный боевой ИИ — кроме проверки, что ход завершается), `ui-language-mixing` (рассинхрон язык клиента/сервера, не быстрый), мастер-видимость (`master-panel-creature-inventory`, `spawn-role-freetext-enum`). Смежные боевые баги (`rest-in-combat-not-rejected`, `equip-in-combat-free`) завязаны на `combat-status-single-source` и в скоуп не входят.

**Ссылки:** [BACKLOG](../../BACKLOG.md), [VISION](../../VISION.md), [Sprint 023](../023-trigger-table/sprint.md)

## Phase 1: Читаемость и тактика боя

Самый плотный кластер из живой партии с 11 волками — всё про то, как бой ощущается и читается. Движение в бою начинает тратить бюджет (кайтинг работает, монстр не пересекает карту за ход), чужие отказы и faction-спам уходят из лога, боевой UI не показывает меню мира, Second Wind не пугает нулевым лечением. Проверка: боевой прогон (integration/WS) — шаги списывают `movement_remaining` и ход завершается, в логе игрока нет чужих отказов, бэкенд-лог не тонет в `faction_hostility_check`, в бою нет travel-меню.

**Айтемы:** `combat-move-budget-not-consumed`, `npc-action-errors-leak-to-log`, `faction-hostility-check-cost`, `hide-world-travel-in-combat`, `second-wind-zero-heal`

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: Полировка торговли и экипировки

Стартовое снаряжение получает SRD-цены и продаётся торговцу из инвентаря; кнопки надеть/снять локализованы без сырых ID. Проверка: снять и продать стартовый предмет; кнопки equip/unequip показывают RU-метки и описания.

**Айтемы:** `catalog-item-prices`, `action-bar-equip-i18n`, `action-bar-unequip-i18n`

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Панель свойств предметов

`WeaponDef`/`ArmorDef`/`ShieldDef`/`AccessoryDef` пробрасываются из каталога в player-facing awareness/схему и отрисовываются как tooltip/панель деталей в магазине и инвентаре: урон, свойства оружия (finesse/reach/two-handed/granted conditions), base AC / dex cap брони, эффект зелий, `grant_modifiers` колец. Проверка: в магазине и инвентаре по предмету видно, что он делает, до покупки/надевания (EN+RU).

**Айтемы:** `item-properties-ui`

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
