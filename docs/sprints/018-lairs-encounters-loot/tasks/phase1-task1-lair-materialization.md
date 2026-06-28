# Task: Lair model, content & materialization on entry

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 1 — Логова (Lairs)

## Description

Ввести понятие «логово»: фиксированное место с постоянным населением монстров. В этой задаче логово появляется в мире и материализуется в концретных существ, когда игрок входит в его локацию; при уходе игрока существа дематериализуются. Машина состояний пока тривиальна (всегда `ACTIVE`), без респавна и деплита — это задачи 2 и 3.

Конкретно:

- `core/lair.py`: dataclass `Lair` (`id`, `name`, `location_id`, `faction_id`, `members: list[str]` — id шаблонов монстров-миньонов, `core: str | None` — id шаблона ядра/босса, `respawn_interval: int` секунды, `depletion_chance: float = 0.0`) + enum `LairState { ACTIVE, DEPLETED }`. Логово стационарно (одна локация), движения нет.
- Контент-схема `LairContent` в `content_loader/schemas.py` + `load_lairs(path, lang)` в `content_loader/monsters.py` (файл `ecology/lairs.yaml`, по аналогии с `load_squads`). Валидация: все `members` и `core` существуют среди известных monster templates, иначе `RuntimeError`.
- Рантайм-состояние логова на `EcologyLayer`: при старте — `state=ACTIVE`, население = полный ростер, ядро живо. (Поля персистенса и респавн добавляются в задаче 2; здесь достаточно держать статический `Lair` + текущее `LairState`.)
- Новый `QueryType.LAIRS_AT_LOCATION` на ecology: по `location_id` возвращает логова в этой локации с их текущим состоянием (state, список живых миньонов/ядра для материализации).
- Материализация в `ActivationManager`: параллельно squad-пути, для каждого логова в активной локации спавним **весь текущий ростер** (ядро + миньоны) как концретные `Creature` (через `MonsterTemplate.spawn`, `faction_id` логова, `RuleBrain`, `temporary=True`), запускаем авто-бой через существующий `_maybe_start_combat`. Трекинг `_materialized_lairs: dict[str, ...]` (instance-id существ + id существа-ядра). При уходе игрока — дематериализация (удаляем существ; синк состояния в задаче 2).
- Wiring в `game_service.py`: `load_lairs(...)` рядом с `load_squads`, передать логова в `EcologyLayer`.
- Тест-контент: monster template `goblin_chieftain` (ядро, CR повыше) + `ecology/lairs.yaml` с гоблинским логовом (ядро `goblin_chieftain` + 3 `goblin`) в отведённой тест-локации. Допустимо как новый минимальный мир-фикстура (по образцу `level_up_test`), так и логово в существующем тест-мире — выбрать то, что даёт детерминированный integration-тест.

**Материализуем полный ростер сразу** (весь лагерь на месте, когда входишь), а не strength-scaled как у сквадов: логово это фиксированное место, а не абстрактная группа.

## Tests First

Integration (бой/материализация через реальные слои, мокается только LLM/random где нужно):

- Игрок входит в локацию логова → в этой локации присутствуют концретные существа: 1 `goblin_chieftain` + 3 `goblin`, все hostile игроку, и **бой стартует автоматически** (логово и игрок на разных сторонах по faction relations).
- Эти существа — реальные `Creature` с корректными HP/AC/атаками из шаблонов (можно проверить, что чифтейн крепче рядового гоблина).
- Игрок покидает локацию (move/travel в соседнюю) → существа логова исчезают из мира (дематериализованы), в новой локации их нет.
- Загрузка мира с `lairs.yaml`, где `core` или `members` ссылаются на несуществующий шаблон → `RuntimeError` на этапе загрузки.

Не писать тесты вида «LairContent имеет поле core» или «load_lairs возвращает dict» — проверяем наблюдаемое поведение в мире.

## Implementation

- Логово живёт на `EcologyLayer` (он владеет абстрактной симуляцией мира, тикает и имеет get_state/load_state). Материализация — на entities-стороне (`ActivationManager`), потому что только она создаёт `Creature` на `EntitiesLayer`. Это сохраняет направление слоёв (entities выше ecology, запрашивает вниз) и повторяет squad-флоу.
- Переиспользовать `MonsterTemplate.spawn` + `_maybe_start_combat`. Не дублировать squad-материализацию: вынести общее в helper, если получается чисто, но не обязательно в этой задаче.
- `LAIRS_AT_LOCATION` возвращает для материализации текущий ростер; в этой задаче он = полный ростер (живое ядро + N миньонов).
- Gotcha: помеченные `temporary=True` существа автоудаляются на `ENTITY_DIED` (`layer.py:293`). Для задачи 3 (детект смерти ядра) это значит, что факт смерти ядра надо снять при дематериализации/синке, а не полагаться на то, что мёртвое существо останется в `_entities`.
- Gotcha: добавить `LAIRS_AT_LOCATION` в `QueryType` и (если нужно для лога) `LAIR_MATERIALIZED` в `EventType` + в `_LOGGED_EVENTS`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Логово определяется в YAML, грузится и материализуется полным ростером при входе игрока
- [ ] Уход игрока дематериализует существ логова
- [ ] Битый ref (`core`/`members`) падает fail-fast при загрузке

## Status

`done`

## Developer Notes

- **Модель.** `core/lair.py`: `Lair` (`@dataclass`, как `Squad`) + `LairState` enum. Статические поля контента (members/core/respawn_interval/depletion_chance) заведены сразу, чтобы YAML был полным; в этой задаче из мутабельного работает только `state` (всегда `ACTIVE`). Респавн/деплит/персистенс — задачи 2-3.
- **Загрузка.** `LairContent` в schemas, `parse_lairs`/`load_lairs` в `content_loader/monsters.py` (файл `ecology/lairs.yaml`). `parse_lairs` валидирует `members`+`core` против известных шаблонов, бьёт `RuntimeError` на битый ref. Wiring в `game_service`: `load_lairs(..., known_templates=set(monster_templates))` → `EcologyLayer(lairs=...)`.
- **Материализация.** Параллельный squad-пути путь в `ActivationManager._update_lair_materialization`: запрос `LAIRS_AT_LOCATION` к ecology, спавн полного ростера (ядро первым, затем миньоны) через `MonsterTemplate.spawn`, faction = faction логова, `RuleBrain`, авто-бой через `_maybe_start_combat`. Трекинг `_materialized_lairs: dict[lair_id → (creature_ids, core_creature_id)]` (core id уже трекается под задачу 3, хотя здесь не используется). Дематериализация при уходе игрока; in-combat guard как у сквадов (бой удерживает существ на месте).
- **Тесты.** `tests/unit/test_lair_materialization.py` (8 тестов) в стиле `test_materialization.py` + politics-стаб для проверки авто-боя. Assembly-тест грузит `test_vale` через `GameService` (lair загружается в `ecology._lairs`). Fail-fast тест через `tmp_path`.
- **Контент.** В `test_vale` добавлены шаблоны `goblin` (base из каталога) + `goblin_chieftain` (inline, hp 21, CR 1) и `ecology/lairs.yaml` (`goblin_warren` в `forest_clearing`). Counts в `test_manifest_game_service` не задеты.
- **Изменённые старые тесты.** `test_activation_manager.py`: три query-стаба (`_noop_query_fn`, `_squad_query_fn`, `hostile_query_fn`) теперь отвечают `[]` на `LAIRS_AT_LOCATION`. Контракт `update_activation` расширился (добавлен запрос логов к ecology) — стабы моделируют пустой ответ ecology, как уже делают для сквадов. Это ожидаемое расширение, не починка ради зелени.
- **mypy gotcha.** Walrus `e` в двух comprehension-ах одной функции конфликтовал по типу (`Entity` vs `Entity | None`); переименовал второй в `ent`.
