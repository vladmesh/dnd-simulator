# Task: Единый typed event-контракт

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 5 — Post-audit refactor

## Description

Закрыть `typed-event-compat-bridge`: typed payload становится единственным runtime-представлением события.
Убрать mapping-фасад `TypedPayload`, legacy aliases и нормализацию словарей из `Event.__post_init__`. Разнести
payload definitions, registry и сам конверт события по устойчивым core-модулям, сохранив публичные импорты там,
где они уже используются кодом проекта.

До удаления моста перевести последний production-emitter и оставшиеся тестовые конструкторы с `data={...}` на
конкретные payload-классы. Сериализация в JSON остаётся отдельной boundary-операцией и не возвращает словари
обратно в доменный контракт.

## Tests First

- Для каждого `EventType` создать событие с его payload-классом и проверить, что неверный класс payload
  отклоняется с именем типа события, а корректный объект проходит без преобразования.
- Зафиксировать attack request и attack result как два разных события: готовый результат не меняет тип, а
  попытка передать словарь старого command/result shape отклоняется вместо скрытой нормализации.
- Проверить trigger condition на реальном typed payload: совпадающие поля активируют пару, несовпадающие нет;
  matcher читает атрибуты payload и не требует mapping API.
- Прогнать representative event flow через perception и JSON boundary: typed combat/action/world события дают
  прежний текст и прежнюю JSON-форму для клиента.

## Implementation

Выделить payload-классы и `EventPayload` в модуль определений, registry `EventType → payload class` в отдельный
модуль контракта, а `Event` оставить простым валидирующим конвертом. Сохранить тонкие re-export'ы из
`core.events`, чтобы миграция структуры не расползлась по всем импортам в одном коммите.

Удалить `TypedPayload.__getitem__`, `get`, `keys`, `__contains__`, `legacy_aliases` и `legacy_type`. Перевести
`EventCondition.matches` на типизированный `getattr` по полям, уже проверенным при загрузке definition. Места,
где нужен wire/log dict, должны явно вызывать dataclass/JSON codec. Не вводить новый универсальный
`dict[str, object]` адаптер внутри core.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Production и тесты не создают `Event` из legacy payload-словарей
- [ ] `Event.data`/`Event.payload` всегда имеют конкретный тип из registry
- [ ] Typed payload не реализует mapping API и не содержит legacy aliases
- [ ] Attack request/result больше не переназначаются скрыто в `Event.__post_init__`
- [ ] Wire JSON и пользовательские event descriptions не изменились

## Status

`pending`
