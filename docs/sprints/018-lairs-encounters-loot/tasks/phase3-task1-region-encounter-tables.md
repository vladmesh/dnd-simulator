# Task: Региональные encounter-таблицы — схема, загрузка, fail-fast

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 3 — Региональные таблицы встреч

## Description

Дать контент-автору задавать encounter-таблицы на уровне региона. Сейчас таблицы только локационные: `ecology/monsters.yaml` содержит `encounters: {location_id: [entries]}`, грузится через `parse_encounters` → `dict[str, list[EncounterEntry]]` (`content_loader/monsters.py:127`). Эта задача добавляет параллельный источник — таблицы по region_id — и валидирует их при загрузке. Резолв «локация без своей таблицы → таблица региона» и сам ролл — задача 2; здесь региональные таблицы только грузятся, валидируются и доезжают до `game_service`, в ролл ещё не подключены.

Конкретно:

- Новый sibling-ключ `region_encounters` в `ecology/monsters.yaml`, по структуре идентичный `encounters`, но ключ — region_id, а не location_id:
  ```yaml
  encounters:            # как было, по location_id
    forest_road:
      - {template: bandit, chance: 0.3, count: [1, 2]}
  region_encounters:     # новое, по region_id
    darkwood:
      - {template: goblin, chance: 0.4, count: [1, 3]}
  ```
  Аддитивно: существующий `encounters` не трогаем, миграции контента нет.
- `parse_region_encounters(data, known_templates, known_regions) -> dict[str, list[EncounterEntry]]` в `content_loader/monsters.py`, рядом с `parse_encounters`. Переиспользует `EncounterEntryContent` и `_to_encounter_entry`. Fail-fast:
  - ссылка на неизвестный monster template → `RuntimeError` (как у `parse_encounters`, `monsters.py:137`);
  - ключ — неизвестный region_id (не из `known_regions`) → `RuntimeError`. Это новая проверка: опечатка в имени региона иначе дала бы молча мёртвую таблицу.
- `load_monsters` возвращает третий элемент — региональные таблицы. Сигнатура становится `tuple[dict[str, MonsterTemplate], dict[str, list[EncounterEntry]], dict[str, list[EncounterEntry]]]` и принимает новый параметр `known_regions: set[str] | None = None` (None → региональные таблицы не валидируются по региону; для прямых юнит-вызовов без геогра­фии). Читает `region_encounters` из того же `monsters.yaml`.
- `game_service.py:121`: передать `known_regions={r.id for r in regions}` (regions грузятся строкой выше, `Region.id` — `layers/geography/models.py:39`), принять третий элемент в локальную переменную (`region_encounter_tables`). В этой задаче переменная ещё не потребляется — экспансия в эффективные таблицы это задача 2. Чтобы не ловить «unused», допустимо сразу прокинуть её в место будущей сборки и оставить TODO, либо оставить распакованной до задачи 2 (тогда `_region_encounter_tables`).
- Обновить распаковку `load_monsters` на 2-кортеж в существующих вызовах: `tests/unit/test_content_parsers_creatures.py` (3 места), `tests/unit/test_monster.py` (2 места). Механически — добавить третий элемент (`_region`).

## Tests First

Юнит/загрузка (продуктовый контракт — контент-автор получает понятную ошибку или валидно загруженный мир):

- Мир с валидным `region_encounters` (регион существует, шаблон существует) грузится без ошибок, и в возвращённом региональном словаре есть запись для этого региона с её entries (template_id / chance / count из YAML).
- `region_encounters`, где entry ссылается на несуществующий monster template → `RuntimeError` на этапе загрузки (по аналогии с локационным кейсом).
- `region_encounters` с ключом-region_id, которого нет среди `known_regions` → `RuntimeError` на этапе загрузки.
- Мир без `region_encounters` (только старый `encounters`) грузится по-прежнему: локационные таблицы не пусты, региональные пусты. Регресс существующего формата.

Не писать тесты вида «parse_region_encounters возвращает dict» или «EncounterEntryContent имеет поле template» — проверяем загрузку/валидацию контента, а не структуру кода.

## Implementation

- `parse_region_encounters` — копия `parse_encounters` с дополнительной проверкой `region_id in known_regions`. Если получится чисто — вынести общий цикл по entries в приватный helper, но не обязательно (две короткие функции читаются нормально).
- `load_monsters`: после `parse_encounters(...)` распарсить `monsters_data.get("region_encounters", {})` через `parse_region_encounters(..., known_regions or set())`. Если `known_regions is None`, валидацию по региону пропустить (региональные ключи примутся как есть) — нужно для юнит-тестов парсеров, которые зовут `load_monsters` без геогра­фии. Геймплейный путь (`game_service`) всегда передаёт реальный набор регионов, так что fail-fast в бою сохраняется.
- `known_regions` в `game_service`: `regions` (строка 103, `list[Region]`) → `{r.id for r in regions}`.
- Gotcha: `load_monsters` экспортируется из `content_loader/__init__.py`; сигнатуру меняем — проверить, что `make check` ловит все распаковки (mypy + 5 тест-сайтов выше).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `region_encounters` грузится из `monsters.yaml` параллельно локационным таблицам
- [ ] Битый template ref в региональной таблице → fail-fast при загрузке
- [ ] Неизвестный region_id в `region_encounters` → fail-fast при загрузке
- [ ] Старый формат (только `encounters`) грузится без изменений

## Status

`done`

## Developer Notes

- **Загрузка/валидация.** Вынес общий цикл по entries в `_parse_encounter_entries(key, entries, known_templates)` — `parse_encounters` теперь однострочный dict-comprehension над ним, `parse_region_encounters` тот же helper плюс проверка `region_id in known_regions`. Дедуп, а не копипаст.
- **`known_regions` опционален и в `parse_region_encounters`** (`set[str] | None = None`, None → проверка региона скипается), не только в `load_monsters`. Так прямой вызов парсера без геогра­фии не падает, а геймплейный путь (`game_service` всегда передаёт `{r.id for r in regions}`) сохраняет fail-fast. Шаблоны валидируются всегда.
- **`load_monsters` → 3-кортеж** `(templates, encounters, region_encounters)`. Обновил 5 распаковок: `test_monster.py` (2), `test_content_parsers_creatures.py` (3) + потребитель `game_service.py:121`. Региональные таблицы пока уходят в `_region_encounter_tables` (не потребляются — экспансия это задача 2).
- **Экспорт.** `parse_region_encounters` добавлен в `content_loader/__init__.py` (import + `__all__`) симметрично `parse_encounters`.
- **Тесты.** 7 новых юнит-тестов (`TestParseRegionEncounters` ×3, `TestLoadMonstersYaml` +2 region-кейса, +regression на пустой `region_encounters` в существующих кейсах). `make check`: backend 2233 passed, mypy/ruff чисто.
- **Не моё, к сведению.** `frontend/SchemaForm.test.tsx > renders ref field as select with fetched options` флапнул один раз в полном vitest-прогоне, зелёный при изоляции и на повторе полного прогона. Бэкенд-only изменение на него влиять не может — фликер фронтового мока, не регресс этой задачи.
