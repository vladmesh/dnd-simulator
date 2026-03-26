# Sprint 006 — Layer Composition

**Goal:** Мир собирается из переиспользуемых шаблонов слоёв. Библиотека слоёв, дерево совместимости, манифест мира.

**Started:** 2026-03-26

## Context

Сейчас world template — плоская директория YAML. Все слои привязаны к конкретному миру, переиспользование невозможно. Для world builder и UGC нужна композиция: мастер выбирает готовые слои из библиотеки или создаёт свои. Это фундамент для будущего world builder UI, маркетплейса шаблонов, и корректного формата сейвов.

Ключевые решения:
- **Гранулярность:** 1 шаблон = 1 слой (geography, politics, settlements, ecology, entities) — 5 шаблонов на мир.
- **Кастомизация:** fork, не overlay. Копия шаблона, редактируемая как угодно.
- **Версионирование:** пиннинг. Мир зафиксирован на версии шаблона, миграций нет.

**Ссылки:** [VISION.md](../../VISION.md), [ROADMAP.md](../../ROADMAP.md), [world-builder plan](../../plans/world-builder.md)

---

## Phase 1: Library Structure + Manifest + Content Migration

Определяем формат шаблона слоя (metadata.yaml + данные), формат манифеста мира, структуру `content/library/`. Конвертируем sword_vale: все 5 слоёв в библиотеку, мир → манифест со ссылками. Старые тестовые миры (arena, village, sneak_test) удаляем. Создаём новый тестовый мир test_vale — all-custom, минимальный но полноценный (2 региона, сквад, патруль, НПС). Settlements выносим из regions.yaml в отдельный settlements.yaml. `content_loader` пока не трогаем — только формат и данные на диске.

**Верифицируем:** структура на диске соответствует новому формату, старых плоских миров не осталось.

**Tasks:**

1. [Library Structure + Sword Vale Extraction](tasks/phase1-task1-library-structure.md)
2. [Manifest Format + World Migration + Cleanup](tasks/phase1-task2-manifest-migration.md)

## Phase 2: Content Loader Reads from Manifest ✓

Рефакторим content_loader: читает manifest.yaml → резолвит каждый слой из library/ или custom из директории мира. `start_game()` работает как раньше, но загружает через новый путь. Все существующие тесты зелёные. Старый формат (без манифеста) — убираем, не поддерживаем.

**Верифицируем:** `make check` зелёный, игра запускается через манифест.

**Tasks:**

1. [Manifest Resolver + Standalone Settlements Loader](tasks/phase2-task1-manifest-resolver.md)
2. [Wire Manifest into GameService + Remove Old Format](tasks/phase2-task2-wire-manifest-into-gameservice.md)

## Phase 3: World Assembly Backend ✓

API для работы с библиотекой: список шаблонов по типу слоя, фильтрация по совместимости (given geography X → compatible politics). API для создания мира: выбрал шаблоны → создался манифест + пустая директория для custom. Fork шаблона: копия из библиотеки в custom директорию мира.

**Верифицируем:** через API можно собрать новый мир из библиотечных шаблонов, запустить сессию в нём.

**Tasks:**

1. [Library Catalog Service + API](tasks/phase3-task1-library-catalog.md)
2. [World Assembly + Fork API](tasks/phase3-task2-world-assembly-and-fork.md)

## Phase 4: World Assembly Frontend ✓

Пошаговый UI: выбери географию → выбери политику (фильтр по совместимости) → ... → назови мир → готово. Заменяет или дополняет текущий WorldPicker ("quick start" vs "custom world").

**Верифицируем:** E2E — пользователь собирает мир через UI, запускает сессию, играет.

**Tasks:**

1. [World Builder Wizard Component](tasks/phase4-task1-world-builder-wizard.md)
2. [Wire WorldBuilder into SetupScreen + E2E Verification](tasks/phase4-task2-wire-into-setup.md)

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
