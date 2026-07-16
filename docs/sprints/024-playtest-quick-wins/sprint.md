# Sprint 024 — Playtest Quick Wins

**Goal:** Быстрые UX-победы из живой партии 2026-07-15 — чинит боевое движение и чистоту лога/боевого UI, полирует торговлю и i18n снаряжения, добавляет панель свойств предметов в магазине и инвентаре.

**Started:** 2026-07-16

## Context

Активного эпика simulation-core этот спринт не двигает. Запрос оператора — быстрые выигрыши пользовательского опыта без архитектурных переделок и крупного контента: мелкие фиксы и фичи с ясным эффектом на качество игры. Живая партия 2026-07-15 оставила плотный кластер таких находок в [BACKLOG](../../BACKLOG.md); спринт снимает с него сливки по критерию «максимум эффекта на минимум кода».

Отобраны восемь айтемов: боевые баги (`combat-move-budget-not-consumed`, `npc-action-errors-leak-to-log`, `faction-hostility-check-cost`, `hide-world-travel-in-combat`, `second-wind-zero-heal`), полировка снаряжения (`catalog-item-prices`, `action-bar-equip-i18n`, `action-bar-unequip-i18n`) и одна средняя фича — панель свойств предметов (`item-properties-ui`).

За границей спринта: `flee-scene-separation` (нужен /grilling), `combat-status-single-source` (зонтик-хардеринг), `combat-pathfinding-avoidance` (умный боевой ИИ — кроме проверки, что ход завершается), `ui-language-mixing` (рассинхрон язык клиента/сервера, не быстрый), мастер-видимость (`master-panel-creature-inventory`, `spawn-role-freetext-enum`). Смежные боевые баги (`rest-in-combat-not-rejected`, `equip-in-combat-free`) завязаны на `combat-status-single-source` и в скоуп не входят.

**Ссылки:** [BACKLOG](../../BACKLOG.md), [VISION](../../VISION.md), [Sprint 023](../023-trigger-table/sprint.md)

## Phase 1: Читаемость и тактика боя ✓

Самый плотный кластер из живой партии с 11 волками — всё про то, как бой ощущается и читается. Учёт бюджета движения унифицируется (одно место списания по факту пройденного, корректная диагональ, честная отбивка, видимость остатка мозгу), чужие отказы и faction-спам уходят из лога, Second Wind не пугает нулевым лечением. Проверка: боевой прогон (integration/WS) — шаги списывают `movement_remaining` и ход завершается, в логе игрока нет чужих отказов, бэкенд-лог не тонет в `faction_hostility_check`.

**Правка по ходу разведки (task 1):** премиса `combat-move-budget-not-consumed` («бюджет не тратится») оказалась неверной — бюджет списывает диспетчер через `action_cost` (`MOVE`=`cost_type=MOVEMENT`), кайтинг уже упирается в speed. Реальная проблема — раздвоенный учёт (`MOVE` списывает по запросу в диспетчере против `MOVE_TO`/`DASH` по факту в хендлере) с латентными багами диагонали/частичного шага. Таск переформулирован в унификацию оси движения.

**Айтемы:** `combat-move-budget-not-consumed`, `npc-action-errors-leak-to-log`, `faction-hostility-check-cost`, `second-wind-zero-heal`

`hide-world-travel-in-combat` при разведке оказался уже закрыт: `GameScreen.tsx:112` свапает правую колонку (`isCombat ? <BattleMap /> : <LocationPanel />`) с Sprint 009, travel-меню в бою не рендерится. Playtest-симптом — десинк режима после flee (`combat-status-single-source`/`flee-scene-separation`, вне скоупа). Айтем помечен superseded в бэклоге.

**Tasks:**

1. [Единый учёт бюджета движения в бою](tasks/phase1-task1-combat-move-budget.md) — переформулирован: бюджет **уже** списывается диспетчером (премиса «не тратится» неверна), но учёт раздвоен — `MOVE`=MOVEMENT (диспетчер, по запросу) против `MOVE_TO`/`DASH`=хендлер (по факту). Унифицируем: `MOVE`→FREE, `handle_move` списывает фактический `moved_ft` атомарно (чинит диагональ/частичный шаг), внятная отбивка `move_to`, остаток движения в LLM-промпт
2. [Чистота боевого лога](tasks/phase1-task2-combat-log-noise.md) — чужие ошибки не текут игроку, faction-спам → DEBUG, relation_fn один раз на ребилд
3. [Second Wind без «0 ОЗ»](tasks/phase1-task3-second-wind-zero-heal.md) — сообщение о полном здоровье при `healed == 0`

## Phase 2: Полировка торговли и экипировки ✓

Стартовое снаряжение получает SRD-цены и продаётся торговцу из инвентаря; кнопки надеть/снять локализованы без сырых ID. Проверка: снять и продать стартовый предмет; кнопки equip/unequip показывают RU-метки и описания.

Закрыта 2026-07-16: integration 164 green, E2E (trading + equip/unequip i18n + combat regress) 8/8. E2E вскрыл предсуществующий баг `ac-stale-on-unequip` (снятие брони повышает КЗ) — вне скоупа фазы, в бэклоге.

**Айтемы:** `catalog-item-prices`, `action-bar-equip-i18n`, `action-bar-unequip-i18n`

**Tasks:**

1. [SRD-цены для каталога предметов](tasks/phase2-task1-catalog-item-prices.md) — проставить `price` в 31 каталожный YAML (плумбинг цены уже на месте, не хватает данных); снятый стартовый предмет продаётся торговцу из инвентаря
2. [i18n кнопок надеть/снять](tasks/phase2-task2-equip-unequip-i18n.md) — 10 slot-меток в `game.json` (EN+RU), хардкод `USE`/`EQUIP` в `InventoryPanel` через `t()`, 12 описаний equip/unequip в RU `.po`; `equip-action-collapse` вне скоупа

## Phase 3: Панель свойств предметов

`WeaponDef`/`ArmorDef`/`ShieldDef`/`AccessoryDef` пробрасываются из каталога в player-facing awareness/схему и отрисовываются как tooltip/панель деталей в магазине и инвентаре: урон, свойства оружия (finesse/reach/two-handed/granted conditions), base AC / dex cap брони, эффект зелий, `grant_modifiers` колец. Проверка: в магазине и инвентаре по предмету видно, что он делает, до покупки/надевания (EN+RU).

**Айтемы:** `item-properties-ui`

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 1 complete (all 3 tasks done, integration 164 green, E2E 9/9). Phase 2 tasks generated (2 tasks). Ready to start Phase 2 task 1.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
