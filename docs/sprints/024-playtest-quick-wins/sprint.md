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

## Phase 3: Панель свойств предметов ✓

Закрыта 2026-07-16: integration 166 green (+2 новых теста на `props` в payload торговца и REST-статусе), E2E 15/15 (карточки всех пяти видов предметов в RU и EN, торговля, экипировка, аксессуары). Отчёт: [e2e/phase3-report.md](e2e/phase3-report.md). Найденное вне скоупа: терминологический рассинхрон КД (клиент) / КЗ (сервер) и нелокализованные имена предметов — оба в кластере `ui-language-mixing`.

`WeaponDef`/`ArmorDef`/`ShieldDef`/`AccessoryDef` пробрасываются из каталога в player-facing awareness/схему и отрисовываются как tooltip/панель деталей в магазине и инвентаре: урон, свойства оружия (finesse/reach/two-handed/granted conditions), base AC / dex cap брони, эффект зелий, `grant_modifiers` колец. Проверка: в магазине и инвентаре по предмету видно, что он делает, до покупки/надевания (EN+RU).

**Айтемы:** `item-properties-ui`

**Разведка (2026-07-16):** свойства предметов сейчас доезжают до UI только строкой `describe_item()` (`core/awareness.py:65`) — захардкоженный английский в native `title`; броня и щит не показывают ничего, кроме имени. Типизированные дефы до фронта не доходят. Решение — аддитивный машиночитаемый `props` в payload + клиентский рендер с i18n-метками, чтобы не завязываться на серверный язык (`ui-language-mixing` не трогаем). LLM-промпты берут из `ItemInfo` только `id`/`name`/`description`, `props` их не раздувает.

**Tasks:**

1. [Структурные свойства предметов в player-facing payload](tasks/phase3-task1-item-props-payload.md) — `item_props()` из типизированных дефов, JSON-safe `props` на `ItemInfo`/`EquippedInfo`, прошивка в инвентарь/экипировку/товары торговца/лут
2. [Панель деталей предмета в магазине и инвентаре](tasks/phase3-task2-item-details-tooltip.md) — компонент `ItemDetails` (CSS-hover карточка), рендер `props` с i18n-метками EN+RU в `InventoryPanel` и `TradePanel`, fallback на `description`

---

## Status

**Current:** CLOSED (2026-07-16).

## Decisions

- **Ось движения унифицирована на хендлерах.** `MOVE`→`CostType.FREE`, `CostType.MOVEMENT` удалён; `movement_remaining` списывают только movement-хендлеры по факту пройденного. Диспетчер владеет осью действий (action/bonus/reaction). Инвариант зафиксирован в CLAUDE.md.
- **`props` считается на сервере, метки рисует клиент.** Машиночитаемый JSON-safe `props` из типизированных дефов вместо серверной строки `describe_item()`; i18n-метки живут во фронтовом `game.json`. Не завязываемся на серверный язык, пока `ui-language-mixing` открыт. Значения `props` обязаны оставаться JSON-примитивами: payload торговца и лута идут через `dataclasses.asdict` без JSON-прохода.
- **`equipped` расширен до `list[dict[str, object]]`** в `PlayerStatusData` и `PlayerStatusResponse`: `props` — dict, старая str-типизация отбивала создание персонажа 422.
- **Карточка `ItemDetails` на `fixed` вместо `absolute`** — все четыре точки рендера внутри `overflow-y-auto`, absolute клипался бы. Контент всегда в DOM (CSS-hover), поэтому тестируем без реального ховера.
- **RU-описания equip/unequip дописаны в `.po` руками.** `make messages` не годится: гонит `pygettext --keyword=_` без `N_` и падает на f-строках.

## Deferred

- `ac-stale-on-unequip` — снятие брони повышает КЗ (`effective_ac` держит устаревший `creature.ac`). Вскрыт E2E фазы 2, предсуществующий, трогает backwards-compat `max()` для stat-block AC существ.
- `use-item-zero-heal` — ветка `healed == 0` для зелий (Second Wind-половина закрыта в phase 1 task 3).
- `ui-language-mixing` — пополнен находками спринта: КД (клиент) против КЗ (сервер), английские имена предметов в локализованном логе.
- Остаток `faction-hostility-check-cost` — кросс-слойный faction-to-faction запрос на пару всё ещё без мемоизации, покрыт `awareness-rebuild-cache`.
- `combat-status-single-source`, `flee-scene-separation`, `combat-pathfinding-avoidance`, `equip-action-collapse` — вне скоупа с планирования.

## Results

**Completed:** 2026-07-16

Восемь айтемов из живой партии 2026-07-15 закрыты за три фазы: бой стал читаться (единый учёт бюджета движения, чужие отказы не текут в лог игрока, `faction_hostility_check` INFO→DEBUG, Second Wind без «0 ОЗ»), снаряжение получило SRD-цены и локализованные кнопки, свойства предметов видно карточкой до покупки и надевания в RU и EN.

Метрики: backend 2573 unit (+~30), frontend 299 (+10), integration 166 (+4). Post-audit E2E 26/26, 0 блокеров. Аудит 2026-07-16 — 13 находок, 2 применены quick-fix, остальные уже трекались в BACKLOG.

Ключевое открытие: премиса `combat-move-budget-not-consumed` («бюджет не тратится, кайтинг бесконечен») оказалась неверной — диспетчер списывал бюджет, speed=30 честно упирался в 30 ft. Разведка кода до правки переформулировала таск в унификацию раздвоенного учёта, где и жили настоящие латентные баги: диагональ списывалась плоскими 5 ft вместо 5/10, частичный шаг списывал запрос, а не пройденное.

`hide-world-travel-in-combat` при разведке оказался уже закрытым с Sprint 009 (`GameScreen` свапает правую колонку в бою) — помечен superseded, playtest-симптом ушёл в `combat-status-single-source`.

При закрытии полный `/update-docs` вскрыл дрейф документации шире дельты спринта: `master/` описан как живой LLM-оркестратор (пустой стаб с первого коммита, никем не импортируется), CLI/Telegram-адаптеры как существующие, `xp_for_kill` вместо `xp_for_cr`, 7 сценариев e2e-плейбука расходились с поведением кода. Починен предсуществующий флейк `test_timeout_preserves_lifecycle_until_same_thread_stops` (тест не восстанавливал 10ms-таймаут, teardown гонялся с живым раунд-потоком).
