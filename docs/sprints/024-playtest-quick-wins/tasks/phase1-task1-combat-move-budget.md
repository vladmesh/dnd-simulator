# Task: Бюджет движения в бою

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 1 — Читаемость и тактика боя

## Description

Компасное перемещение в бою (`handle_move`, боевая ветка) не тратит бюджет движения, поэтому монстр пересекает всю карту за один ход и кайтинг невозможен (`combat-move-budget-not-consumed`).

`handle_move` (`rules/handlers/movement.py:51-80`, ветка «в бою с OA-колбэком») ставит новую позицию через `bm.set_position` и считает `moved_ft = grid_distance(...)`, но не проверяет и не списывает `ctx.turn_budget.movement_remaining`. Бюджет трогают только `handle_move_to` (BFS, `-= spent` на 142/152) и `handle_dash` (`+= speed` на 182).

Последствие в связке с RuleBrain: `_try_advance` (`rules/rule_brain.py:275`) пускает движение по гейту `movement_left >= 5`; раз бюджет не убывает, гейт всегда истинен, `move_toward_target` шагает по 5ft за итерацию хода без ограничения — доходит до цели через всю карту за ход. Принудительное завершение сейчас случается только через `consecutive_failures_end_turn` (`round.py:290`).

Фикс: в боевой ветке `handle_move` после расчёта `moved_ft`, если `ctx.turn_budget` присутствует:
- если `moved_ft > budget.movement_remaining` — вернуть `ActionResult(success=False, error=_("No movement remaining"))` до `set_position` (не двигаться);
- иначе после успешного перемещения `budget.movement_remaining -= moved_ft`.

Порядок с OA: списывать бюджет только за реально сделанный шаг (когда `set_position` состоялся и mover жив). Проверку достаточности бюджета делать до OA-триггеров/`set_position`.

## Tests First

Продуктовые сценарии (юнит на хендлере + через боевой ход RuleBrain):

- Существо со `speed = 30` в бою, вне досягаемости цели. Серия компасных `move` (5ft) суммарно списывает `movement_remaining` до нуля; после исчерпания `_try_advance` возвращает `None`, и ход завершается штатно (`end_turn`), а не через `consecutive_failures_end_turn`. Итоговое пройденное расстояние ≤ speed (не через всю карту).
- Один `move` на 5ft уменьшает `movement_remaining` ровно на пройденные футы (`grid_distance`).
- `move`, требующий больше футов, чем осталось в бюджете, отбивается `success=False` и НЕ меняет позицию на карте.
- Регресс: `handle_move_to` (BFS-клик игрока) по-прежнему корректно списывает бюджет и не задет фиксом.

## Implementation

- `rules/handlers/movement.py` — `handle_move`, только боевая ветка (`ctx.combat_state is not None and ctx.on_leave_reach is not None`). Non-combat ветка (emit для CombatManager) не трогается.
- `budget = ctx.turn_budget`; guard `if budget is not None`. Проверка достаточности — до `set_position`/OA; списание — после успешного шага.
- `moved_ft` уже считается как `grid_distance(cur_pos, new_pos)`; им же вычитать (одиночный компасный шаг, без diagonal 5/10-чередования `move_to` — приемлемо для quick-fix, отметить комментарием).
- Убедиться, что при гибели mover в OA (ранний `return ActionResult()` на строке 66) бюджет не списывается за несделанный шаг.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Компасный `move` в бою проверяет и списывает `movement_remaining`
- [ ] RuleBrain-существо не пересекает карту за один ход; ход завершается по исчерпании speed, а не только failsafe
- [ ] `handle_move_to` / `handle_dash` поведение не изменилось

## Status

`pending`
