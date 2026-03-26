# Sprint 007 — World Builder + Session Robustness

**Goal:** Мир можно форкнуть и редактировать через UI, сессии надёжно сохраняются и восстанавливаются без потери данных, мастер имеет полный набор hot controls.

**Started:** 2026-03-26

## Context

Sprint 006 заложил фундамент world builder: библиотека шаблонов, манифест, wizard, fork API. Но UI для fork/edit отсутствует, и есть только один набор шаблонов — wizard фактически создаёт копию sword_vale. Fork+editor дадут реальную кастомизацию без необходимости создавать новые шаблоны.

Параллельно: save/load имеет дыры в сериализации (resource pools, combat state, generic creature brain type). Autosave/restore работает, но не гарантирует идентичность состояния. Master controls почти все реализованы на бэкенде, но give_item не exposed в UI.

**Ссылки:** [sprint 006](../006-layer-composition/sprint.md), [world-builder plan](../../plans/world-builder.md), [VISION.md](../../VISION.md)

---

## Phase 1: Save/Load Completeness

Фиксим дыры в сериализации: resource pools (Second Wind и др. сбрасываются при загрузке), combat state (graceful exit при save — корректно завершаем бой, не теряем молча), generic creature brain type. Unit-тесты: save → load → assert state identical для каждого слоя. E2E: start game → perform actions → save → load → verify state preserved.

**Верифицируем:** unit-тесты на round-trip сериализацию всех слоёв, E2E сценарий save/load.

**Tasks:**

1. [Serialize Resource Pools & NPC ai_type](tasks/phase1-task1-resource-pools-ai-type.md)
2. [Serialize Combat State (Mid-Combat Save/Load)](tasks/phase1-task2-combat-state-serialization.md)
3. [Full Layer Round-Trip Integration Tests](tasks/phase1-task3-full-roundtrip-tests.md)

## Phase 1.5: Save/Load Gaps (найдено при интеграционном тестировании) ✓

Phase 1 закрыла основные дыры, но интеграционные тесты на живом стеке выявили проблемы, которые не ловятся unit-тестами. Цель: RED-GREEN — написать тесты которые сейчас падают, починить код, сделать зелёными.

### Найденные проблемы

**1. Spawned creatures теряются при load**
- `load_state()` обновляет только entity, которые уже есть в `self._entities` (загруженные из YAML контентом).
- Если creature был заспавнен через `POST /creatures` (master API), он сохраняется в save-файл, но при load его нет в свежем слое — данные молча игнорируются.
- Тест: spawn goblin → save → delete goblin → load → goblin должен вернуться. Сейчас: 404.
- Причина: `load_state()` не умеет создавать entity из saved data (кроме PlayerCharacter, для которого есть `parse_player`).

**2. Brain switch не тестируется в интеграции (нет LLM в test env)**
- `PUT /creatures/{id}/brain` с `type=llm` вызывает `BrainFactory.create("llm", strict=True)`, что требует `OPENROUTER_API_KEY`.
- В docker compose для тестов LLM отсутствует → 400 при попытке переключить.
- Нужно: либо `strict=False` при brain switch (fallback на RuleBrain если LLM недоступен), либо mock/stub LLM brain для тестов, либо тестировать только rule_based→rule_based round-trip (бессмысленно).
- Решение: `BrainFactory.create` должен принимать `strict=False` по умолчанию для set_brain, а `strict=True` только при первоначальном создании из YAML. Тогда в save хранится `ai_type="llm"`, при load создаётся RuleBrain с warning если LLM недоступен, а при следующем brain switch уже с LLM — будет работать.

**3. Spawned creatures не получают brain при load**
- Даже если починить проблему #1, у восстановленного creature не будет brain (brain не сериализуется — это transient field).
- Нужно: при восстановлении creature из saved data, вызывать `BrainFactory.create(ai_type)` для назначения brain.
- Проблема: `EntitiesLayer` не знает про `BrainFactory` (это зависимость service уровня). Нужно либо инжектить factory в слой, либо восстанавливать brain в service при load.

**Верифицируем:** все xfail-тесты в `test_save_roundtrip.py` стали зелёными, новый тест на spawned creature round-trip зелёный.

**Tasks:**

1. [Recreate Spawned Entities from Save Data](tasks/phase1.5-task1-recreate-spawned-entities.md)
2. [Reassign Brains After Load](tasks/phase1.5-task2-brain-reassignment-after-load.md)
3. [Integration Tests — Spawned Creature & Brain Switch Round-Trip](tasks/phase1.5-task3-integration-tests.md)

## Phase 2: Master Controls + Give Item UI ✓

Give Item кнопка в creature panel (бэкенд endpoint существует, нет UI). API client method + React компонент. Ревью остальных master controls на предмет gaps между бэкендом и фронтом. E2E: master spawns creature, gives item, verifies equipment.

**Верифицируем:** все существующие master endpoints доступны через UI, E2E сценарий master workflow.

**Tasks:**

1. [Give Item API Plumbing — Backend Response + TS Types + Client Method](tasks/phase2-task1-give-item-api-plumbing.md)
2. [Give Item Dialog UI](tasks/phase2-task2-give-item-dialog.md)
3. [E2E — Master Spawns Creature, Gives Item, Verifies Equipment](tasks/phase2-task3-e2e-master-workflow.md)

## Phase 3: Fork UI + World Inspector ✓

API plumbing (manifest endpoint, TS types, client methods) + WorldInspector component с fork кнопками. Компонент работает, но размещён на player-facing WorldPicker — неправильно. Перенос в MasterScreen → phase 3.5.

**Tasks:**

1. [World Manifest API + TS Types + Client Methods](tasks/phase3-task1-manifest-api-plumbing.md)
2. [World Inspector UI on Setup Screen](tasks/phase3-task2-world-inspector-ui.md)
3. [E2E — Fork Workflow via World Inspector](tasks/phase3-task3-e2e-fork-workflow.md)

## Phase 3.5: Move Fork UI to Master Screen ✓

WorldInspector + Fork — мастерская функциональность, не игроцкая. Игрок на setup screen выбирает мир и играет. Мастер на `/master` управляет мирами и сессиями — туда и идёт инспектор слоёв.

1. Убрать "Layers" кнопку и WorldInspector из WorldPicker
2. Добавить WorldInspector в MasterScreen (под world selector)
3. E2E — fork workflow через `/master`

**Верифицируем:** WorldPicker чистый (только карточки + New Session), WorldInspector с fork доступен на /master, fork workflow работает.

**Tasks:**

1. [Move WorldInspector from WorldPicker to MasterScreen](tasks/phase3.5-task1-move-inspector-to-master.md)
2. [E2E — Fork Workflow via Master Screen](tasks/phase3.5-task2-e2e-master-fork.md)

## Phase 4: Layer Editor ✓

Новый API: чтение и запись YAML-файлов форкнутых (custom) слоёв. Frontend: code editor для YAML (только custom слои, library — read-only). Валидация YAML на бэкенде перед сохранением. E2E: fork → edit YAML → create session → verify changes applied in game.

**Верифицируем:** можно отредактировать YAML форкнутого слоя через браузер, изменения отражаются в новой сессии.

**Tasks:**

1. [Layer Files Read/Write API](tasks/phase4-task1-layer-files-api.md)
2. [Layer Editor UI](tasks/phase4-task2-layer-editor-ui.md)
3. [E2E — Fork, Edit YAML, Create Session, Verify Changes](tasks/phase4-task3-e2e-layer-editor.md)

## Phase 5: Backend — Partial Worlds + World Management API

Манифест поддерживает неполные миры (часть слоёв undefined). Новые эндпоинты: форк мира целиком, создание пустого custom слоя (scaffold), удаление мира, флаг `complete` в списке миров. Только complete миры можно запускать в сессию.

**Контекст:** Phases 1–4 дали fork+edit для отдельных слоёв. Но создать мир с нуля или форкнуть мир с обрезкой верхних слоёв невозможно — manifest требует все 5 слоёв. Это блокирует объединение DM-механик в единый UX.

**Scope:**

1. **Partial manifest** — `resolve_manifest()` не крашится на undefined слоях; `layers.{type}: null` или отсутствие ключа = undefined слой. `start_game()` отказывает для incomplete миров.
2. **`complete` флаг** — `GET /api/master/worlds` возвращает `complete: bool` для каждого мира. complete = все 5 слоёв defined и резолвятся.
3. **Scaffold для нового слоя** — `POST /api/master/worlds/{world_id}/layers/{layer_type}/scaffold` создаёт минимальный custom слой (пустой но валидный YAML: пустой regions.yaml для geography, пустой nations.yaml для politics и т.д.). Обновляет manifest: source → custom.
4. **Форк мира** — `POST /api/master/worlds/{world_id}/fork` → создаёт копию мира с новым id. Опциональный param `from_layer` (geography|politics|settlements|ecology|entities) — всё от этого слоя и выше обрезается (становится undefined в манифесте копии). Library ссылки сохраняются (файлы не копируются).
5. **Удаление мира** — `DELETE /api/master/worlds/{world_id}`. Запрет на удаление base миров (sword_vale) и миров с активными сессиями.
6. **Интеграционные тесты** — partial manifest resolution, create session rejected for incomplete world, scaffold creates valid layer, fork world + fork with truncation, delete world + delete blocked.

**Верифицируем:** можно создать неполный мир, дополнить его scaffold-слоями по одному, и только после заполнения всех 5 слоёв запустить сессию. Форк мира с обрезкой создаёт draft, который можно доделать.

**Tasks:**

1. [Partial Manifest + Complete Flag + Create Empty World](tasks/phase5-task1-partial-manifest.md)
2. [World Fork + Delete Endpoints](tasks/phase5-task2-world-fork-delete.md)
3. [Layer Scaffold Endpoint](tasks/phase5-task3-layer-scaffold.md)

## Phase 6: Frontend — DM/Player Restructure

Главная страница разделена на Player и DM входы. Player: выбор complete мира → сессия → персонаж. `/master` перестроен: вкладки Worlds (список с fork/edit/delete, экран редактирования мира как stepper по слоям) и Sessions (текущий функционал). Scaffold UI для создания слоя с нуля.

**Контекст:** Сейчас механики мастера разбиты: создание мира на главной (визард выбора шаблонов), fork/edit — на `/master`. Создание мира бесполезно (один набор шаблонов). Редактирование — голый YAML. Нужно собрать всё в единый DM UX с понятным pipeline.

**Scope:**

1. **Главная страница** — два входа: "Играть" (→ WorldPicker только complete миры → создание/выбор сессии → персонаж) и "Мастерская" (→ `/master`). Убрать кнопку "Build Custom World" из player flow.
2. **`/master` — вкладки Worlds / Sessions** — Sessions: текущий список сессий с hot controls (перенос существующего). Worlds: таблица миров со столбцами name, status (complete/draft), type (base/custom), actions (fork/edit/delete).
3. **Экран редактирования мира** — клик по миру → stepper/pipeline из 5 слоёв. Каждый слой: defined (library badge + view/fork) или defined (custom badge + edit) или undefined (кнопки "выбрать шаблон" / "создать с нуля"). Объединяет WorldBuilder + WorldInspector.
4. **Scaffold UI** — "создать с нуля" открывает минимальную форму (название + базовые поля для типа слоя), вызывает scaffold API, затем открывает YAML editor для доработки.
5. **Кнопка "Создать мир"** — на вкладке Worlds. Вводишь id/name/description → создаёт пустой мир (все слои undefined) → открывает экран редактирования.
6. **E2E** — player видит только complete миры; DM создаёт мир с нуля (scaffold + edit), форкает существующий, доводит draft до complete, запускает сессию.

**Верифицируем:** полный цикл DM: создание пустого мира → scaffold слоёв → edit → запуск сессии. Полный цикл Player: видит только готовые миры, выбирает, играет. Fork мира через UI.

---

## Status

**Current:** Phase 4 complete. Phase 5 ready for task generation.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
