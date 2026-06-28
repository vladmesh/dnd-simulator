# Sprint 018 — Lairs, Encounters & Loot

**Goal:** Монстры населяют мир независимо от игрока: постоянные логова (зачищаются убийством ядра), региональные таблицы встреч, опасность по времени суток и лутаемые контейнеры/трупы.

**Started:** 2026-06-28

## Context

Бой, классы (Fighter/Rogue/Paladin L1-L2), XP и уровни уже есть, но мир не даёт игроку самостоятельной, неподстраивающейся опасности. Монстры приходят только бродячими сквадами (материализуются рядом с игроком) и вероятностным encounter-роллом по локации (Sprint 004). Нет фиксированных мест, где живёт конкретный монстр, нет региональной угрозы, нет суточного ритма, нет добычи с боя.

Спринт закрывает backlog must-айтем `monster-spawn` в кенши-рамке вижна («мир, который живёт сам»): опасность это свойство мест и времени, она **не масштабируется под уровень игрока**. Игрок сам решает, готов ли он лезть в логово или идти через регион ночью. Лут замыкает петлю «зачем драться» и кормит уже готовую систему XP (Sprint 017).

Строим поверх существующего: ecology-слой и сквады, `MonsterTemplate` с `cr`/`xp_value`, location-keyed encounter-таблицы и проксимити-материализация (Sprint 004), система предметов и каталоги + механика переноса в торговле (`rules/trade.py`).

**Ссылки:** [VISION](../../VISION.md), [ROADMAP](../../ROADMAP.md), [BACKLOG `monster-spawn`](../../BACKLOG.md), [Sprint 004](../004-monster-encounters/sprint.md)

## Phase 1: Логова (Lairs) ✓

Концепт логова: локация с постоянным населением монстров и машиной состояний `active → depleted`. Пока живо ядро (core/boss), население восстанавливается до капа по интервалу на тике ecology; смерть ядра деплитит логово навсегда (респавн выключен, состояние сохраняется). Для логов без выраженного босса опциональный `depletion_chance` (ролл после полного вайпа). Лута в этой фазе нет.

**Verify:** integration. Мир с гоблинским логовом; вход → население на месте; убил миньонов, промотал время → респавн; убил ядро → респавн выключен навсегда и переживает save/load.

**Решение по модели:** логово это отдельная сущность на `EcologyLayer` (не разновидность `Squad`): стационарно, фиксированный ростер с ядром, машина состояний `ACTIVE → DEPLETED`. Переиспользуем паттерн материализации сквадов (спавн `Creature` рядом с игроком + дематериализация при уходе), не класс `Squad`. `depleted`/население логова персистятся в `EcologyLayer.get_state`. Деплит-ролл через сидируемый `get_global_rng()`.

**Tasks:**

1. [Lair model, content & materialization](tasks/phase1-task1-lair-materialization.md) — `Lair`/`LairState`, схема + `load_lairs`, `LAIRS_AT_LOCATION`, материализация полного ростера при входе
2. [Lair respawn while active](tasks/phase1-task2-lair-respawn.md) — синк потерь визита, респавн до полного ростера на тике, персистенс состояния логова
3. [Lair depletion](tasks/phase1-task3-lair-depletion.md) — смерть ядра → `DEPLETED` навсегда, опц. `depletion_chance`, переживает save/load

**Closed 2026-06-28.** Integration: +4 lair tests (`tests/integration/test_lairs.py` + `lair_world`) covering load, full-roster materialization, core-death depletion, depleted-state save/load survival; suite 142 → 146 green. E2E: regression on the shared round/activation/combat path (setup → peaceful → combat), 12/12 pass, 0 blockers — see [e2e/phase1-report.md](e2e/phase1-report.md).

## Phase 2: Лут и контейнеры (Loot & Containers) ✓

Примитив лутаемого инвентаря. `InventoryHolder` Protocol (всё, у чего есть `inventory` + `gold`) и `is_lootable()` как производное состояние (мёртвое существо / открытый контейнер). Труп остаётся `Creature` (класс не меняем: задел под воскрешение и «осмотреть труп»). Новая лёгкая `Entity`-сущность `Container` (сосед `Creature`, без HP/хода/мозга). Вынос общего `transfer_items` из `rules/trade.py` и перевод торговли на него. Action `take` поверх любого `Lootable` в локации + awareness + лут-UI. Казна логова = `Container`, наполняется из loot-таблицы при спавне (опционально за ядром). Торговля и воровство не замешиваются в лут: общий у них только примитив переноса, гейты разные.

**Verify:** integration. Труп с инвентарём → `take` переносит предметы и золото игроку; казна логова доступна после смерти ядра; существующие trade-тесты зелёные (рефактор не сломал перенос). E2E: убил → залутал.

**Решения по фазе (из планирования):**
- `gold` поднят с `Character` на `Creature` — единый субстрат `InventoryHolder` (inventory + gold); мобы по умолчанию `gold == 0`.
- `take` — take-all: одно действие переносит весь инвентарь + золото холдера. Per-item отложено.
- Казна логова = персистентный `Container`-entity (новый `EntityKind.CONTAINER`, save/load в Task 2); спавнится один раз, не дематериализуется, разлутанное состояние переживает уход/возврат и save/load.
- Трупы обычных мобов не лутаются: lair-спавны `temporary=True` и удаляются на смерти. Лут идёт через казну-`Container` и персистентные (authored) трупы. Общемонстровый дроп — backlog (`loot-drops-monsters`).
- Лут-таблицы детерминированы (список предметов + золото в контенте); рандомные таблицы — вне scope.

**Tasks:**

1. [InventoryHolder substrate, `is_lootable`, `transfer_items`](tasks/phase2-task1-inventory-holder.md) — `gold`→`Creature`, `InventoryHolder` Protocol, `is_lootable`, общий примитив переноса, рефактор trade
2. [`Container` entity + save/load](tasks/phase2-task2-container-entity.md) — `Container(Entity)` (inventory/gold/open), `EntityKind.CONTAINER`, персистенс
3. [`take` action](tasks/phase2-task3-take-action.md) — `ActionType.TAKE`, `LootActionProvider`, валидация, хендлер, awareness, лут-UI
4. [Lair treasury](tasks/phase2-task4-lair-treasury.md) — казна-`Container` из контента, гейт за ядром, персистенс разлутанного состояния

## Phase 3: Региональные таблицы встреч (Region Encounter Tables) ✓

Encounter-таблицы можно задавать на уровне региона; локация без своей таблицы фоллбечится на таблицу своего региона (резолв через `location_graph`). Своя таблица локации перекрывает региональную. Контент-автор задаёт профиль угрозы на весь регион без поштучной разметки локаций.

**Verify:** integration. Локация без своей таблицы в регионе с таблицей → ролл из региональной; локация со своей таблицей → её таблица, регион игнорируется.

**Решение по подходу:** резолв «регион → локация» делаем на загрузке, калькой с уже существующей сборки `battle_map_configs` (`game_service.py:153-163`: региональный дефолт + пер-локационный override). Региональные таблицы схлопываются в эффективную пер-локационную `dict[str, list[EncounterEntry]]`, поэтому рантайм `ActivationManager` не меняется. Контент аддитивен: новый sibling-ключ `region_encounters` (по region_id) рядом с существующим `encounters` (по location_id) в `ecology/monsters.yaml`, без миграции.

**Tasks:**

1. [Региональные encounter-таблицы — схема, загрузка, fail-fast](tasks/phase3-task1-region-encounter-tables.md) — `region_encounters` в YAML, `parse_region_encounters` (fail-fast по template и region_id), `load_monsters` → 3-кортеж, прокидка в `game_service`
2. [Фоллтру локация → регион (override) и боевой ролл](tasks/phase3-task2-region-fallthrough.md) — сборка эффективных таблиц (регион дефолт, локация override) калькой `battle_map_configs`; integration на живом пути активации

**Closed 2026-06-28.** Резолв собран в `_flatten_region_defaults[T]` (общий хелпер для `battle_map_configs` и `effective_encounters` — дедуп, не копипаст); `ActivationManager` не тронут (резолв load-time). Integration: +3 теста (`tests/integration/test_encounters.py` + `encounter_world`) — fallthrough из региональной таблицы, override локационной, пустой регион без таблицы; suite 149 → 152 green (детерминизм через `chance: 1.0` + `count: [1,1]`, без сидов — encounter-ролл идёт мимо seeded dice RNG). Unit: 4 in-process продуктовых теста через `GameService` + реальные слои (`random` мокается). `make check` green (2237 backend, 238 frontend, mypy чисто). E2E: регрессия общего пути активация/раунд/бой (setup → peaceful: wait+move → combat), 12/12 pass, 0 blockers — [e2e/phase3-report.md](e2e/phase3-report.md). Пре-существующая мелочь (не фаза 3): смешанный EN/RU в game-строках (бэкенд `DND_LANGUAGE=ru`, UI-хром EN).

## Phase 4: Время суток (Time-of-Day Spawns) ✓

Encounter-таблицы тегаются временем суток: ночная встреча роллится только ночью, дневная — только днём, без тега — всегда (текущее поведение). День/ночь берётся из geography-слоя (`rules/geography.is_daylight`) через новый запрос `IS_DAYLIGHT`. Здесь же финальный E2E-цикл спринта.

**Решения по фазе (из планирования):**
- **Scope: только встречи.** Активность логов день/ночь вынесена в бэклог (`lair-time-of-day`); логова остаются always-active, пока `ACTIVE`.
- **Жёсткий гейт по тегу**, не множитель частоты (из двух вариантов фразы «только ночью либо с повышенной частотой» берём простой и детерминированно тестируемый).
- **Ролл встреч живёт в `ActivationManager` (entities), не в ecology** — формулировка «хук в ecology» неточна. Entities выше geography в стеке, запрос вниз легален, рефактор не нужен.
- `TimeOfDay(StrEnum)` (`day`/`night`) в `core/models.py`, общий для рантайма, контента и запроса. Невалидный тег падает на загрузке (Pydantic).
- Финальный полный E2E спринта (опасный регион → логово → убить ядро → казна → XP) выполняется при закрытии фазы через `/close-phase` → `/e2e`, отдельной задачей не оформляется.

**Verify:** integration. Промотать в ночь → ночная встреча выстреливает, днём нет. E2E полный цикл: пройти опасным регионом, найти логово, зачистить (убить ядро), вскрыть казну, получить XP.

**Tasks:**

1. [Time-of-day encounters](tasks/phase4-task1-time-of-day-encounters.md) — `TimeOfDay` enum, `IS_DAYLIGHT` geography query, `time_of_day` на encounter-схеме/рантайме/лоадере, чистое правило `is_active_at_time`, фильтр в `ActivationManager._roll_encounters`

**Closed 2026-06-28.** Day/night сигнал собран в geography (`IS_DAYLIGHT` резолвит location→region→latitude→`is_daylight`); `ActivationManager._is_daylight_at` дёргает его раз на ролл, фильтр через чистое `rules/encounters.is_active_at_time` (дефолт «день» при отсутствии geography — untagged никогда не подавляется). Integration: +2 теста (`TestTimeOfDayEncounter` на `encounter_world/night_marsh`) — пусто днём, спавн после `advance_time` в ночь; suite 152 → 154 green. Unit: 3 продуктовых (`test_time_of_day_encounters.py`) + 2 парсерных fail-fast/round-trip (`test_monster.py`); `make check` green (2245 backend, 238 frontend, mypy чисто). Старый тест обновлён намеренно: `test_manifest_game_service.test_locations` 6 → 7 (в `test_vale` добавлен `night_hollow`). E2E (sprint018-phase4): фича подтверждена вживую на запущенном сервере — `night_hollow` пусто в 10:00, Bandit в 02:00 (логи: `encounter_roll_off_hours` днём, `is_day:false` + спавн ночью); регрессия setup→peaceful→combat→loot→reputation 9/9, 0 блокеров ([e2e/phase4-report.md](e2e/phase4-report.md)). Фундамент (`TimeOfDay`/`IS_DAYLIGHT`/`is_active_at_time`) переиспользуем отложенным `lair-time-of-day`. Пре-существующие мелочи (не фаза 4): смешанный EN/RU в game-строках; мёртвое существо держит Attack/Talk в Nearby; после килла нужен End Turn до peaceful-move.

---

## Results

**Completed:** 2026-06-28

Все 4 фазы закрыты. Монстры теперь населяют мир независимо от игрока, опасность фиксирована местом и временем (кенши-стиль, без авто-скейлинга под уровень партии). Закрыт backlog must-айтем `monster-spawn`.

- **Phase 1 — Лога:** `core/lair.py` (`Lair`/`LairState`), машина `ACTIVE → DEPLETED`, материализация ростера при входе, респавн на тике ecology, смерть ядра деплитит навсегда + опц. `depletion_chance`, переживает save/load.
- **Phase 2 — Лут и контейнеры:** `InventoryHolder` Protocol + `is_lootable`, `Container`-сущность (`EntityKind.CONTAINER`), общий `transfer_items` (торговля переведена на него), action `take` (take-all) + LootPanel, казна логова за ядром. Попутно: фикс WS-disconnect deadlock (`asyncio.to_thread`).
- **Phase 3 — Региональные таблицы встреч:** `region_encounters` по region_id, fallthrough локация→регион + override, резолв load-time через общий `_flatten_region_defaults`.
- **Phase 4 — Время суток:** `TimeOfDay` enum, geography `IS_DAYLIGHT` query, тег `time_of_day`, чистое `is_active_at_time`, фильтр в `ActivationManager`.

**Метрики:** integration 142 → 154 green; `make check` зелёный (2249 backend unit, 238 frontend, mypy чисто). Аудит 2026-06-28 (12 находок) триажирован. Post-audit E2E: loot/take/combat/reputation/encounters зелёные; найден и исправлен 1 блокер — brand-new сессия показывала «GAME OVER» (раунд-луп слал `on_game_over` при административном `stop()` на StrictMode-disconnect); фикс `Round.is_stopped` гейт + `_on_session_empty` перепроверяет `has_listeners()` (+5 unit-тестов).

**Deferred (в бэклог):** `loot-drops-monsters`, `theft`, `container-hp-locks`, `lair-actions`, `lair-new-leader`, `spawn-event-trigger`, `lair-time-of-day` (фичи); `encounter-spawned-perceiver`, `combat-log-i18n-gaps`, `session-disconnect-debounce`, `corpse-nearby-actions` (находки E2E/полиш).

## Status

**Current:** CLOSED 2026-06-28.

## Decisions

- **Мир не подстраивается под игрока (кенши-стиль).** Отказались от CR-budget / авто-скейлинга встреч под уровень партии. Опасность фиксирована местом и временем; игрок сам оценивает риск. Соответствует VISION.
- **Логово как машина состояний `active → depleted`, не как respawn-логика.** «Не восстановилось» это терминальный стейт, в который ведут разные триггеры, а не спецслучай. Строим стейт-машину сразу в Фазе 1.
- **Триггер деплита: ядро (core/boss) детерминированно — основной; `depletion_chance` — опция.** Детерминированное «убей босса = зачистил» легибельнее и даёт агентность; чистый шанс ощущается произвольно. «После смерти ядра поднимается новый вожак» отложено в бэклог (`lair-new-leader`).
- **`Lootable` это производное состояние, а не класс.** Труп остаётся `Creature` (`is_lootable()` = производная от `alive`), что бесплатно даёт воскрешение и «осмотреть труп». Универсальный субстрат это `InventoryHolder` (Protocol); `Container` это `Entity`-сосед `Creature`.
- **Лут, торговля и воровство это три отдельных режима доступа над одним примитивом `transfer_items`.** Loot — пассивный источник без согласия; trade — согласие + цена; theft — contested-проверка. Не сливаем в один путь, чтобы `take` не оброс ветками. Воровство отложено в бэклог (`theft`).
- **Порядок фаз: логова → лут → регион → время.** Казна это фича логова, а примитив переноса полезно иметь рано, поэтому лут идёт второй фазой.

## Deferred

В бэклог (секция Gameplay), вместе с планом спринта:

- `loot-drops-monsters` (should) — общемонстровый дроп: loot-таблицы на шаблонах монстров, корпс-лут с обычных мобов поверх `take`
- `theft` (should) — воровство как отдельный режим доступа поверх `transfer_items`
- `container-hp-locks` (could) — сундуки с замком/HP (взлом, «разбить»)
- `lair-actions` (could) — D&D lair actions на ядре логова
- `lair-new-leader` (could) — шанс поднять нового вожака вместо деплита после смерти ядра
- `spawn-event-trigger` (should) — event-триггер спавна, в связке со спринтом квестов
- `lair-time-of-day` (could) — активность логова варьируется день/ночь (`active_at: day|night` гейтит материализацию ростера); переиспользует `TimeOfDay`/`IS_DAYLIGHT`/`is_active_at_time` из фазы 4 (отложено при планировании фазы 4)
