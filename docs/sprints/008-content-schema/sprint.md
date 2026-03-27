# Sprint 008 — Content Schema & Catalogs

**Goal:** Единый source of truth для структуры контента — Pydantic-модели управляют парсингом, валидацией, API и фронтенд-формами. Монстры и предметы становятся переиспользуемыми каталогами, независимыми от миров.

**Started:** 2026-03-26

## Context

Sprint 007 довёл world builder до рабочего состояния: fork, scaffold, YAML editor. Но YAML editor — тупик для масштабирования. Структура контента нигде не формализована: парсеры в content_loader знают её неявно через `dict[str, Any]`, фронтенд не знает вообще. Добавление сотен монстров, NPC, предметов и заклинаний требует формализации.

Параллельно: монстры и предметы живут внутри слоёв мира (ecology/entities), хотя по природе — справочные данные, переиспользуемые между мирами. Goblin — один и тот же в любом мире, мир только выбирает каких монстров использовать.

Pydantic-модели контента решают обе проблемы: дают формальную схему (JSON Schema → формы) и типизированное хранение (каталоги с валидацией).

**Ссылки:** [sprint 007](../007-world-session/sprint.md), [VISION.md](../../VISION.md), [ecs-and-content](../../brainstorms/ecs-and-content.md)

---

## Phase 1: Pydantic Content Models + Parser Rewrite ✓

Pydantic-модели для всех типов сущностей (Region, Location, Nation, Settlement, NPC, MonsterTemplate, Squad, Item, Attack, AbilityScores). Переписываем парсеры в content_loader — `model_validate` вместо ручного `ndata.get(...)`. Обратная сериализация (model → YAML-compatible dict). Все существующие тесты проходят — внешнее поведение не меняется.

**Верифицируем:** `make check` зелёный, новые тесты round-trip (YAML → model → dict → YAML → model) для каждого типа.

**Tasks:**

1. [Pydantic Content Model Definitions](tasks/phase1-task1-content-models.md)
2. [Rewrite World Structure Parsers](tasks/phase1-task2-rewrite-world-parsers.md)
3. [Rewrite Creature, Monster, and Item Parsers](tasks/phase1-task3-rewrite-creature-parsers.md)

## Phase 2: Catalogs — Monsters + Items ✓

Новая структура `content/catalogs/{monsters,items}/`. Каталог — коллекция standalone YAML-файлов, по одному на сущность. Catalog loader индексирует по ID. Мировой ecology слой ссылается на каталог (`base: goblin` + optional `overrides`). NPC equipment — ссылки на item catalog (`ref: longsword`). Миграция sword_vale контента.

**Верифицируем:** sword_vale загружается из каталогов (не из inline данных), `start_game` работает, все тесты зелёные.

**Tasks:**

1. [Catalog Loader + Monster Catalog](tasks/phase2-task1-catalog-loader-monsters.md)
2. [Item Catalog + NPC Equipment References](tasks/phase2-task2-item-catalog.md)
3. [Assembly Integration — Wire Catalogs into Game Start](tasks/phase2-task3-assembly-integration.md)

## Phase 3: Entity CRUD API + JSON Schema ✓

Entity-level CRUD для мировых слоёв и каталогов (list/get/create/update/delete). JSON Schema endpoint — генерится из Pydantic-моделей автоматически. Layer-refs endpoint для cross-layer dropdown данных. Enum-значения в схеме автоматически.

**Верифицируем:** API создаёт NPC через JSON → файл обновляется → сессия видит NPC. JSON Schema содержит все enum-значения, дефолты, типы.

**Tasks:**

1. [Content CRUD Layer](tasks/phase3-task1-content-crud-layer.md)
2. [Entity CRUD API Endpoints](tasks/phase3-task2-entity-crud-api.md)
3. [JSON Schema + Layer-Refs Endpoints](tasks/phase3-task3-json-schema-refs.md)

## Phase 4: Frontend — Schema-Driven Forms + DM Restructure

Generic form renderer из JSON Schema. EntityListEditor заменяет YAML textarea. Catalog browser: browse/pick монстров и предметов для мира. `/master` restructure: вкладки Worlds/Sessions, world editor как stepper по слоям. Главная: Player/DM разделение.

**Верифицируем:** мастер создаёт NPC через форму, добавляет монстра из каталога, запускает сессию — всё работает. E2E: полный цикл создания мира через формы.

**Tasks:**

1. [Schema-Driven Form Renderer](tasks/phase4-task1-schema-form-renderer.md)
2. [Entity CRUD UI + Catalog Browser](tasks/phase4-task2-entity-crud-ui.md)
3. [Master Restructure + Main Page](tasks/phase4-task3-master-restructure.md)

## Phase 5: DM World Management ✓

Мастер управляет мирами: форкает готовые (полная копия с новым именем), переименовывает, редактирует, удаляет. Игрок только выбирает мир и создаёт персонажа — конструктор миров у игрока убираем. Fork layer пока скрываем из UI (бэкенд остаётся, пригодится для продвинутого конструктора).

**Верифицируем:** мастер форкает sword_vale → получает копию → переименовывает → редактирует NPC через stepper → создаёт сессию. Игрок видит оба мира, выбирает, создаёт персонажа. Удаление форкнутого мира работает.

**Tasks:**

1. [Restructure Player/Master World Flows](tasks/phase5-task1-restructure-flows.md)
2. [Fork World + Create World UI on Master](tasks/phase5-task2-fork-world-ui.md)

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

**Completed:** 2026-03-27

Pydantic content models as single source of truth for all entity types. Parsers rewritten to use `model_validate`. Monster and item catalogs extracted from world layers into standalone `content/catalogs/`. Entity CRUD API with auto-generated JSON Schema and cross-layer refs. Frontend: schema-driven forms (SchemaForm + EntityListEditor), catalog browser, master restructure (Worlds/Sessions tabs, layer stepper), landing page with Player/DM split. Player flow simplified (no world builder — master creates worlds, player picks from list).

5 phases, 14 tasks, ~60 commits. Integration tests: 92 pass. E2E: 18/18 green.

**Deferred:** Layer editor (fork individual layer, YAML textarea) hidden from UI but backend remains — superseded by schema-driven forms for entity editing.
