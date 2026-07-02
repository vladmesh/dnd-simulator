# Task: Typed query accessors + payload dataclasses

**Date:** 2026-07-02
**Sprint:** 020-thermo-sweep
**Phase:** 2 — Типизация границ + enums

## Description

Заменить ручное сужение `Answer.value: object` на типизированные аксессоры: по функции на `QueryType`, каст живёт один раз внутри аксессора. Для многополевых payload'ов — frozen dataclasses; скаляры остаются скалярами.

Новый модуль `core/queries.py`:

- Payload-датаклассы: `WeatherInfo`, `RegionInfo`, `NationInfo`, `SettlementInfo` (по фактическим ключам из веток `query()` слоёв).
- Аксессоры вида `query_weather(query_fn, location_id) -> WeatherInfo`, `query_faction_relation(query_fn, a, b) -> FactionRelation`, `query_is_daylight(...) -> bool`, `query_location_region(...) -> str | None`, `query_player(...) -> PlayerCharacter | None` и т.д. Аксессор сам строит `Query` (включая params) и знает имя слоя-владельца — стрингли-обращения к params у потребителей исчезают.
- При неожиданном типе ответа аксессор падает с внятной ошибкой (fail-fast, принцип sprint 016), вместо тихой деградации soft-isinstance.

Мигрировать потребителей (карта из ревью/разведки):

- `awareness_builder.py:62-114, 335-386` — 9 запросов, все soft-isinstance/`str()` касты.
- `commands_world_state.py` — 7 `_expect(...)`; helper `_expect` удалить.
- `combat_manager.py:102,375,409` — FACTION_RELATION (assert + bare `==`).
- `activation_manager.py:272,297` — IS_DAYLIGHT / FACTION_RELATION (squad/lair-запросы — task 2).
- `settlements/layer.py:78-103` — WEATHER / NATION_INFO.
- `session.py:289-299` — PLAYERS / PLAYER.
- `commands_creatures.py:35-45` — ALL_CREATURES / ENTITY_INFO (списки entity-словарей остаются `list[dict[str, object]]`, но сужение централизуется в аксессоре).

Ветки `query()` слоёв возвращают датаклассы вместо руками собранных dict там, где появился payload-тип (geography WEATHER/REGION_INFO, politics NATION_INFO, settlements SETTLEMENT_INFO/REGION_SETTLEMENTS). Ветки, чей dict уходит прямо в wire-ответы (entities `_entity_summary`/`_entity_detail`), не переводим на датаклассы — только аксессор.

Вне скоупа: SQUADS_AT_LOCATION / SQUAD_INFO / LAIRS_AT_LOCATION (task 2), таблица диспатча `query()` вместо if/elif (не в фазе), мёртвый NEW_RAW_EVENTS (фаза 3).

## Tests First

Это refactor с неизменным поведением — тесты в первую очередь пиновка (GREEN до и после), плюс несколько новых:

- Аксессоры сквозь реальные слои: собрать мир из тестового контента, `query_weather` возвращает `WeatherInfo` с condition/temperature из geography-слоя; `query_region_settlements` — список `SettlementInfo` региона; `query_faction_relation` — `FactionRelation` из politics-отношений.
- Awareness-пиновка: awareness существа в локации включает погоду региона, имя нации-владельца и поселения — через реальные geography/politics/settlements (расширить test_awareness_builder, если сценария нет).
- Fail-fast: аксессор, получивший ответ неожиданного типа (подложный query_fn), поднимает ошибку с именем QueryType — не молчит.
- Существующие test_commands_world_state / test_combat_* / test_activation_manager остаются зелёными.

## Implementation

1. Написать `core/queries.py` (датаклассы + аксессоры). Имена слоёв взять из фактических `layer.name` констант.
2. Перевести producer-ветки перечисленных QueryType на датаклассы.
3. Мигрировать потребителей по списку, удаляя isinstance/assert/`_expect`/`str()`-касты.
4. `Query.params` у мигрированных вызовов строится только внутри аксессоров — прямых обращений `params["..."]` у потребителей не остаётся.

Gotcha: `commands_world_state` кладёт результаты прямо в wire-ответы — при переходе на датаклассы конвертировать через `dataclasses.asdict` на границе, формат ответа неизменен (пиновка через существующие API-тесты).

## Acceptance Criteria

- [ ] Пиновочные и новые тесты написаны до рефактора; fail-fast тест RED до реализации аксессоров
- [ ] Все перечисленные consumer-сайты без ручного сужения `Answer.value`
- [ ] `make check` зелёный (mypy strict без новых ignore)
- [ ] Wire-формат REST/WS ответов не изменился (существующие API-тесты зелёные)

## Status

`pending`
