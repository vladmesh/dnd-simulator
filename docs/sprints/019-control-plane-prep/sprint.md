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

## Phase 1: World-state seam + hot-control test net

Вынести `GameService.get_world_state()` — снапшот мира живёт в сервисе, а не в адаптере (`thick-adapter-world-state`: `routes_session` сейчас сам дёргает 7+ layer-queries с assert-валидацией). Покрыть тестами live-session control-поверхность, на которой это сидит: `session.py` (listener dispatch, round lifecycle), `commands_time/politics/save`, master/content-роуты. Это защитная сетка под глубокий peel фазы 2.

**Verify:** characterization-тест фиксирует поведение world-state эндпоинта без изменений; новые unit-тесты на session/commands/routes зелёные; `make check` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: GameService deeper peel + adapter hygiene

Структурный выигрыш. Раздробить оставшиеся command/query-группы GameService в суб-фасады, чтобы заметно опустить 1044 строки. Убрать прямые импорты `core` из адаптеров (`adapter-imports-core-directly`), вынести парсинг `Action` из JSON в сервис (`action-parsing-in-adapter`), выставить `World`-query как public API (`world-private-method-access`: `world._make_query_fn()` зовётся из session/round). Тесты фазы 1 стерегут поведение.

**Verify:** integration зелёный (поведение сохранено), число строк GameService падает, mypy чисто.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Visible gaps + backlog reconcile + dead code

Закрыть видимую грязь: `combat-log-i18n-gaps` (код-баг `rules/handlers/movement.py` — сырые английские `error=...` без `_()`, em-dash на строке 56; + дрейф каталога через `make messages`/`compile-messages`), `encounter-spawned-perceiver` (мусорный «Something happened» в логе на каждый спавн), `corpse-nearby-actions` (скрыть Attack/Talk у трупа), `look-action-i18n-hardcode`. Удалить мёртвый код (`dead-refund`, `dead-walk-path`, `dead-prone-stand-cost`, `dead-to-save-data`, `dead-can-opportunity-attack`). Свести бэклог: пометить `battle-map-configs-not-wired` и `player-character-no-attacks` как fixed (проверено в коде при планировании).

**Verify:** E2E — чистый RU боевой лог, нет мусорной encounter-строки, нет кнопок на трупе; grep подтверждает удаление мёртвого кода; `make check` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **Техспринт целится в следующий спринт, а не просто в бэклог.** Из всего бэклога приоритет — кластер, который `control-interfaces` будет резать на роли (GameService / session / commands / master-routes). Отвердить его до разреза дешевле, чем чинить регрессии после.
- **Тесты раньше рефактора (фаза 1 → фаза 2).** Deeper peel god-class без сетки = занос регрессий. Сначала characterization + unit на поверхность, потом дробление.
- **Deeper peel, но дисциплинированный.** Пользователь поднял глубину с «небольшой рефактор» до реального дробления GameService; держим в рамках команд/query-групп под защитой тестов, без переписывания механик.
- **Identity/roles/spectator/мультиплеер — не сюда.** Это содержание самого `control-interfaces`; техспринт только готовит почву (тонкие адаптеры, сервисный get_world_state, развязка core/adapter).

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
