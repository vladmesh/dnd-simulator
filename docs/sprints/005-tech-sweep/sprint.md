# Sprint 005 — Tech Sweep

**Goal:** Расчистить техдолг: разбить god classes, закрыть тестовые дыры, починить архитектурные нарушения, убрать legacy content format, довести type safety до strict.

**Started:** 2026-03-26

## Context

3 feature-спринта подряд (001, 003, 004) наращивали код без системной расчистки. EntitiesLayer вырос с 832 до 1215 строк. action_handlers.py (605 строк, core combat) — без единого теста. rules/ импортирует из layers/, round.py обходит World query validation. 27 type: ignore в mixins. Три legacy single-file мира тянут fallback-ветки по всему content_loader.

Следующие 3-4 спринта будут feature-heavy (квесты, заклинания, ключевые NPC) — им нужен чистый фундамент.

**Ссылки:** [BACKLOG.md](../../BACKLOG.md), [audit](../../audit.md), [Sprint 004](../004-monster-encounters/sprint.md)

---

## Phase 1: Content Standardization ✓

Удаляем legacy single-file формат. Конвертируем arena.yaml, village.yaml, sneak_test.yaml в директории. Убираем `_resolve_source()`, fallback-ветки в `parse_npc`/`parse_player`, legacy aliases в schemas.py, fallbacks в commands_creatures.py и entities_layer.py. Переписываем интеграционные тесты на multi-file миры. `make check` зелёный.

**Tasks:**

1. [Convert all single-file worlds to directory format](tasks/phase1-task1-convert-worlds.md)
2. [Remove legacy single-file loading code and fallback aliases](tasks/phase1-task2-remove-legacy-loading.md)
3. [Update integration test world references](tasks/phase1-task3-update-test-references.md)

## Phase 2: God Class Splits ✓

EntitiesLayer (1215 LOC) → выделяем awareness builder, activation manager, query handler в отдельные модули. Тесты перекладываются, публичный API слоёв не меняется.

**Decision:** PoliticsLayer (609 LOC) оставляем как есть — нет методов >100 LOC, подсистемы уже чётко разделены внутри файла. Разбивать ради разбивки нет смысла.

**Tasks:**

1. [Extract AwarenessBuilder from EntitiesLayer](tasks/phase2-task1-extract-awareness-builder.md)
2. [Extract ActivationManager from EntitiesLayer](tasks/phase2-task2-extract-activation-manager.md)
3. [Extract QueryHandler from EntitiesLayer](tasks/phase2-task3-extract-query-handler.md)

## Phase 3: Growing Files Split ✓

action_handlers.py (607 LOC) → combat, movement, trade handlers. content_loader.py (757 LOC) → по домену. Длинные методы (query 127 LOC, resolve_attack 186 LOC) — разбить.

**Tasks:**

1. [Split action_handlers.py into domain modules](tasks/phase3-task1-split-action-handlers.md)
2. [Split content_loader.py into domain modules](tasks/phase3-task2-split-content-loader.md)
3. [Decompose resolve_attack and query dispatcher](tasks/phase3-task3-decompose-long-methods.md)

## Phase 4: Architecture Violations + Type Safety

Fix round.py private layer access. Service mixin type safety (24 type: ignore). Answer.value Any→object for cross-layer type safety.

**Descoped:** rules→layers imports — already clean (merchant is_merchant lives on Character in core, rules never import layers).

**Tasks:**

1. [Service mixin Protocol base](tasks/phase4-task1-mixin-protocol.md)
2. [Eliminate Round's private EntitiesLayer access](tasks/phase4-task2-round-private-access.md)
3. [Answer.value Any → object](tasks/phase4-task3-answer-value-object.md)

## Phase 5: Test Gaps

Unit-тесты для action_handlers (split modules из Phase 3), action_provider, awareness, items, world, turn_budget, brain_factory. Приоритет: combat execution path.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **PoliticsLayer не разбиваем** (2026-03-26): 609 LOC, нет методов >100 строк, подсистемы (economy, wars, stability, diplomacy, leaders) уже чётко разделены как приватные методы. Разбивка ради разбивки — overengineering.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
