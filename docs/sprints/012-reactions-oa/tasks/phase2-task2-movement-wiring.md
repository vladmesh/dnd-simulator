# Task: Wire movement handlers to trigger OA

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 2 — Movement Integration + Round Wiring

## Description

Две точки входа движения должны вызывать `on_leave_reach` callback:

1. **`handle_move_to`** (`rules/handlers/movement.py`): сейчас вызывает `walk_path()` который проходит весь путь за раз. Заменить на пошаговый проход: на каждом шаге вызвать `find_oa_triggers` для пары (current, next), если есть триггер — вызвать `ctx.on_leave_reach`. Если callback вернул False (мувер мёртв) — остановить движение, позиция = текущий шаг. Обновить budget по фактически пройденному расстоянию.

2. **`resolve_move`** (`layers/entities/combat_manager.py`): один шаг на 5ft. После вычисления new_pos проверить, покидает ли мувер reach кого-то (вызвать callback). Если мувер мёртв — не перемещать. Проблема: `resolve_move` не получает `ActionContext` — получает `Event`. Нужно передать callback через другой механизм или реструктурировать.

**Решение для resolve_move**: `handle_move` handler получает `ActionContext` с callback. Вместо emit → resolve_move, handler сам делает single-step movement (как resolve_move, но с доступом к ctx). combat_manager.resolve_move остаётся для совместимости non-combat move events, но combat движение идёт через handler напрямую.

Альтернатива: вынести логику single-step movement из resolve_move в pure function в `rules/movement.py`, вызывать из обоих мест.

## Tests First

Unit-тесты в `tests/unit/test_movement_oa.py`:

- **handle_move_to: мувер проходит мимо врага, callback вызван с правильными позициями.** Путь из 3 шагов, враг стоит так что мувер покидает его reach на шаге 2. Mock callback, проверить вызов.
- **handle_move_to: callback возвращает False (мувер мёртв) — движение остановлено.** Мувер должен пройти 3 шага, на шаге 1 callback возвращает False. Финальная позиция = шаг 1, budget потрачен только за 1 шаг.
- **handle_move_to: мувер с is_disengaging=True — callback не вызывается.** find_oa_triggers возвращает пустой список, движение проходит полностью.
- **handle_move_to: два врага на разных шагах — два вызова callback.** Враг A на шаге 1, враг B на шаге 3. Оба callback вызваны.
- **handle_move (direction): мувер покидает reach врага — callback вызван.** Один шаг, враг рядом, после шага мувер вне reach.
- **handle_move (direction): callback не вызван если on_leave_reach is None (non-combat).** Мирное движение, callback отсутствует — работает как раньше.

## Implementation

1. Вынести single-step movement logic в pure function `resolve_step(cur_pos, direction, ft, battle_map, mover_id) -> Position` в `rules/movement.py`.
2. `handle_move_to`: заменить `walk_path` на пошаговый цикл с `find_oa_triggers` + callback.
3. `handle_move`: после resolve_step, если в combat и callback есть — проверить reach departure, вызвать callback.
4. `combat_manager.resolve_move`: использовать `resolve_step` из rules/movement.py для переиспользования логики.

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] handle_move_to ходит пошагово с OA проверками
- [ ] handle_move проверяет OA на single-step
- [ ] Движение прерывается при смерти мувера
- [ ] is_disengaging предотвращает вызов callback
- [ ] Non-combat движение работает как раньше (callback=None)
- [ ] Existing tests pass (`make check`)

## Status

`pending`
