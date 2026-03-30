# Task: check_reactions rewrite + on_leave_reach callback

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 2 — Movement Integration + Round Wiring

## Description

`Round.check_reactions` — скелет, который вызывает `choose_action` вместо `choose_reaction`, не передаёт `ReactionTrigger`/`ReactionOption`, помечен TODO. Переписать на рабочую версию.

Добавить `on_leave_reach` callback на `ActionContext` — инъекция из Round в movement handlers. Round создаёт замыкание, handler вызывает при выходе мувера из reach врага. Handler не импортирует Round.

Конкретные изменения:

1. **`ActionContext`** (`rules/validation.py`): добавить `on_leave_reach: OnLeaveReachFn | None = None`. Тип: `Callable[[Creature, Position, Position, list[Creature]], bool]` — мувер, from_pos, to_pos, reactors. Возвращает `True` если мувер жив после реакций.

2. **`Round.check_reactions`** (`round.py`): переписать сигнатуру — принимает `ReactionTrigger`, `list[ReactionOption]`, `list[Creature]` (candidates). Для каждого кандидата вызывает `creature.brain.choose_reaction(creature, trigger, options)`. Если не SKIP — диспатчит через `_execute_action`. Возвращает список выполненных реакций.

3. **`Round._make_on_leave_reach`**: замыкание, которое строит `ReactionTrigger(LEAVING_REACH, ...)`, список `ReactionOption` с OA, вызывает `check_reactions`, возвращает `mover.is_alive`.

4. **`Round.run_combat_turn`**: передаёт `on_leave_reach` в `ActionContext`.

## Tests First

Unit-тесты в `tests/unit/test_check_reactions.py`:

- **check_reactions вызывает choose_reaction с правильным trigger и options.** Два кандидата с реакциями: RuleBrain (всегда OA), mock-brain (всегда SKIP). Проверить: один OA выполнен, один SKIP.
- **check_reactions пропускает мёртвых и без бюджета.** Кандидат с reaction=0, мёртвый кандидат, живой с reaction=1. Только живой получает choose_reaction.
- **check_reactions consume reaction после OA.** Reactor начинает с reaction=1, после OA reaction=0.
- **on_leave_reach callback возвращает True если мувер жив, False если мёртв.** Mock emit_fn, мувер с 1 HP, OA наносит урон → возвращает False.
- **ActionContext принимает on_leave_reach.** Просто конструирование с callback, проверка что доступен.

## Implementation

1. Добавить `OnLeaveReachFn` type alias и поле на `ActionContext`.
2. Переписать `check_reactions` — новая сигнатура, `choose_reaction` вместо `choose_action`, правильный dispatch.
3. Создать `_make_on_leave_reach` на Round — замыкание.
4. В `run_combat_turn` передать callback в ctx.

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] check_reactions использует choose_reaction, не choose_action
- [ ] on_leave_reach callback на ActionContext
- [ ] Round передаёт callback в контекст каждого combat turn
- [ ] Existing tests pass (`make check`)

## Status

`pending`
