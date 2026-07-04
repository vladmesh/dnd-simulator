# Task: ecology/layer split — movement / squad_combat / lairs

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

## Description

`ecology/layer.py` (450) держит `EcologyLayer` вместе с движением сквадов (`_move_squad`, `_move_route`, `_move_roam`), боем сквадов (`_resolve_squad_combat`, `_are_hostile`, `_fight_squads`) и логовами (`_apply_lair_dematerialize`, `_respawn_lairs`). Разбить по образцу `politics/` (там `diplomacy.py`/`warfare.py`/`economy.py` — сабмодули, слой их оркестрирует).

Сделать (поведение неизменно):

1. **`ecology/movement.py`** — `_move_squad`/`_move_route`/`_move_roam` как функции над Squad (чистая геометрия перемещения по графу локаций уходит в rules, если ещё не там; ecology-специфика — здесь).
2. **`ecology/squad_combat.py`** — `_resolve_squad_combat`/`_are_hostile`/`_fight_squads` (abstract combat сквадов).
3. **`ecology/lairs.py`** — `_apply_lair_dematerialize`/`_respawn_lairs`. (Чистая `rules/lairs.should_deplete` уже вынесена в фазе 1 — не дублировать, звать её.)
4. `EcologyLayer` остаётся Layer-фасадом: `tick`/`handle_event`/`query`/`get_state`/`load_state` + оркестрация сабмодулей. `_squad_info`/`_lair_info` (payload-датаклассы из фазы 2) остаются на границе query.

Вне скоупа: смена модели сквадов/логов, событийная запись лестницы детализации, формат сериализации ecology (пиновка round-trip).

## Tests First

Поведение неизменно — пиновка (GREEN до рефактора, есть в `test_ecology_layer`/`test_squad_movement`/`test_squad_combat`/`test_lairs`):

- Сквад по маршруту двигается по рёбрам графа между локациями на ecology-тик; roam-сквад бродит.
- Два враждебных сквада в одной локации: `_resolve_squad_combat` даёт бой, победитель определяется по strength, событие эмитится.
- Логово: респавн ростера к капу на тик при ACTIVE; дематериализация применяет сверку.
- `query` ветки (SQUADS_AT_LOCATION/LAIRS_AT_LOCATION) возвращают те же `SquadInfo`/`LairInfo`.
- Save/load ecology-состояния (сквады+логова) round-trip неизменен.

## Implementation

1. Убедиться в пиновке движения/боя/логов (GREEN).
2. Вынести три сабмодуля; `EcologyLayer` делегирует. Держать сигнатуры сабмодулей чистыми (Squad/Lair + query_fn аргументом, без обратной зависимости на слой сверх необходимого — паттерн politics).
3. Прогнать пиновку + ecology save-roundtrip.

Gotcha: `politics/` — эталон структуры (слой тонкий, механика в сабмодулях). `get_state`/`load_state` формат ecology не трогать. `_fight_squads` эмитит события — сохранить контракт события (тип/payload) 1:1.

## Acceptance Criteria

- [ ] `ecology/movement.py`, `ecology/squad_combat.py`, `ecology/lairs.py` созданы
- [ ] `EcologyLayer` — тонкий Layer-фасад (tick/handle_event/query/state + оркестрация)
- [ ] Пиновка движения/боя/логов/query GREEN
- [ ] Save/load ecology round-trip неизменён
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- Split `ecology/layer.py` (450 → 256), following the politics-package pattern (submodule functions take explicit state, not the layer object):
  - **`ecology/movement.py`** (84): `move_squad(squad, route_index, route_direction, location_graph)` + `_move_route`/`_move_roam`; `_ROUTE_BEHAVIORS`/`_ROAM_BEHAVIORS` moved here.
  - **`ecology/squad_combat.py`** (129): `resolve_squad_combat(squads, location_graph, last_move_time, route_index, route_direction, query_fn)` + `_are_hostile`/`_fight_squads`. Destroyed-squad cleanup mutates the passed dicts.
  - **`ecology/lairs.py`** (57): `apply_lair_dematerialize(lairs, event)`, `respawn_lairs(lairs, now)`. Calls the existing pure `rules.lairs.should_deplete` (not duplicated).
- `EcologyLayer` is now a thin Layer facade: `tick`/`handle_event`/`query`/`get_state`/`load_state` + `_squad_info`/`_lair_info` payload builders. `get_state`/`load_state` format untouched (ecology save round-trip unchanged).
- **Test contract change**: `test_squad_movement` patched `ecology.layer.random` (roam) → `ecology.movement.random`. No test called the private methods directly, so nothing else changed.
- `make check` green.
