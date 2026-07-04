# Task: Enum-добивка (LayerSource, BrainType, EntityKind на API) + World.get_layer

**Date:** 2026-07-02
**Sprint:** 020-thermo-sweep
**Phase:** 2 — Типизация границ + enums

## Description

Разведка показала: `EntityKind` и `BrainType` уже внедрены почти везде (спринты 016+), остались хвосты на границах. Плюс — единая точка поиска слоя.

**LayerSource** (`content_loader/manifest.py:19`):
- `_resolve_layer_path` / `_resolve_entity_layer_path` (`commands_worldbuilder.py:383,424`) возвращают `tuple[Path, str]` → вернуть `LayerSource`.
- Четыре `if source == "library":` (`:368,428,444,459`) → `is LayerSource.LIBRARY`.

**BrainType** (`core/brain.py:37`):
- `set_creature_brain` (`commands_creatures.py:209`) возвращает `.value`-строку → возвращать `BrainType`.
- `routes_session.py:157` сравнивает enum с строкой (`actual_type != BrainType.LLM.value`) → enum↔enum; `SetBrainResponse.brain_type` типизировать `BrainType`.

**EntityKind на API-границе**:
- `SpawnCreatureRequest.entity_type: str` (`schemas.py:32`) и query-param `list_creatures(entity_type: str | None)` (`routes_session.py:80`, `commands_creatures.py:23`) → `EntityKind`. Невалидное значение станет 422 от FastAPI вместо ValueError из глубины (fail-fast, фиксация нового поведения тестом).
- `CreatureResponse.entity_type` (`schemas.py:227`) оставить строкой (wire-формат, пустая строка — легальное значение), не трогаем.
- Ревью-MINOR «EntityKind fuses two vocabularies» — вне скоупа, не переоткрываем.

**World.get_layer**:
- `World.get_layer[L: Layer](kind: type[L]) -> L` — единый поиск с `LayerNotFoundError` (или `RuntimeError` с именем типа) при отсутствии; плюс `World.find_layer(kind) -> L | None` для partial-миров.
- Мигрировать 6 сайтов: `world.py:45-49` (`creature_host`), `game_service.py:251-267` (три `_get_*_layer` — тела становятся однострочниками, protocol в `service/base.py` не ломаем), `action_dispatcher.py:222-224,251-253` (merchant/lootables — используют `find_layer`, текущее тихое `[]` для partial-миров сохраняется).

## Tests First

- Пиновка: смена мозга через REST возвращает прежний `brain_type` и `no_llm_key`-warning без ключа (test_brain_reassignment — проверить покрытие REST-пути, дописать).
- Пиновка: CRUD-запись в library-слой отклоняется с прежней ошибкой (test_content_crud / commands_worldbuilder-тесты).
- RED: `GET /creatures?entity_type=bogus` → 422 (сейчас ValueError из query_handler).
- Новое: `world.get_layer(EntitiesLayer)` возвращает слой; на мире без слоя поднимает ошибку с именем типа; `find_layer` возвращает None.
- Пиновка: спавн/лут/торговля через REST не изменились (существующие integration).

## Implementation

Прямолинейная замена по списку выше. Gotcha: `list_creatures` кладёт значение в `Query.params` — согласовать с task 1 (если ALL_CREATURES-аксессор уже есть, параметр типизируется там же). Порядок с task 1 некритичен, но лучше после него.

## Acceptance Criteria

- [ ] 422-тест RED до реализации, GREEN после
- [ ] Ни одного `== "library"` в service/; `_resolve_*` возвращают `LayerSource`
- [ ] Ни одного enum↔`.value`-строка сравнения для BrainType
- [ ] 6 isinstance-циклов поиска слоя заменены на `get_layer`/`find_layer`
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- **World.get_layer/find_layer** (`core/world.py`): generic `get_layer[L](kind: type[L]) -> L` (fail-fast `LayerNotFoundError`, subclasses `RuntimeError` so existing handlers keep catching) + `find_layer[L] -> L | None` for partial worlds. Migrated all 6 sites: `creature_host` property, three `_get_*_layer` in game_service (now one-liners; `service/base.py` protocol untouched), two `_build_nearby_*_fn` in action_dispatcher (use `find_layer`, silent `[]` for partial worlds preserved). `creature_host` passes the runtime_checkable `CreatureHost` Protocol → one narrow `# type: ignore[type-abstract]` (mypy rejects a Protocol as `type[...]`, but isinstance works).
- **LayerSource** (`commands_worldbuilder.py`): `_resolve_layer_path`/`_resolve_entity_layer_path` now return `tuple[Path, LayerSource]`; four `if source == "library"` → `is LayerSource.LIBRARY`. Import lifted to module top (was function-local).
- **BrainType**: `set_creature_brain` returns `BrainType` (was `.value` str); route warning check `actual_type is not BrainType.LLM`; `SetBrainResponse.brain_type: BrainType`. Wire JSON unchanged (StrEnum serializes to its value).
- **EntityKind at API**: `SpawnCreatureRequest.entity_type: EntityKind`, `list_creatures` route + command param `EntityKind | None`, `query_all_creatures` accessor param `EntityKind | None` (stores `.value`). Invalid `?entity_type=bogus` now 422 from FastAPI instead of a deep ValueError. `CreatureResponse.entity_type` left `str` (wire format, "" legal). New RED→GREEN test for the 422.
- **Test fix**: `test_action_dispatcher._WORLD` (a `MagicMock(spec=World)`) — old code iterated `world.layers` (mock `__iter__` → empty), new code calls `world.find_layer()` which returned a truthy Mock, so the merchant/lootable providers activated and hit `world.time` (an instance attr absent from spec). Set `find_layer.return_value = None` to mirror an empty world. 15 get_available_actions tests were failing on this; now green.
- Pre-existing frontend flake (`CreatureForm.test.tsx`, userEvent 5s timeout under full-suite load) tripped once in `make check`; passes reliably in isolation. Out of scope (backend-only task), not touched.
