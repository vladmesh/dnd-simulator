# Task: Изоляция ошибок action от round loop

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 4 — Ручка ГМ + failure containment

## Description

Закрыть `action-error-kills-round-loop`: неверные или неполные параметры известного action должны давать
неуспешный `ActionResult`, доходить до игрока как обычная ошибка хода и оставлять round loop живым. Неизвестный
тип action по-прежнему отклоняется transport parser, а внутренние программные ошибки не должны маскироваться под
пользовательский ввод.

## Tests First

- В peaceful WS-сессии отправить `travel` без обязательного `destination_id`; получить `action_result` с ошибкой,
  не получить `game_over`, затем отправить валидное действие и дождаться следующего штатного состояния хода.
- Повторить цепочку в combat для action с отсутствующим required param: бюджет не расходуется, после отказа игрок
  может выполнить валидное действие в том же ходу.
- Передать параметры неверной формы/типа, которые сейчас выбрасывают ожидаемые `ValueError`, `TypeError` или
  lookup `KeyError` внутри handler: ошибка изолирована и залогирована с actor/action, состояние мира не меняется.
- Закрепить границу containment: незарегистрированный handler и специально брошенная непредвиденная ошибка
  остаются programming errors и не превращаются молча в `ActionResult`.

## Implementation

Сделать required-param validation в `ActionDispatcher` возвратом `ActionResult(success=False, error=...)`, а не
исключением. Вокруг вызова зарегистрированного handler ввести узкую границу для ошибок, вызванных входными
параметрами; отделить lookup handler до неё и не ловить общий `Exception`. Если существующих типов исключений
недостаточно чётко отделяют bad input от бага, ввести один доменный action-rejection exception и перевести на
него места, которые сейчас используют неоднозначный `KeyError`.

Round должен обработать такой результат по уже существующей ветке failed action: callback с ошибкой, нулевой
расход бюджета и продолжение combat до лимита отказов либо новый peaceful turn. Добавить session/WS regression,
который проверяет жизнь того же round thread после malformed payload, а не только unit-вызов dispatcher.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Missing/invalid params известного action возвращают failed `ActionResult` без мутации и расхода бюджета
- [ ] Malformed WS action не завершает round thread и не отправляет `game_over`
- [ ] После отказа игрок может выполнить следующий валидный action в той же сессии
- [ ] Неизвестные action names остаются transport errors
- [ ] Непредвиденные programming errors не поглощаются containment-границей

## Status

`pending`
