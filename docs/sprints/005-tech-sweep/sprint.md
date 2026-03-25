# Sprint 005 — Tech Sweep

**Goal:** Расчистить техдолг: разбить god classes, закрыть тестовые дыры, починить архитектурные нарушения, убрать legacy content format, довести type safety до strict.

**Started:** 2026-03-26

## Context

3 feature-спринта подряд (001, 003, 004) наращивали код без системной расчистки. EntitiesLayer вырос с 832 до 1215 строк. action_handlers.py (605 строк, core combat) — без единого теста. rules/ импортирует из layers/, round.py обходит World query validation. 27 type: ignore в mixins. Три legacy single-file мира тянут fallback-ветки по всему content_loader.

Следующие 3-4 спринта будут feature-heavy (квесты, заклинания, ключевые NPC) — им нужен чистый фундамент.

**Ссылки:** [BACKLOG.md](../../BACKLOG.md), [audit](../../audit.md), [Sprint 004](../004-monster-encounters/sprint.md)

---

## Phase 1: Content Standardization

Удаляем legacy single-file формат. Конвертируем arena.yaml, village.yaml, sneak_test.yaml в директории. Убираем `_resolve_source()`, fallback-ветки в `parse_npc`/`parse_player`, legacy aliases в schemas.py, fallbacks в commands_creatures.py и entities_layer.py. Переписываем интеграционные тесты на multi-file миры. `make check` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: God Class Splits

EntitiesLayer (1215 LOC) → выделяем awareness builder, activation manager, query handler в отдельные модули. PoliticsLayer (609 LOC) → выделяем подсистемы. Тесты перекладываются, публичный API слоёв не меняется.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Growing Files Split

action_handlers.py (605 LOC) → combat, movement, trade handlers. content_loader.py (815 LOC) → по домену. Длинные методы (query 125 LOC, resolve_attack 186 LOC) — разбить.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Architecture Violations + Type Safety

Fix rules→layers imports (merchant protocol в core). round.py → World.query_layer(). Mixin Protocols (27 type: ignore). Any→object в Query/Answer (24 каскадных изменения).

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 5: Test Gaps

Unit-тесты для action_handlers (split modules из Phase 3), action_provider, awareness, items, world, turn_budget, brain_factory. Приоритет: combat execution path.

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
