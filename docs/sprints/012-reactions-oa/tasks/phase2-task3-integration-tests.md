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

`pending`
