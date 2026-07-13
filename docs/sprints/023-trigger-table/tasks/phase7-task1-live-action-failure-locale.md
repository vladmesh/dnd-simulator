# Task: Locale server-rendered action failure в live session

**Date:** 2026-07-14
**Sprint:** 023-trigger-table
**Phase:** 7 — Follow-up post-audit E2E locale

## Description

Закрыть оставшийся post-audit E2E blocker: в EN player session failed action, например melee attack
за пределами reach, приходит в `action_result.error` на русском. Ошибка создаётся dispatcher/handler
в round thread до того, как Phase 6 применяет `language_context(session.lang)` к построению WS payload,
поэтому перевод уже зафиксирован в process-default locale.

Граница задачи: session-scoped locale должна действовать во время выполнения player action и создания
его `ActionResult`, а не только во время serialisation ответа. Сохранить containment ожидаемых action
errors: неуспешное действие не завершает round loop и следующий ход остаётся доступен.

Mixed-language label расы соседнего существа явно не входит в эту задачу: это server-rendered content
name, для которого `DND_LANGUAGE` и UI locale сейчас являются отдельными контрактами. Он non-blocking
для повторного E2E и требует отдельного продуктового решения, а не расширения locale propagation fix.

## Tests First

- Создать EN live player session, довести её до combat и отправить melee attack по цели вне reach;
  полученный `action_result.error` содержит English `Target too far` и не содержит русский перевод.
- Повторить тот же live WS сценарий для RU session и убедиться, что ошибка остаётся русской.
- После смены language уже подключённой EN session на RU следующая failed action приходит на русском,
  а следующий допустимый action проходит, не останавливая round loop.
- Проверить unit-level session/round boundary с process default RU: action failure в session с lang EN
  создаётся на английском до включения в `action_result` message.

## Implementation

Найти session-owned execution boundary для player action в `GameSession`/`Round` и обернуть сам dispatch
и создание `ActionResult` в `language_context(self.lang)`. Не локализовать строку повторно в transport
builder и не передавать process-global язык в rules handlers: правила продолжают использовать gettext
context только в момент формирования ожидаемой ошибки.

Расширить существующие session/WS action-error regression tests вместо добавления browser-only покрытия;
если меняется thread context, закрепить, что session locale устанавливается в round thread до вызова
handler. После implementation повторить targeted post-audit E2E scenario 3.1–3.2.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] EN live action failure is English even when process default is RU
- [x] RU live action failure remains Russian
- [x] Changing an open session locale affects the next failed action
- [x] Failed action remains contained and the round accepts a later valid action
- [x] Nearby-creature race label is recorded as a deferred non-blocking issue, not folded into this fix

## Status

`done`

## Developer Notes

`Round` now accepts a session-owned action context and `GameSession` supplies `language_context(self.lang)` for every dispatch. The WS regression verifies English first, Russian after changing the same session, and a succeeding action afterward; the reaction fixture now supplies the new null action scope because it constructs `Round` without `__init__`. The test began RED on the stale round-thread locale and the full local gate passed: 2541 backend unit tests and 288 frontend tests.
