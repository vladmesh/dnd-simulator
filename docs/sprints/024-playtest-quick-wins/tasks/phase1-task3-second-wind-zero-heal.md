# Task: Second Wind без «0 ОЗ»

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 1 — Читаемость и тактика боя

## Description

Second Wind при полном HP показывает «восстанавливаешь 0 ОЗ» — механически корректно (ресурс потрачен, лечение = 0), но выглядит багом (`second-wind-zero-heal`).

`_perceive_second_wind` (`layers/entities/perception.py:349-357`) всегда форматирует «You catch your breath, regaining {hp} HP» / «{entity} catches their breath, regaining {hp} HP» из `healed` в `EntitySecondWindPayload`. При максимальных HP `healed == 0`.

Фикс: при `healed == 0` — отдельная строка вместо «regaining 0 HP»:
- self: «You catch your breath, but you are already at full health».
- other: «{entity} catches their breath, already at full health».

Новые строки в EN base + перевод в RU `.po`, компиляция `.mo`. Ненулевой случай не меняется.

## Tests First

Продуктовые сценарии (перцепция от события `ENTITY_SECOND_WIND`):

- Боец при максимальных HP использует Second Wind (`healed == 0`) → сообщение наблюдателю-игроку про полное здоровье, БЕЗ «0 HP»/«0 ОЗ».
- Боец с неполными HP использует Second Wind (`healed > 0`) → обычная строка «regaining {N} HP» с реальным числом (регресс).
- Оба варианта проверяются и для self (актор = наблюдатель), и для other (актор ≠ наблюдатель).

## Implementation

- `layers/entities/perception.py` — `_perceive_second_wind`: ветка `if healed == 0` возвращает full-health строки (self/other), иначе существующие «regaining {hp} HP».
- i18n: обернуть новые строки в `_()`; добавить EN msgid + RU перевод в `locale/*/LC_MESSAGES/*.po`; `make messages` при необходимости для извлечения, `make compile-messages` для `.mo`.
- Строки короткие, без em-dash; регистр/тон — как у соседних combat-перцепций.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `healed == 0` → сообщение о полном здоровье без «0 HP»
- [ ] `healed > 0` → прежняя строка с числом
- [ ] EN + RU переводы на месте, `.mo` перекомпилированы

## Status

`pending`
