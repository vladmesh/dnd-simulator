# Task: Контракты событий действий

**Date:** 2026-07-12
**Sprint:** 023-trigger-table
**Phase:** 1 — Типизированная таксономия событий

## Description

Завершить таксономию переводом событий действий: say, attack result, dodge/flee, dash/disengage, item/class abilities, equip/unequip, trade и loot. Убрать оставшиеся чтения `event.data` из perception и игровых consumers, чтобы весь `EventType` enum имел фиксированный payload-контракт перед началом write-back и trigger table.

## Tests First

- Реальные handlers для боя, движения, предметов, экипировки и торговли эмитят payload'ы с полями, нужными для результата действия и player log; тесты проходят через dispatcher/handler, а не проверяют только dataclass-конструкторы.
- Attack perception по-прежнему отображает бросок, AC, оружие, critical и компоненты урона; equip/trade/item события сохраняют локализацию и observer-specific формулировки.
- Инвентарная цепочка buy → equip → use/take выдаёт последовательность типизированных событий без свободных словарей и с корректными actor/target/item IDs.
- Контрактная проверка покрывает все неслужебные `EventType`: для каждого типа зарегистрирован ровно один payload, новый enum member без контракта ломает тест.

## Implementation

Добавить action payload-модели в `core/events.py`, мигрировать `rules/handlers/`, attack resolution и оставшиеся producer-сайты. В `layers/entities/perception.py` сузить dispatch handler так, чтобы он получал payload ожидаемого типа, а не общий `Event` с ручными `str()`/`assert`/словарными lookup. Общие value objects броска и компонентов урона сделать типизированными и переиспользовать между resolution и perception.

Удалить `Any` из контракта `Event`; допустимые truly dynamic значения должны быть отдельным явно названным payload-типом и не участвовать в trigger matching. Обновить gettext-каталог только если изменились user-visible msgid.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Все штатные `EventType` имеют один зарегистрированный payload-контракт
- [ ] В production producers и perception нет обращений `event.data[...]`/`event.data.get(...)`
- [ ] `Event` больше не экспортирует свободный `dict[str, Any]` как доменный контракт

## Status

`pending`
