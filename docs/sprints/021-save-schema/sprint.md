# Sprint 021 — Save Schema & World Reproducibility

**Goal:** Мир сохраняется через единую версионированную Pydantic-схему сейва, симуляция воспроизводима от явного сида (RNG прокинут в слои, состояние RNG в сейве), автосейв периодический и не глушит ошибки.

**Started:** 2026-07-10

## Context

Первый эпик цепочки simulation-core: `save-schema` → `anchor-as-property`/`intents` → `trigger-table` → ... «Мир заморожен на полушаге» требует lossless-сейва, а значит единой схемы вместо рукописных dict-ов, размазанных по `commands_save` / `World.save` / пяти `get_state()`. Почва подготовлена Sprint 020 phase 3 (format-preserving дедуп, `entity_serialization.py`).

Вторая половина — воспроизводимость: encounter rolls, roam movement и retreat selection сидят на процесс-глобальном `random` (`layers/entities/encounters.py`, `layers/ecology/movement.py`, `layers/ecology/squad_combat.py`), `PoliticsLayer`/`GeographyLayer` принимают seed, но `game_service` его не передаёт, `DND_DICE_SEED` сидит только dice-RNG. Флак PR #31 (осиротевшие раунды сдвигали глобальный RNG) — живая иллюстрация. Без явного RNG состояние генератора нечем класть в сейв.

Закрываемые backlog-айтемы: `save-schema` (must), `layer-rng-threading`, `test-gap-world-rng-determinism`, `periodic-autosave-scheduler`, `silent-failure-autosave`; попутно минимальный фикс `saved-session-accumulation` (чистка saves/ в teardown интеграционных тестов).

**Ссылки:** [simulation-core](../../brainstorms/simulation-core.md), [BACKLOG](../../BACKLOG.md#simulation-core-брейншторм-2026-07-04), [020 phase3 serialization dedup](../020-thermo-sweep/tasks/phase3-task1-serialization-dedup.md)

## Phase 1: RNG threading & determinism ✓

Единый world-seed: RNG создаётся на уровне World/сессии и прокидывается в слои через конструкторы (расширение существующего паттерна `PoliticsLayer(seed)` / `WeatherEngine(seed)`; `EcologyLayer` получает seed впервые). Три bare-`random` сайта (encounters, roam movement, retreat) переводятся на слоевой RNG. `game_service` реально передаёт сиды (env `DND_WORLD_SEED`, по умолчанию случайный). Тесты детерминизма: одинаковый сид → идентичная эволюция мира (encounter rolls, движение сквадов, retreat), разный сид → расходится.

Проверка: `make test`, новые unit-тесты детерминизма зелёные. Почему первым: без явного RNG его состояние не положить в схему сейва (phase 2).

**Tasks:**

1. [World seed plumbing](tasks/phase1-task1-world-seed-plumbing.md)
2. [Миграция bare-random сайтов на слоевой RNG](tasks/phase1-task2-bare-random-migration.md)
3. [Сквозной тест воспроизводимости мира](tasks/phase1-task3-world-determinism-test.md)

## Phase 2: Unified Pydantic save schema ✓

Pydantic-модели сейва (`SaveGame`: `schema_version`, `meta`, `world{time, last_tick_times, layers}`) как единый source of truth. Слои отдают/принимают типизированные модели вместо сырых dict-ов; `entity_serialization` переезжает на модели. Состояние RNG (dice + per-layer) сериализуется в сейв — загрузка продолжает ту же случайную последовательность. Единый путь загрузки в `commands_save`: `schema_version=1`, legacy-фолбэки (три исторических формата) удаляются — сейвы dev-артефакты. Round-trip тесты перепиниваются на новый формат.

Проверка: `make test-integration` (round-trip сьют), ручная проверка save→load→continue в UI. Почему вторым: схема фиксирует то, что phase 1 сделал явным.

**Tasks:**

1. [Типизированные state-модели простых слоёв + RNG в состоянии](tasks/phase2-task1-layer-state-models.md)
2. [Entities-слой на Pydantic-моделях сейва](tasks/phase2-task2-entities-state-model.md)
3. [SaveGame-конверт, schema_version=1, единый путь загрузки](tasks/phase2-task3-save-envelope.md)
4. [Entities save-модели — source of truth, не обёртка](tasks/phase2-task4-entities-models-source-of-truth.md)

## Phase 3: Autosave hardening

Периодический автосейв: фоновый asyncio-таск в FastAPI lifespan (интервал env `DND_AUTOSAVE_SECONDS`, default ~120), cancel на shutdown перед финальным autosave. Ошибки автосейва логируются вместо `contextlib.suppress(Exception)` (3 сайта). Минимальный фикс накопления: интеграционные тесты чистят созданные сессии в `saves/` в teardown.

Проверка: unit-тест шедулера (старт/останов/интервал), `make test-integration`, `saves/` не растёт после прогона. Почему последним: частый автосейв имеет смысл только поверх надёжной схемы.

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- Legacy-форматы сейва (без `meta`, flat-world, top-level `player`) удаляются без миграции: сейвы — dev-артефакты, `schema_version=1` стартует с чистого листа (2026-07-10).
- RNG-паттерн: унифицируем на layer-constructor-owned `random.Random(seed)` (существующий Pattern B), сиды раздаёт World/сессия из одного world-seed; dice-RNG (`rules/dice.py`) остаётся отдельным потоком, но его состояние тоже попадает в сейв (2026-07-10).
- Ревью phase 2 task 2: принятая воркером обёртка (`extra="allow"` + рукописный `serialize_entity`) отклонена — модели обязаны быть source of truth (иначе intents/триггеры снова допишут рукописный формат); переработка выделена в task 4. Там же закрывается найденный на ревью lossless-пробел: `CombatState.sides` не сериализуется (2026-07-10).
- Phase 1 закрыта без отдельного E2E: пользовательской поверхности нет (RNG plumbing), integration 160 passed; браузерный E2E идёт на закрытии phase 2/3 (2026-07-10).
- Legacy `World.save()` уже пишет `seed`, чтобы разные world-seed snapshots различались до ввода Pydantic save schema; полное состояние RNG остаётся задачей phase 2 (2026-07-10).

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
