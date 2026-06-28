# Task: Lair respawn while active

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 1 — Логова (Lairs)

## Description

Активное логово восстанавливает население со временем. Зачистил часть лагеря, ушёл, вернулся позже — миньоны на месте снова. Это то, что отличает логово от разовой встречи.

Конкретно:

- Рантайм-состояние логова на `EcologyLayer` становится мутабельным и **персистится**: `state: LairState`, число живых миньонов (или множество живых member-id), `core_alive: bool`, `last_respawn_time: int` (секунды игрового времени).
- Синк после визита: при дематериализации логова `ActivationManager` считает, кто из ростера выжил (ядро и миньоны), и сообщает это ecology (по аналогии с `SQUAD_DEMATERIALIZED` → событие `LAIR_DEMATERIALIZED`, которое `EcologyLayer.handle_event` применяет к рантайм-состоянию логова). После этого население логова отражает реальные потери визита.
- Респавн на тике ecology: для `ACTIVE` логова, если миньонов меньше полного ростера и с `last_respawn_time` прошло ≥ `respawn_interval`, население добивается до полного ростера, `last_respawn_time` обновляется. (Минимально достаточно «refill до полного за один тик»; постепенный долив не требуется.) Ядро в этой задаче не воскрешается отдельно — это поведение задаётся деплитом в задаче 3; пока живое ядро остаётся живым, мёртвое (если так вышло) пока просто не материализуется как ядро — корректную семантику «ядро мертво → деплит» закрывает задача 3.
- `EcologyLayer.get_state`/`load_state` расширяются: сериализовать рантайм-состояние логов наряду со сквадами. `depleted`/население переживают save/load.
- Материализация (из задачи 1) теперь спавнит **текущее** население логова, а не всегда полный ростер.

## Tests First

Integration:

- Игрок входит в логово (3 гоблина + чифтейн), убивает 2 гоблинов, уходит в соседнюю локацию. Сразу возвращается (прошло < `respawn_interval`) → в логове 1 гоблин + чифтейн (потери визита сохранились, респавна ещё нет).
- Тот же сценарий, но перед возвратом промотать время ≥ `respawn_interval` → в логове снова 3 гоблина (миньоны восстановились до полного ростера).
- Save/load в середине: убил 2 гоблинов, ушёл, сохранил мир, загрузил, промотал < интервала, вернулся → по-прежнему 1 гоблин (потери и таймер пережили reload).
- Полный ростер не «переполняется»: после респавна миньонов ровно столько, сколько в `members`, не больше.

## Implementation

- Респавн считать на `EcologyLayer.tick` (он уже тикает раз в час и итерирует мир). Использовать `time.to_total_seconds()` и `last_respawn_time` так же, как squad-движение использует `_last_move_time`.
- Синк потерь — на дематериализации в `ActivationManager`, по образцу `_dematerialize_squad` (там strength обновляется пропорционально; здесь явный подсчёт живых member-ов + жив ли core). Эмитить `LAIR_DEMATERIALIZED` через `emit_fn`, ловить в `EcologyLayer.handle_event`.
- Персистенс: расширить существующие `get_state`/`load_state` в `ecology/layer.py`, не заводить отдельный механизм. Держать ключ `lairs` рядом с `squads`.
- Gotcha: материализованные существа `temporary=True` исчезают на смерти; «сколько выжило» надо считать из тех instance-id, что ещё живы в `_entities` на момент дематериализации (мёртвых там уже нет — значит выжившие = пересечение трекнутых id с живыми в `_entities`).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Активное логово добивает миньонов до полного ростера после `respawn_interval`
- [ ] Потери визита и таймер респавна переживают save/load
- [ ] Население не превышает полный ростер

## Status

`done`

## Developer Notes

- **Runtime state на `Lair`.** Добавлены мутабельные поля: `alive_members: list[str] | None` (`None` == полный ростер), `core_alive: bool`, `last_respawn_time: int`. Держим прямо на dataclass, как `Squad.strength`; `EcologyLayer` мутирует и сериализует подмножество.
- **Текущее население в материализации.** `_lair_to_dict` теперь отдаёт `members` = живые миньоны (`alive_members` или полный ростер) и `core` = id ядра только если `core_alive`. Материализатор спавнит ровно текущее население. Задача-1 тесты не задеты (свежее логово → None → полный ростер).
- **Синк потерь.** `ActivationManager._dematerialize_lair` считает выживших (ядро + миньоны по `_is_alive`: существо есть в `_entities` и `is_alive` — мёртвые temporary уже удалены на `ENTITY_DIED`, но в юнит-тестах остаются с hp 0, поэтому проверяю именно `is_alive`) и эмитит `LAIR_DEMATERIALIZED` (новый `EventType`) с `alive_members`, `core_alive`, `at_seconds`. `EcologyLayer.handle_event` применяет это к логову. Трекинг расширен до 3-tuple `(creature_ids, core_creature_id, minion_templates)` — порядок creature_ids = `[core?] + minions`, так что survivors мапятся на шаблоны по позиции.
- **Респавн.** Новая фаза в `EcologyLayer.tick`: `ACTIVE` логово ниже полного ростера и `now - last_respawn_time >= respawn_interval` → `alive_members = None` (полный), `last_respawn_time = now`. Анкер таймера = время ухода игрока (`at_seconds` из события), поэтому отсчёт идёт от визита, а не от эпохи. Респавн = refill до полного за один тик, без overflow (`alive_members=None` ≡ ровно `len(members)`).
- **Персистенс.** `lairs` добавлен в `EcologyLayer.get_state`/`load_state` рядом со `squads`. Логова приходят из контента; восстанавливаем только мутабельные поля (как у сквадов).
- **Тесты.** 4 новых в `TestLairRespawn` (потери до интервала / респавн после / без overflow / save-load). Хелперы `_lair`/`_make_layers` из задачи 1 расширены (param `respawn_interval`, опц. готовый `ecology`) — обратносовместимо, задача-1 тесты зелёные.
