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

## Phase 1: Корректность и целостность save/load

Чинит все поведенческие баги ревью, каждый под regression-тестом (TDD: RED → GREEN). Верификация: save→load round-trip тест на магических аксессуарах из `d0e8eda`, frontend vitest на иконку, integration зелёный.

- Модификаторы аксессуаров + `experience`/`level_up_available` переживают save→load (`ItemContent` симметричные имена `modifiers`↔`grant_modifiers` + `extra="forbid"`; `to_full_save_data`/`PlayerContent`/`_to_player`).
- Иконка `lay_on_hands` рендерится (схлопнуть два реестра иконок в один / `satisfies`-проверка exhaustiveness).
- `handle_wait` отдаёт `ActionResult(success=False)` на недостижимый/несуществующий travel-таргет (закрывает `silent-failure-movement`), без silent `pass`.
- HTTP-статус из типов исключений (`PlayerNotFound`/`InvalidLevelUp`), а не из подстроки в тексте сообщения.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: Чистота rules/ + добивка i18n

`rules/` снова чистый (инвариант VISION «правила — чистые функции без состояния и I/O»), ошибки хендлеров локализованы. Верификация: integration зелёный, mypy чисто, тест на RU-локаль ошибок хендлеров, seeded-тест воспроизводимости хила.

- Убрать structlog из `sneak_attack.py` / `rule_brain.py` (возвращать причину вызывающему, логирует impure-caller).
- Обернуть все `ActionResult(error=...)` в `_()` по хендлерам (items/equipment/trade/action_surge/loot/combat) — добивает `combat-log-i18n-gaps` после фазы 3 Sprint 019.
- Прокинуть `rng` через `ActionContext` в хендлеры (хил/Second Wind воспроизводимы при сидированном реплее).
- Вынести деплит логова в чистую `rules/lairs.should_deplete(lair, roll)` с инъектируемым роллом.
- Убрать I/O из pure rules: `merchant-provider-in-rules` (world-query callback) → в service/аргументом; `base-action-provider-stateful` → standalone-функция / frozen dataclass.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Типизация границ + enums (фундамент под control-interfaces)

Межслойные контракты типизированы, строковые сравнения заменены enum'ами, единая точка поиска слоя. Верификация: mypy strict чисто, integration зелёный, поведение неизменно.

- Типизированный query-контракт: результат на `QueryType` (типизированные dataclasses / аксессоры) → схлопывает касты `Answer.value`/`isinstance` (`any-to-object-sweep`, `dict-str-object-overuse`); типизировать `Query.params`.
- `SquadInfo`/`LairInfo` frozen dataclasses вместо bare-dict на границе ecology→entities.
- Enums: `EntityType` / `BrainType` (строковые сравнения), `LayerSource` вместо `"library"` (`layer-source-string-cmp`).
- `World.get_layer[L: Layer](kind: type[L]) -> L` вместо 5× isinstance-циклов (единое поведение при отсутствии слоя).
- App-level exception handlers в `app.py` (убирает per-route try/except-лестницу + дубль type-guard в content-роутах).
- Единый источник player-status: `player_status` → `PlayerStatusData`, остальное через `model_validate(asdict(...))`.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Декомпозиция бэкенд-модулей (отложенный 019-м sweep)

Выросшие модули раздроблены, поведение неизменно, под полной тест-сеткой фаз 1-3. Верификация: integration 154+ зелёный, combat E2E без изменений, дельты размеров файлов.

- `activation_manager` (614) → `activation` / `encounters` / `materialization` + общий трекер материализации (squad и lair — один алгоритм).
- `round.py` (619) → единый `_run_turn_loop` (combat/peaceful), сборка awareness в `AwarenessBuilder`, одна активация за итерацию loop, `resolve_abstract_move` → `rules/movement`, выкинуть dead-параметр.
- `combat_manager` (491) → `make_relation_fn` helper (6 hand-rolled closures), split initiative/turn от combat-state.
- `ecology/layer` (457) → `movement` / `squad_combat` / `lairs` (паттерн politics).
- Реестр экипировки: `equipped: dict[EquipmentSlot, Item]` + один EQUIP/UNEQUIP со `slot`-параметром + factory-хендлеры вместо 6 полей / 12 ActionType / 12 обёрток (ужимает `action_defs`).
- Дедуп сериализации: `GameDateTime.to_dict/from_dict`, per-layer `_x_to_dict` (или `DictBackedLayer` база), `entity_serialization.py` (зеркало `combat_serialization`); разрыв цикла `core/player → content_loader` (сериализация предмета в content_loader).

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 5: Декомпозиция фронта

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

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **Полный sweep, а не фокус.** Пользователь выбрал максимальный скоуп: баги + чистота + типизация + декомпозиция бэка + фронтовые god-компоненты. Закрывает обещание Sprint 019 про отложенный tech-sweep.
- **Багфиксы первой фазой.** BLOCKER порчи данных и видимые баги — до любого рефактора; рефактор поверх зелёных тестов.
- **Чистота rules/ до декомпозиции.** Инвариант VISION дёшево восстановить, и он защищает движок при последующих перестановках.
- **Сериализационную половину `player-xp-not-persisted` берём, WS-race — нет.** Та же дыра `to_full_save_data`, что и BLOCKER; сам `session-disconnect-debounce` остаётся отдельным багом в бэклоге.
- **Принятые core→rules lazy-импорты не трогаем.** `class_features`/`combat`/`monster` — by-design композиция (решение `core-brain-imports-rules`). В скоупе только цикл `core/player → content_loader`.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
