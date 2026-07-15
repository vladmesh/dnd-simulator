# Task: Единый учёт бюджета движения в бою

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 1 — Читаемость и тактика боя

## Description

Переформулировано 2026-07-16 после разведки кода. Исходная премиса айтема `combat-move-budget-not-consumed` («компасное движение в бою не тратит бюджет, монстр пересекает карту за ход») **неверна**: бюджет движения списывается — но не в хендлере, а в диспетчере. `ActionDispatcher.dispatch` (`service/action_dispatcher.py:134-136`) после успешного хендлера зовёт `TurnBudget.consume(action_cost(action))`, а `MOVE` объявлен `cost_type=MOVEMENT` (`core/action_defs.py:212`), то есть диспетчер списывает `movement_ft = запрошенные ft`. Воспроизведено: существо speed=30 через реальный диспетчер проходит ровно 30ft (6 шагов по 5ft), затем `check_budget` отбивает `move` с «Недостаточно ресурсов». Кайтинг уже работает; «пересечение всей карты» этим механизмом не воспроизводится (вероятно dash или мелкая карта — вне этого таска).

Настоящая проблема — **раздвоенный и неконсистентный учёт стоимости движения**:

- `MOVE` (компас) — `cost_type=MOVEMENT`, бюджет списывает диспетчер по **запрошенным** `ft`.
- `MOVE_TO` (клик/BFS) — `cost_type=FREE`, бюджет списывает **хендлер** по факту пройденного (`spent`, с диагональю 5/10 через `step_cost`).
- `DASH` — `cost_type=ACTION`, хендлер **добавляет** `+speed` к движению.

Movement — исполнительная стоимость: сколько реально пройдено, известно только после резолва (стены, обрыв пути на OA-смерти, диагональное чередование). Декларативный `action_cost` этого знать не может — он чистая функция от параметров, без карты. Поэтому `MOVE_TO`/`DASH` правильно отдают учёт движения хендлеру, а `MOVE` — сидит на заборе: списывает **запрошенные** ft, а не фактически пройденные. Латентные баги, замаскированные тем, что RuleBrain ходит ортогонально по 5ft:

- **Диагональ недосписывается** — диспетчер берёт плоские 5 за диагональный шаг, `grid_distance` даёт ×1.5.
- **Заблокированный/частичный шаг пересписывается** — запрос `ft=30`, стена на 10ft → двигается 10, списывается 30.

Дополнительно: гейт мозга (`movement_remaining` в awareness) и фактическое списание (запрошенные ft в диспетчере) считаются по-разному → расхождение «мозг думал что хватит, а списалось иначе». Совпадают только в ортогональном 5ft-случае.

## Почему так (обоснование)

Инвариант: **диспетчер владеет только осью действий (actions / bonus_actions / reaction); `movement_remaining` мутируется исключительно в movement-хендлерах.** Тогда:

- Учёт движения — в одном месте, по факту пройденного. Диагональ/частичный шаг чинятся сами собой.
- Awareness пересобирается каждую итерацию цикла хода с живым `turn_budget` (`round.py:269`), поэтому гейт мозга и списание — гарантированно одно и то же число. Отбивка честна по построению.
- Мозгу нужна видимость остатка, чтобы планировать «подбежал-ударил-отбежал». Игрок (`BudgetDisplay`/`BattleMap.reachable`) и RuleBrain (`rule_brain.py:274`) её уже имеют; LLM-промпт — нет (только `Speed`, дистанции). Единственная реальная дыра видимости.

## Scope

Три части, все в одном таске:

**A. Единый учёт (Option C).**
- `core/action_defs.py`: `MOVE` `cost_type` MOVEMENT → FREE; удалить член enum `CostType.MOVEMENT` (после снятия у него не остаётся потребителей).
- `rules/actions.py`: убрать `case CostType.MOVEMENT`.
- `rules/handlers/movement.py` `handle_move`, боевая ветка: после `moved_ft = grid_distance(...)`, если `budget is not None and moved_ft > budget.movement_remaining` → reject `_("Not enough movement")` **до** OA/`set_position` (не двигаться); иначе после успешного `set_position` — `budget.movement_remaining -= moved_ft`. Ранний `return` при гибели mover в OA бюджет не трогает.

**B. Внятная отбивка в `handle_move_to`.**
- Различать «стена, пути нет» и «путь есть, но длиннее бюджета». В ветке `if not path`: fallback-пересчёт достижимости без лимита бюджета; если цель достижима в принципе → `_("Not enough movement to reach there")`, иначе `_("No path to target")`.

**C. Видимость движения для LLM.**
- `llm/brain.py` `_combat_awareness_to_dict`: добавить `movement_remaining` (из `aw.turn_budget`, fallback `self_speed`); пометить nearby-цели достижимыми в этот ход (`distance_ft <= movement_remaining`).
- `llm/prompts.py`: строка статуса «Movement remaining: N ft»; отметка достижимых целей в списке nearby.

Новые i18n-строки переводятся в `locale/ru` (проект RU-default).

## Tests First

- `handle_move` (боевая ветка): одиночный 5ft `move` уменьшает `movement_remaining` ровно на `grid_distance`; серия шагов упирается в speed (speed=30 → 6 шагов, дальше reject, позиция замерла, суммарно ≤ speed); `move`, требующий больше остатка → `success=False`, позиция и бюджет не меняются, `emit` не вызван; гибель mover в OA не списывает бюджет.
- Регресс диспетчера: `test_dash_adds_effective_speed_without_moving_then_move_spends_it` остаётся зелёным (dash → 45, компасный move 5ft → 40) — ровно одно место списывает.
- `handle_move_to`: цель за пределами бюджета (но достижимая) → `Not enough movement to reach there`; цель за стеной → `No path to target`; успешный путь по-прежнему списывает `spent`.
- `_combat_awareness_to_dict`: содержит `movement_remaining`; nearby в пределах остатка помечены достижимыми.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `MOVE` FREE, `CostType.MOVEMENT` удалён, `handle_move` списывает фактический `moved_ft` атомарно
- [ ] Диагональ/частичный компасный шаг списываются по факту, не по запросу
- [ ] `handle_move_to` различает «нет пути» и «не хватает движения»
- [ ] LLM-промпт показывает остаток движения и достижимые цели
- [ ] `handle_move_to` / `handle_dash` числовое поведение бюджета не изменилось

## Status

`done`

## Developer Notes

Разведка перевернула таск: исходная премиса «бюджет не тратится» неверна. `ActionDispatcher.dispatch` уже списывал движение через `TurnBudget.consume(action_cost(MOVE))` (MOVE был `cost_type=MOVEMENT`), а `check_budget` гейтил. Воспроизведено скриптом: speed=30 через реальный диспетчер = ровно 6 шагов по 5ft, дальше reject. Кайтинг работал. Backlog-анализ читал только тело `handle_move` и не увидел диспетчерский слой.

Реализовано (унификация оси движения):
- **A.** `MOVE` → `cost_type=FREE`, член enum `CostType.MOVEMENT` и его ветка в `_cost_type_to_cost` удалены. `handle_move` (боевая ветка) теперь сам проверяет `moved_ft <= movement_remaining` до OA/`set_position` (reject целиком, без частичного перемещения) и списывает `moved_ft` по факту. Гибель mover в OA бюджет не трогает.
- Добавлен валидатор `check_movement_available` (`rules/validation.py`): раз MOVE стал FREE, `check_budget` больше не отсекает MOVE при 0 движения — новый чек возвращает `No movement remaining`, сохраняя «0 движения → MOVE недоступен» (регрессия в `BaseActionProvider`, который гейтит через `validate_action`).
- **B.** `handle_move_to`: при `not path` — fallback-пересчёт достижимости без лимита бюджета; цель достижима в принципе → `Not enough movement to reach there`, иначе `No path to target`. Extra-Dijkstra только на failure-пути.
- **C.** `_combat_awareness_to_dict` (`llm/brain.py`) отдаёт `movement_remaining` (fallback `self_speed`) и метит nearby-цели `reachable` при `distance_ft <= movement_remaining`; `prompts.py` рендерит «Movement remaining this turn: N ft» и «(in reach this turn)».

Обновлённые старые тесты (интенциональная смена контракта, не подгон): `test_action_dispatcher` (`test_move_consumes_movement`/`test_move_insufficient_movement_rejected` переписаны на полный боевой ctx — бюджет владеет хендлер; `test_dash_...then_move_spends_it` остался зелёным без правок), `test_multi_action.test_move_costs_movement` → `test_move_is_free_at_dispatcher` (movement_ft==0), `test_session_awareness` (cost_type `movement`→`free`). Новые i18n-строки переведены в `locale/ru`, `.mo` перекомпилирован.

Симптом живой партии «монстр через карту» этим механизмом не воспроизводится — вероятно dash или мелкая карта, вне таска (отмечено в бэклоге/спринте).
