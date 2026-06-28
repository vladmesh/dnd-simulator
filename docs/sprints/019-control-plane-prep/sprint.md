# Sprint 019 — Control-Plane Prep

**Goal:** Отвердить control-plane (GameService / session / commands / адаптеры) под будущий разрез на роли: раздробить god-class GameService, покрыть тестами session/commands/routes, вынести `get_world_state` и утончить адаптеры — попутно закрыв видимые дырки (i18n-лог, encounter-perceiver, труп-кнопки) и сведя бэклог.

**Started:** 2026-06-28

## Context

Техспринт после продуктового 018. База здоровая (аудит 2026-06-28 — 12 находок, почти все low/could, ноль архитектурных нарушений), так что это не тушение пожара, а целенаправленная подготовка к **следующему спринту** — `control-interfaces`.

`control-interfaces.md` формулирует три управляющих интерфейса (worldbuilder / DM / админка) как **три линзы над одним ядром** — `content_loader` + `GameService` + `session`, а не три приложения. Следующий спринт будет резать именно этот кластер по ролям. Сегодня он в плохой форме для такого разреза:

- `service/game_service.py` — **1044 строки**, god-class facade, без выделенных тестов.
- `service/session.py` — 536 строк, **0** unit-тестов (spectator-listener поедет сюда).
- `service/commands_time/politics/save.py` — **0** тестов (это и есть DM hot-controls / policy-поверхность).
- `adapters/routes_session.py` — оркестрирует 7+ layer-queries напрямую + assert-based валидация (`thick-adapter-world-state`).

Рефакторить непокрытый god-class в три проекции — способ занести регрессии. Спринт отвердит этот срез: тесты сначала, потом глубокий peel, потом видимая полировка.

Решения планирования: акцент — control-plane prep + bug sweep; глубина рефактора — **deeper peel** (реально уменьшить 1044 строки, не только косметика), но дисциплинированно — под защитой тестов из фазы 1.

**Out of scope** (это уже сам `control-interfaces` или позже): identity / roles / auth, spectator-listener, мультиплеер, любая новая gameplay/LLM/контент-фича. Большие type-свипы (`any-to-object-sweep`, `dict-str-object-overuse`) остаются в бэклоге.

**Ссылки:** [control-interfaces](../../brainstorms/control-interfaces.md), [BACKLOG](../../BACKLOG.md), [audit](../../audit.md), [VISION](../../VISION.md)

## Phase 1: Session lifecycle test net ✓

**Closed 2026-06-28.** Все 3 таски `done`; integration 154/154 зелёный; E2E (`e2e/phase1-report.md`) — 9/9, ноль блокеров (находки преэкзистинг minor: `spawn-role-freetext-enum`, mixed-language race, dev-only WS StrictMode race). `get_world_state` happy-path и SchemaForm (memoize-фикс) подтверждены через UI; `make check` зелёный. Доп: убраны 2 преэкзистинг eslint-варнинга в `SchemaForm.tsx`.

**Перескоплено при планировании (2026-06-28).** Исходный headline фазы — «вынести `GameService.get_world_state()`» — **уже сделан** (sprint 016: `commands_world_state.py`, адаптер `routes_session.py:55-60` это 6-строчный делегат) **и покрыт тестами** (`test_commands_world_state.py`). Несколько перечисленных test-gap тоже оказались устаревшими: `test_commands_politics.py` и `test_autosave_all.py` существуют; `advance_time` — тонкий 1-строчный враппер с 7 integration-ссылками. `thick-adapter-world-state` и эти test-gap помечаются fixed в фазе 3 (сверка бэклога).

Реальная незакрытая дыра, и именно на поверхности, которую трогает peel фазы 2 и spectator-listener следующего спринта: **round-lifecycle и listener-dispatch в `session.py`** (`add_listener`/`remove_listener`/`start_round`/`stop_round`/`_fire`/`submit_*`/`resolve_abstract_move` — 0 выделенных тестов; покрыты только serialization-хелперы). Плюс мелкие: `commands_save.load_game`/`list_saves`/`delete_save` (0 unit) и fail-fast вместо `assert` в `get_world_state`.

Фаза = characterization-сетка на этот срез (плюс одно маленькое поведенческое ужесточение get_world_state). Это защитная сетка под глубокий peel фазы 2.

**Verify:** новые unit-тесты на session lifecycle/listener + commands_save зелёные (characterization — проходят сразу); get_world_state на битых данных слоя кидает понятную типизированную ошибку, не `AssertionError`/500; `make check` зелёный.

**Tasks:**

1. [Session listener dispatch + abstract-move resolution](tasks/phase1-task1-session-listener-dispatch.md) — синхронная сетка: listener dispatch, empty→`_on_empty`, submit-raises-when-idle, все ветки `resolve_abstract_move`
2. [Session round lifecycle](tasks/phase1-task2-session-round-lifecycle.md) — `start_round` идемпотентность + wiring PlayerBrain + живой thread; `stop_round` чистит стейт + join; submit после старта
3. [commands_save round-trip + get_world_state hardening](tasks/phase1-task3-save-commands-worldstate-hardening.md) — `load_game`/`list_saves`/`delete_save` через реальный `JsonFileStore`; `assert isinstance` → явный fail-fast с именем слоя/запроса

## Phase 2: GameService deeper peel + adapter hygiene ✓

**Closed 2026-06-29.** Все 3 таски `done`; integration 154/154 зелёный; E2E (`e2e/phase2-report.md`) — 18/18, ноль блокеров. GameService 1044 → 357 строк (`WorldBuilderCommands` + `PlayerCommands` mixins); `parse_action`/`ActionParseError` вынесены в `service/action_parsing.py` (routes_ws больше не импортирует `Action`/`ActionType` из core); `World.make_query_fn`/`make_emit_fn` сделаны public. Три backlog-айтема помечены fixed: `action-parsing-in-adapter`, `world-private-method-access`, `adapter-imports-core-directly`. E2E подтвердил поведение сохранено на всех трёх peel-поверхностях (char creation / WS-actions / worldbuilder+creature CRUD); все находки преэкзистинг (F1 `spawn-role-freetext-enum`, F2 i18n-split, F3 dev-only WS StrictMode race, + косметика `corpse-nearby-actions`), ноль регрессий. `make check` зелёный, mypy чисто.

Структурный выигрыш. Раздробить оставшиеся command/query-группы GameService в суб-фасады, чтобы заметно опустить 1044 строки. Убрать прямые импорты `core` из адаптеров (`adapter-imports-core-directly`), вынести парсинг `Action` из JSON в сервис (`action-parsing-in-adapter`), выставить `World`-query как public API (`world-private-method-access`: `world._make_query_fn()` зовётся из session/round). Тесты фазы 1 стерегут поведение.

**Verify:** integration зелёный (поведение сохранено), число строк GameService падает, mypy чисто.

**Перескоплено при планировании (2026-06-28).** Worldbuilder-templates и content/catalog-CRUD объединены в один mixin (`WorldBuilderCommands`) — у них общие приватные хелперы (`_validate_world_id`, `_resolve_layer_path`, `_resolve_entity_layer_path`), разрезать = протокол-черн. Это и есть «worldbuilder lens» для `control-interfaces`. Peel: ~500 (worldbuilder+content) + ~176 (player) строк → GameService 1044 → ~370. `adapter-imports-core-directly` решён прагматично (решение планирования): из core-импортов в адаптерах удаляется только `Action/ActionType` (через вынос парсинга), `BrainType`/`FightingStyle` остаются как enum-at-boundary в Pydantic-схемах (аудит 2026-06-28: 0 арх-нарушений, адаптерам можно импортировать enum).

**Tasks:**

1. [Peel worldbuilder + content CRUD](tasks/phase2-task1-worldbuilder-commands-peel.md) — `WorldBuilderCommands` mixin (~500 строк): world templates/manifest + layer-files + entity/catalog CRUD; `_content_dir`/`_validate_world_id` в протокол
2. [Peel player commands](tasks/phase2-task2-player-commands-peel.md) — `PlayerCommands` mixin (~176 строк): create_player/level_up_player/player_status
3. [Adapter hygiene](tasks/phase2-task3-adapter-hygiene.md) — `action-parsing-in-adapter` (вынос в `service/action_parsing.py` + типизированная ошибка) + `world-private-method-access` (public `make_query_fn`/`make_emit_fn`) + сверка бэклога

## Phase 3: Visible gaps + backlog reconcile + dead code ✓

**Closed 2026-06-29.** Все 3 таски `done`; integration 154/154 зелёный; E2E (`e2e/phase3-report.md`) — 6/6, ноль NEW-блокеров. Все три видимых фикса подтверждены в живом UI под RU-сессией: (1) **combat-log i18n** — строка атаки рендерится по-русски «Ты атакуешь человек (longsword slash) [d20(13)+2=15 vs КЗ 10], 4 урона (1d8 рубящий)», без утечки плейсхолдеров `{oa}`/`{weapon}`, плюс RU для combat-start/смерти/репутации/конца боя (catalog-drift фикс работает); (2) **encounter-perceiver** — лог показывает «Поблизости что-то шевелится» (RU-флейвор), НЕ фоллбэк «Something happened», ростер скрыт (нет утечки имён мобов), бэкенд-лог: 5 `encounter_spawn`, ноль «Something happened»; (3) **corpse-nearby-actions** — у трупа в панели «Поблизости» только Inspect (нет Атаковать/Говорить), лут через панель «Добыча». Movement-handler ошибки (`movement.py`, 9 строк в `_()`, em-dash убраны) покрыты 2 новыми unit-тестами + RU-каталог доказан вживую на трёх независимых группах строк. `make check` зелёный (backend 2267, frontend 240, mypy чисто). Находки — преэкзистинг minor: dev-only WS StrictMode race, английские item/faction-имена внутри RU-строк (вне скоупа фазы, кандидат в i18n-свип). Латентный баг `player-xp-not-persisted` занесён в BACKLOG как should (вне гранулы).

Закрыть видимую грязь: `combat-log-i18n-gaps` (код-баг `rules/handlers/movement.py` — сырые английские `error=...` без `_()`, em-dash на строке 56; + дрейф каталога через `make messages`/`compile-messages`), `encounter-spawned-perceiver` (мусорный «Something happened» в логе на каждый спавн), `corpse-nearby-actions` (скрыть Attack/Talk у трупа), `look-action-i18n-hardcode`. Удалить мёртвый код (`dead-refund`, `dead-walk-path`, `dead-prone-stand-cost`, `dead-to-save-data`, `dead-can-opportunity-attack`). Свести бэклог: пометить `battle-map-configs-not-wired` и `player-character-no-attacks` как fixed (проверено в коде при планировании).

**Verify:** E2E — чистый RU боевой лог, нет мусорной encounter-строки, нет кнопок на трупе; grep подтверждает удаление мёртвого кода; `make check` зелёный.

**Перескоплено при планировании (2026-06-29).** Код-ревью нашло два айтема фазы устаревшими: `look-action-i18n-hardcode` — `_cmd_look` уже удалён в раннем рефакторе (хардкод-строк «Terrain:»/«Weather:» в `service/` нет, остались только мусорные msgid в `.po`); `dead-can-opportunity-attack` — функция уже удалена (коммит 67f057b). Оба схлопываются в reconcile, не в работу. Оба reconcile-айтема подтверждены fixed в коде: `battle-map-configs-not-wired` (проводка `game_service.py:171-183`), `player-character-no-attacks` (стартовое снаряжение даёт оружие, симптом «дерётся кулаками» ушёл). Часть `combat-log-i18n-gaps` тоже устарела: `direction_label`/репутационные строки уже обёрнуты в `_()`, им нужна только регенерация каталога, не правка кода. Реальная работа: код-баг сырых `error=` в `movement.py` (+ em-dash) + дрейф каталога (`{oa}`) + перцептор encounter + фронт-гейт на трупах + удаление 4 мёртвых функций.

**Tasks:**

1. [Combat-log i18n + encounter perceiver](tasks/phase3-task1-combat-log-i18n-encounter-perceiver.md) — обернуть сырые `error=` в `movement.py` в `_()` (убрать em-dash); `_perceive_encounter_spawned` в `_DISPATCH`; один проход каталога (`make messages` → перевод RU → `make compile-messages`)
2. [Hide Attack/Talk on corpses](tasks/phase3-task2-corpse-nearby-actions.md) — фронт-гейт Attack/Talk на `!entity.lootable` в `Perception.tsx` (бэкенд уже отдаёт `lootable`)
3. [Dead-code removal + backlog reconcile](tasks/phase3-task3-dead-code-backlog-reconcile.md) — удалить `dead-refund`/`dead-walk-path`/`dead-prone-stand-cost`/`dead-to-save-data` (+ тесты); пометить fixed/obsolete `dead-can-opportunity-attack`, `battle-map-configs-not-wired`, `player-character-no-attacks`, `look-action-i18n-hardcode`

---

## Status

**Current:** CLOSED 2026-06-29. Все 3 фазы закрыты (Phase 1/2/3 ✓), аудит триажирован, post-audit E2E зелёный (0 NEW-блокеров), integration 154/154, `make check` зелёный. См. Results.

## Decisions

- **Техспринт целится в следующий спринт, а не просто в бэклог.** Из всего бэклога приоритет — кластер, который `control-interfaces` будет резать на роли (GameService / session / commands / master-routes). Отвердить его до разреза дешевле, чем чинить регрессии после.
- **Тесты раньше рефактора (фаза 1 → фаза 2).** Deeper peel god-class без сетки = занос регрессий. Сначала characterization + unit на поверхность, потом дробление.
- **Deeper peel, но дисциплинированный.** Пользователь поднял глубину с «небольшой рефактор» до реального дробления GameService; держим в рамках команд/query-групп под защитой тестов, без переписывания механик.
- **Identity/roles/spectator/мультиплеер — не сюда.** Это содержание самого `control-interfaces`; техспринт только готовит почву (тонкие адаптеры, сервисный get_world_state, развязка core/adapter).
- **Phase 1 перескоплена с «вынести seam» на «сетка на session.py» (2026-06-28).** При планировании фазы выяснилось: `get_world_state` уже вынесен и покрыт тестами (sprint 016), а `thick-adapter-world-state` + часть test-gap (`commands-politics`, autosave) устарели. Реальная незакрытая дыра — round-lifecycle/listener в `session.py` (0 тестов), ровно та поверхность, что трогает peel фазы 2 и spectator-listener следующего спринта. Headline фазы сменился, цель (сетка под peel) — нет.

## Deferred

- **should** `player-xp-not-persisted` — XP/`level_up_available` не переживают современный save/reload (`to_full_save_data` не сериализует `experience`); в dev усугубляется WS StrictMode evict→restore. Обнаружено в phase 3, занесено в BACKLOG, фикс вне скоупа техспринта (чинить с/после `session-disconnect-debounce`).
- Растущие модули из аудита (`round-growing`, `activation-manager-growing`, `action-defs-growing`, `perception-fail-fast`, `god-class-combat-manager`) — это combat/ecology/core, не control-plane. Отложены в будущий tech-sweep (триаж 2026-06-29).
- Преэкзистинг minor из E2E: dev-only WS StrictMode race, `spawn-role-freetext-enum`, английские item/faction-имена внутри RU-строк (кандидат в i18n-свип). Все в BACKLOG.

## Results

**Completed:** 2026-06-29

Техспринт достиг цели: control-plane отвердён под будущий разрез на роли в `control-interfaces`.

- **Тест-сетка (Phase 1):** characterization-сетка на `session.py` (listener dispatch, round lifecycle start/stop идемпотентность + brain wiring) + `commands_save` round-trip через реальный `JsonFileStore`; `get_world_state` теперь fail-fast с именем слоя/запроса вместо `AssertionError`/500.
- **Peel (Phase 2):** `GameService` 1044 → 357 строк. Команды разнесены в миксины `WorldBuilderCommands` (world/content/catalog CRUD) и `PlayerCommands` (create_player/level_up_player/player_status) поверх `GameServiceProtocol`. `parse_action`/`ActionParseError` вынесены в `service/action_parsing.py` — адаптеры больше не импортируют `Action`/`ActionType` из core. `World.make_query_fn`/`make_emit_fn` сделаны public. Три backlog-айтема (`action-parsing-in-adapter`, `world-private-method-access`, `adapter-imports-core-directly`) закрыты.
- **Видимые дырки (Phase 3):** combat-log i18n (сырые `error=` в `movement.py` обёрнуты в `_()`, em-dash убраны, прогон каталога убрал утечку `{oa}`), encounter-перцептор («Поблизости что-то шевелится» вместо утечки ростера/фоллбэка «Something happened»), фронт-гейт Attack/Talk на трупах (`!entity.lootable` в `Perception.tsx`). Удалены 4 мёртвые функции (`refund`/`walk_path`/`prone_stand_cost`/`to_save_data`). Сверка бэклога: 8 айтемов помечены fixed/obsolete.

**Метрики:** integration 154/154 на всех трёх close-phase; финальный post-audit E2E — 28 сценариев, 27 pass / 1 partial, 0 NEW-блокеров (`e2e-reports/2026-06-29-sprint019-post-audit.md`). Аудит 2026-06-29 — 17 находок, 0 new of note, 0 арх-нарушений; «healthiest control-plane state to date». `make check` зелёный (backend 2267, frontend 240, mypy чисто).

**Deferred:** см. раздел выше — главное `player-xp-not-persisted` (should).
