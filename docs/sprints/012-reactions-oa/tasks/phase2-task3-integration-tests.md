# Task: Integration tests — OA fires during movement

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 2 — Movement Integration + Round Wiring

## Description

End-to-end тесты через docker compose стек (REST + WebSocket). Проверяют что вся цепочка работает: движение → find_oa_triggers → check_reactions → choose_reaction → OA handler → урон.

## Tests First

Интеграционные тесты в `tests/integration/test_opportunity_attacks.py`:

- **OA срабатывает при выходе из reach.** Два существа в бою на расстоянии 5ft. Мувер двигается в сторону от врага. Враг (RuleBrain) делает OA. В событиях есть OPPORTUNITY_ATTACK с правильным attacker и target. У мувера снялось HP.

- **Disengage предотвращает OA.** Мувер делает Disengage (тратит action), затем двигается. В событиях НЕТ OPPORTUNITY_ATTACK. Враг сохраняет реакцию.

- **Рог: Cunning Action Disengage (bonus) + Attack (action) + безопасное движение.** Рог делает Disengage как bonus action, Attack как action, затем двигается. OA не срабатывает. Все три действия в одном ходу.

- **OA убивает мувера — движение прервано.** Мувер с 1 HP двигается мимо врага. OA убивает. Мувер мёртв, позиция = клетка где стоял при выходе из reach (не destination).

- **Два врага — оба бьют OA.** Мувер проходит мимо двух врагов на разных позициях. Оба делают OA (у обоих есть реакция). Два OPPORTUNITY_ATTACK события.

## Implementation

Использовать паттерн из `tests/integration/test_combat_turns.py`:
- `_create_session` для создания сессии с нужным контентом
- WebSocket для получения ходов и отправки действий
- `_collect_events_until_turn` для сбора событий
- `_find_event` для проверки конкретных событий

Нужен test world с двумя-тремя существами на battle map в правильных позициях. Возможно, custom YAML для тестового мира или создание через API.

## Acceptance Criteria

- [ ] Все 5 сценариев проходят через docker compose стек
- [ ] OA корректно наносит урон
- [ ] Disengage корректно предотвращает OA
- [ ] Смерть мувера прерывает движение
- [ ] `make test-integration` проходит

## Status

`done`

## Developer Notes

Three bugs were found and fixed during implementation:

1. **Double reaction consumption (crash):** `handle_opportunity_attack` manually consumed `turn_budget.reaction -= 1`, but the dispatcher also called `turn_budget.consume(cost)` on success. The handler's manual consumption was removed since the dispatcher handles it via ActionDef's `CostType.REACTION`.

2. **Missing initial turn_budget (OA never triggered):** When combat starts, creatures that haven't had their first turn have `turn_budget = None`. `find_oa_triggers` skips creatures with no budget. Fix: `start_combat()` now initializes a reaction-only budget (`TurnBudget(actions=0, bonus=0, movement=0, reaction=1)`) for all combatants.

3. **OPPORTUNITY_ATTACK event not logged:** `EventType.OPPORTUNITY_ATTACK` was missing from `_LOGGED_EVENTS` in `EntitiesLayer`, so the event was emitted but never stored in the location log and never sent to the WebSocket client.

Tests: 5 new integration tests, 1 unit test modified (reaction consumption assertion). All 111 integration tests + 1648 unit tests pass.
