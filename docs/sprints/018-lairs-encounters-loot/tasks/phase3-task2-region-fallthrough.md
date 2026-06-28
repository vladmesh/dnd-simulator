# Task: Фоллтру локация → регион (override) и боевой ролл

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 3 — Региональные таблицы встреч

## Description

Подключить региональные таблицы (загруженные в задаче 1) к роллу встреч: локация без своей encounter-таблицы фоллбечится на таблицу своего региона; своя таблица локации перекрывает региональную (override, без слияния). Контент-автор задаёт профиль угрозы на весь регион, а отдельные локации могут его переопределить.

Резолв делаем **на загрузке**, по образцу уже существующей сборки `battle_map_configs` (`game_service.py:153-163`): там региональный battle_map применяется ко всем локациям региона, а пер-локационный перекрывает. Делаем ровно так же для encounter-таблиц. Это значит, что рантайм `ActivationManager._check_encounters` / `_roll_encounters` **не меняется** — он по-прежнему работает с плоским `dict[str, list[EncounterEntry]]` по location_id; вся региональная логика схлопывается в эффективную пер-локационную таблицу при старте сессии.

Конкретно:

- В `game_service`, после загрузки `region_encounter_tables` (задача 1) и до `EntitiesLayer(...)`, собрать эффективные таблицы:
  ```python
  effective_encounters: dict[str, list[EncounterEntry]] = {}
  for loc in locations:
      if loc.region_id in region_encounter_tables:
          effective_encounters[loc.id] = region_encounter_tables[loc.region_id]
      if loc.id in encounter_tables:
          effective_encounters[loc.id] = encounter_tables[loc.id]
  ```
  (региональная — дефолт, локационная — override; точная калька с `battle_map_configs`). Передать `effective_encounters` в `EntitiesLayer(encounter_tables=...)` вместо сырого `encounter_tables`.
- Список объектов `EncounterEntry` региона шарится по ссылке между локациями региона — это безопасно: `EncounterEntry` frozen, ролл только читает entries. Кулдаун остаётся пер-локационным (`_encounter_cooldowns` по location_id), так что две бестабличные локации одного региона роллят независимо.
- Контент: в тест-мире завести регион с `region_encounters` и тремя локациями — (а) локация без своей таблицы (должна ролить из региональной), (б) локация со своей таблицей в том же регионе (override), (в) необязательно — вторая бестабличная для проверки независимого кулдауна. Подойдёт расширение существующего `test_vale` (есть `encounters: forest_road`, регион `darkwood`) либо отдельная мини-фикстура по образцу lair-мира фазы 1 — выбрать то, что даёт детерминированный integration-тест.

## Tests First

Integration (живой путь активации/ролла через реальные слои; `random` мокается, чтобы ролл был детерминирован):

- **Фоллтру:** игрок входит в локацию БЕЗ своей таблицы, лежащую в регионе с `region_encounters` → встреча роллится из региональной таблицы (при форсированном «hit» в локации спавнятся монстры именно из региональной таблицы, и при враждебности стартует авто-бой). В соседней локации другого региона (без региональной таблицы) — ничего не спавнится.
- **Override:** игрок входит в локацию, у которой есть СВОЯ таблица, в том же регионе с региональной → роллится только локационная таблица; шаблон из региональной таблицы не появляется. Перекрытие, не слияние.
- (опц.) **Независимый кулдаун:** игрок проходит две разные бестабличные локации одного региона за один прогон → региональная таблица роллится в каждой (кулдаун по location_id, не по региону).

Мокать только `random` (и LLM, если затронут). Не мокать слои/активацию — проверяем наблюдаемый спавн в мире, а не вызовы методов.

## Implementation

- Единственная точка изменения логики — сборка `effective_encounters` в `game_service` (калька `battle_map_configs`). `ActivationManager` и `EntitiesLayer.__init__` не трогаем по сигнатурам (передаём уже схлопнутый словарь в существующий параметр `encounter_tables`).
- Порядок применения важен: сперва региональная (дефолт), потом локационная (override). Если у локации нет ни своей, ни региональной — её нет в `effective_encounters`, и `_check_encounters` (`activation_manager.py:169`) корректно скипает.
- Для детерминизма теста: ролл идёт через `random.random()` (`activation_manager.py:191`) и `random.randint` (`:202`). Замокать так, чтобы `chance` гарантированно срабатывал и `count` был фиксирован. Существующие encounter-тесты (если есть) — образец паттерна мока.
- Авто-бой после спавна уже встроен (`_maybe_start_combat`), отдельной работы не требует; в тесте достаточно проверить присутствие заспавненных существ нужного шаблона в локации (и, для враждебных, факт старта боя).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Локация без своей таблицы роллит из таблицы своего региона
- [ ] Локация со своей таблицей перекрывает региональную (без слияния)
- [ ] Локация вне региона с таблицей и без своей таблицы — встреч нет
- [ ] Рантайм-ролл (`ActivationManager`) не изменён по контракту — резолв на загрузке

## Status

`done`

## Developer Notes

- **Resolution = one shared helper, not a second copy-paste loop.** Extracted `_flatten_region_defaults[T]` (PEP 695 generic) in `game_service.py` and routed *both* `battle_map_configs` and the new `effective_encounters` through it. The task said "калька с battle_map_configs"; literally copying the loop would have doubled the pattern, so I deduped instead. `effective_encounters` is passed into the existing `EntitiesLayer(encounter_tables=...)` param — `ActivationManager` / `_roll_encounters` are byte-for-byte unchanged (resolution is load-time only).
- **`_region_encounter_tables` → `region_encounter_tables`** (now consumed). Region default first, per-location override second — exact override semantics, no merge.
- **Test boundary: in-process product test, not docker.** The encounter roll uses the bare `random.random()` / `random.randint()` module functions, *not* the seeded `get_global_rng()`, so `DND_DICE_SEED` (how the docker `test_lairs.py` gets determinism) would NOT make the roll deterministic. The faithful deterministic path is in-process: `GameService.start_game` + `create_player` build the world through the real game_service resolution, then drive `EntitiesLayer.update_activation` with the world's real query/emit fns and `random` mocked. Lives in `tests/unit/test_region_encounters.py` (4 tests), same pattern as `test_lair_materialization.py`.
- **Content (test_vale, additive):** `region_encounters: crossroads → goblin` in `ecology/monsters.yaml`; new bare `forest_edge` location in region `darkwood` (no lair) for the "no table anywhere → nothing spawns" negative check — `forest_clearing` couldn't serve that role because it hosts the goblin lair. Bumped the `test_manifest_game_service.py` location-count assertion 5 → 6 (intentional: the test world gained a location).
- **RED coverage.** Fallthrough (`crossroads_tavern` → regional goblin) and per-location cooldown (two tableless crossroads locations roll independently) were RED before the impl, GREEN after. Override (`forest_road` own bandit table beats the regional goblin) and the darkwood negative are guards: they can't be RED pre-impl because the regional table only enters the roll path *with* this change — they catch a future merge/global-leak regression.
- `make check`: backend 2237 passed (4 new), mypy clean (145 files), frontend 238 passed. The 2 eslint SchemaForm warnings are pre-existing/unrelated.
