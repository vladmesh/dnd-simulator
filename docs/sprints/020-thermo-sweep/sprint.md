# Sprint 020 — Thermo Sweep

**Goal:** закрыть кластер структурного долга и багов из термоядерного ревью — восстановить чистоту `rules/`, типизировать межслойные границы, декомпозировать выросшие модули и фронтовые god-компоненты. Поведение неизменно, всё под защитой тестов.

**Started:** 2026-06-30

## Context

Внеочередной техспринт по результатам термоядерного ревью всей кодовой базы ([thermo-nuclear-review.md](../../thermo-nuclear-review.md)): 7 агентов глубокого чтения + межмодульный проход, итог — 2 BLOCKER, 49 MAJOR, 37 MINOR.

Почему сейчас:
- **Спринт 019 явно отложил декомпозицию выросших модулей «в будущий tech-sweep»** (`round-growing`, `activation-manager-growing`, `action-defs-growing`, `god-class-combat-manager`, `perception-fail-fast`). Этот спринт — тот самый sweep.
- **Большинство тем ревью уже благословлены бэклогом** как should-tech-debt: `any-to-object-sweep`, `dict-str-object-overuse`, `layer-source-string-cmp`, `entity-type-enum`, `brain-type-enum`, `long-func-start-round`, `silent-failure-movement`, `merchant-provider-in-rules`, `base-action-provider-stateful`, `schema-form-growing`, `world-overview-growing`.
- **Целимся в следующий продуктовый спринт** (`control-interfaces`, разрез control-plane на роли): типизация границ, exception handlers, унификация player-status и `World.get_layer` напрямую разгружают предстоящий разрез — отвердить дешевле до него, чем чинить регрессии после (тот же принцип, что в Sprint 019).
- **Свежий main (`d0e8eda`, #16) добавил магический лут** (`ring_of_protection`, `circlet_of_aim`, `boots_of_speed`) — аксессоры с `modifiers`. Это ровно тот контент, что триггерит BLOCKER потери модификаторов при save/load, и готовые фикстуры для regression-теста фазы 1.

Scope IN: корректностные баги ревью; чистота `rules/` + добивка i18n; типизация границ + enums + exception handlers + унификация player-status; декомпозиция round/combat/ecology/activation + реестр экипировки; дедуп сериализации + разрыв цикла `core/player→content_loader`; фронтовые god-компоненты.

Scope OUT:
- Принятые by-design lazy-импорты `core→rules` в `class_features`/`combat`/`monster` (решение бэклога `core-brain-imports-rules`) — не переоткрываем.
- Сам WS-race `session-disconnect-debounce` — отдельный баг. Но сериализационную половину `player-xp-not-persisted` (`experience`/`level_up_available` в `to_full_save_data`) берём в фазу 1: это та же дыра `to_full_save_data`, что и BLOCKER с модификаторами.
- Новые механики/контент/фичи; identity/роли/мультиплеер (содержание `control-interfaces`); security-бэклог (cors/auth/csrf); перф (`awareness-rebuild-cache`).

**Ссылки:** [thermo-nuclear-review](../../thermo-nuclear-review.md), [BACKLOG](../../BACKLOG.md), [VISION](../../VISION.md), [Sprint 019](../019-control-plane-prep/sprint.md)

## Phase 1: Корректность и инварианты ✓

Чинит все поведенческие баги ревью И восстанавливает чистоту `rules/` — вся корректностная/инвариантная работа до рефактора, каждый пункт под regression-тестом (TDD: RED → GREEN). Верификация: save→load round-trip на магических аксессуарах из `d0e8eda`, frontend vitest на иконку, тест RU-локали ошибок хендлеров, seeded-тест воспроизводимости хила, integration зелёный.

Баги:
- Модификаторы аксессуаров + `experience`/`level_up_available` переживают save→load (`ItemContent` симметричные имена `modifiers`↔`grant_modifiers` + `extra="forbid"`; `to_full_save_data`/`PlayerContent`/`_to_player`).
- Иконка `lay_on_hands` рендерится (схлопнуть два реестра иконок в один / `satisfies`-проверка exhaustiveness).
- `handle_wait` отдаёт `ActionResult(success=False)` на недостижимый/несуществующий travel-таргет (`silent-failure-movement`), без silent `pass`.
- HTTP-статус из типов исключений (`PlayerNotFound`/`InvalidLevelUp`), а не из подстроки в тексте сообщения.

Чистота `rules/` (инвариант VISION «правила — чистые функции без состояния и I/O»):
- Убрать structlog из `sneak_attack.py` / `rule_brain.py` (возвращать причину вызывающему, логирует impure-caller).
- Обернуть все `ActionResult(error=...)` в `_()` по хендлерам (items/equipment/trade/action_surge/loot/combat) — добивает `combat-log-i18n-gaps` после фазы 3 Sprint 019.
- Прокинуть `rng` через `ActionContext` в хендлеры (хил/Second Wind воспроизводимы при сидированном реплее).
- Вынести деплит логова в чистую `rules/lairs.should_deplete(lair, roll)` с инъектируемым роллом.
- Убрать I/O из pure rules: `merchant-provider-in-rules` (world-query callback) → в service/аргументом; `base-action-provider-stateful` → standalone-функция / frozen dataclass.

**Tasks:**

1. [Save/load data integrity (BLOCKER)](tasks/phase1-task1-save-load-integrity.md) — аксессуар-модификаторы + XP/`level_up_available` переживают save→load round-trip
2. [Visible behavioral bugs](tasks/phase1-task2-visible-bugs.md) — иконка `lay_on_hands`, тихий `handle_wait` travel, HTTP-статус из типов исключений
3. [rules/ purity — determinism](tasks/phase1-task3-purity-determinism.md) — structlog вон из sneak_attack/rule_brain, `rng` через `ActionContext`, `rules/lairs.should_deplete`
4. [rules/ purity — i18n handler errors](tasks/phase1-task4-handler-i18n.md) — обернуть `ActionResult(error=...)` в `_()` (items/equipment/trade/action_surge/loot) + RU перевод
5. [rules/ purity — provider I/O & state](tasks/phase1-task5-purity-providers.md) — merchant/loot провайдеры без world-query в rules; `BaseActionProvider` без состояния

## Phase 2: Типизация границ + enums (фундамент под control-interfaces) ✓

Межслойные контракты типизированы, строковые сравнения заменены enum'ами, единая точка поиска слоя. Верификация: mypy strict чисто, integration зелёный, поведение неизменно.

**Закрыта 2026-07-04.** Все 4 задачи done. `make check` зелёный, integration 154 passed, E2E зелёный (см. [e2e/phase2-report.md](e2e/phase2-report.md)) — блокеров нет. Task 4 подтверждён через UI: player-status с `appearance` течёт через WS корректно, дубль-fork → 409 через app-level handler.

- Типизированный query-контракт: результат на `QueryType` (типизированные dataclasses / аксессоры) → схлопывает касты `Answer.value`/`isinstance` (`any-to-object-sweep`, `dict-str-object-overuse`); типизировать `Query.params`.
- `SquadInfo`/`LairInfo` frozen dataclasses вместо bare-dict на границе ecology→entities.
- Enums: `EntityType` / `BrainType` (строковые сравнения), `LayerSource` вместо `"library"` (`layer-source-string-cmp`).
- `World.get_layer[L: Layer](kind: type[L]) -> L` вместо 5× isinstance-циклов (единое поведение при отсутствии слоя).
- App-level exception handlers в `app.py` (убирает per-route try/except-лестницу + дубль type-guard в content-роутах).
- Единый источник player-status: `player_status` → `PlayerStatusData`, остальное через `model_validate(asdict(...))`.

**Tasks:**

1. [Typed query accessors + payload dataclasses](tasks/phase2-task1-typed-query-contract.md) — `core/queries.py`: аксессор на QueryType, frozen payload-датаклассы, миграция ~28 cast-сайтов
2. [SquadInfo/LairInfo на границе ecology→entities](tasks/phase2-task2-squad-lair-info.md) — bare-dict сквад/логово-payload'ы → frozen dataclasses, ActivationManager читает поля
3. [Enum-добивка + World.get_layer](tasks/phase2-task3-enums-get-layer.md) — LayerSource/BrainType/EntityKind хвосты на границах; `get_layer`/`find_layer` вместо 6 isinstance-циклов
4. [App-level exception handlers + единый player-status](tasks/phase2-task4-exception-handlers-player-status.md) — handlers для однозначных типов + дедуп content type-guard; `player_status` единственный источник (WS получает `appearance`)

## Phase 3: Декомпозиция бэкенд-модулей (отложенный 019-м sweep)

Выросшие модули раздроблены, поведение неизменно, под полной тест-сеткой фаз 1-3. Верификация: integration 154+ зелёный, combat E2E без изменений, дельты размеров файлов.

- `activation_manager` (614) → вынести `encounters` / `materialization` + общий трекер материализации (squad и lair — один алгоритм). Саму activation-логику **не полировать** — она будет заменена машиной намерений/триггеров ([simulation-core](../../brainstorms/simulation-core.md)); цель фазы — изолировать её, а не улучшать.
- `round.py` (619) → сборка awareness в `AwarenessBuilder`, `resolve_abstract_move` → `rules/movement`, одна активация за итерацию loop, выкинуть dead-параметр. Слияние combat/peaceful в единый `_run_turn_loop` — **отменено**: peaceful-ход будет переписан намерениями (simulation-core), боевой останется как есть.
- `combat_manager` (491) → `make_relation_fn` helper (6 hand-rolled closures), split initiative/turn от combat-state.
- `ecology/layer` (457) → `movement` / `squad_combat` / `lairs` (паттерн politics).
- Реестр экипировки: `equipped: dict[EquipmentSlot, Item]` + один EQUIP/UNEQUIP со `slot`-параметром + factory-хендлеры вместо 6 полей / 12 ActionType / 12 обёрток (ужимает `action_defs`).
- Дедуп сериализации (**повышен**: предусловие simulation-core — «мир заморожен на полушаге» требует lossless-сейва, это стартовый кусок бэклог-эпика `save-schema`): `GameDateTime.to_dict/from_dict`, per-layer `_x_to_dict` (или `DictBackedLayer` база), `entity_serialization.py` (зеркало `combat_serialization`); разрыв цикла `core/player → content_loader` (сериализация предмета в content_loader).

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Декомпозиция фронта

God-компоненты разбиты, типы перестали быть ручными близнецами, дубли убраны. Верификация: vitest зелёный, E2E без регрессий.

- `TargetDropdown` (354) → target-pick + `AttackAction` / `LayOnHandsAction` обёртки; smite-UI один (`<SmiteChoice>` вместо инлайн-копии), `buildAttackParams` shared.
- `SchemaForm` (488) → `<FieldShell>` + один `buildDefaults` + `localizedCodec`.
- `EventLog` (388) → хуки `useStickyScroll` / `useLogInteraction`; Compact/Full различаются только виртуализацией.
- `WorldOverview` (331) → generic `EditableStatsTable<T>` + типизированные строки.
- Типы: сгенерированные/общие из бэкенд-схемы вместо ручных близнецов `PlayerStatus`/`PlayerStatusResponse`; `Region`/`Nation`/`Settlement` вместо `Record<string, unknown>`.
- Дедуп: `turnSlice` (`applyCommon` + `extractGameTime`), разбор ошибок API (`ApiError.detailMessage()`), reset стейта в `connectionSlice`.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 2 COMPLETE (2026-07-04). Ready for Phase 3 task generation.

## Decisions

- **Полный sweep, а не фокус.** Пользователь выбрал максимальный скоуп: баги + чистота + типизация + декомпозиция бэка + фронтовые god-компоненты. Закрывает обещание Sprint 019 про отложенный tech-sweep.
- **4 фазы, не 5 (консолидировано по просьбе).** Каждая граница фазы прогоняет close-phase (integration + E2E), поэтому фаз меньше. Баги ревью и восстановление чистоты `rules/` слиты в одну Phase 1 — общая природа (фикс-до-рефактора под regression-тестами), один прогон вместо двух. Рефактор-фазы (типизация / бэк-декомпозиция / фронт-декомпозиция) раздельны: разные поверхности, разная верификация.
- **Корректность и инварианты — до рефактора.** BLOCKER порчи данных, видимые баги и чистота `rules/` чинятся первой фазой под тестами; вся декомпозиция — поверх зелёной сетки.
- **Сериализационную половину `player-xp-not-persisted` берём, WS-race — нет.** Та же дыра `to_full_save_data`, что и BLOCKER; сам `session-disconnect-debounce` остаётся отдельным багом в бэклоге.
- **Принятые core→rules lazy-импорты не трогаем.** `class_features`/`combat`/`monster` — by-design композиция (решение `core-brain-imports-rules`). В скоупе только цикл `core/player → content_loader`.
- **Фазы 3-4 сверены с брейнштормом [simulation-core](../../brainstorms/simulation-core.md) (2026-07-04).** Спринт достраиваем: почти всё переживает будущий rework активации. Ре-скоуп фазы 3: activation-логику только изолируем (заменится намерениями/триггерами), слияние combat/peaceful turn-loop отменено, дедуп сериализации повышен до предусловия новой модели. Фаза 4 ортогональна, без изменений.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
