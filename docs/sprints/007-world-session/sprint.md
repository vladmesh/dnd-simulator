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

## Phase 2: Master Controls + Give Item UI

Give Item кнопка в creature panel (бэкенд endpoint существует, нет UI). API client method + React компонент. Ревью остальных master controls на предмет gaps между бэкендом и фронтом. E2E: master spawns creature, gives item, verifies equipment.

**Верифицируем:** все существующие master endpoints доступны через UI, E2E сценарий master workflow.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Fork UI + World Inspector

На setup screen — возможность посмотреть структуру мира (какие слои library, какие custom). Кнопка Fork на каждом слое. API endpoint `POST /worlds/{id}/fork/{layer_type}` уже есть — нужен фронт. После форка — визуальная индикация "custom". `GET /worlds/{id}` endpoint есть, API client method есть (`getWorld`) но нигде не используется.

**Верифицируем:** можно открыть мир, увидеть структуру слоёв, форкнуть слой, увидеть что он стал custom.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Layer Editor

Новый API: чтение и запись YAML-файлов форкнутых (custom) слоёв. Frontend: code editor для YAML (только custom слои, library — read-only). Валидация YAML на бэкенде перед сохранением. E2E: fork → edit YAML → create session → verify changes applied in game.

**Верифицируем:** можно отредактировать YAML форкнутого слоя через браузер, изменения отражаются в новой сессии.

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
