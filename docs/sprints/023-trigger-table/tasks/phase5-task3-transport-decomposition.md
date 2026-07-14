# Task: Разделение backend и frontend transport builders

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 5 — Post-audit refactor

## Description

Разгрузить `service/session.py` и `frontend/src/transport/apiClient.ts` без изменения REST/WS wire-контракта.
Backend payload builders не относятся к round lifecycle и locking, frontend request core не должен жить в одном
файле с master world/content/session API и player API.

Публичные точки входа сохраняются: service-команды и adapters получают те же `PlayerStatusData`/message dict,
frontend callers продолжают импортировать `api` и `ApiError` из `transport/apiClient` без массовой миграции
компонентов.

## Tests First

- Сравнить player status одного персонажа через REST и WS turn: HP/AC, journey, resources, inventory и equipped
  имеют одинаковые значения и wire shape после вынесения builders.
- Провести peaceful action и reaction/combat callback через `GameSession`: сообщения `turn`, `action_result`,
  `round_result` и `reaction_prompt` сохраняют обязательные поля и JSON-safe event data.
- Во frontend fetch-тестах вызвать representative world/content/session/creature/save/player методы и закрепить
  HTTP method, URL, query encoding, body и типизированную ошибку `ApiError`.
- Проверить, что существующий `api.master`/`api.player` facade вызывает выделенные domain clients и не меняет
  импортный контракт компонентов.

## Implementation

Вынести awareness/event/budget/reaction/location/player-status serialization из `session.py` в focused
service payload module. `GameSession` оставляет lifecycle, locks, listener registry и wiring round callbacks;
commands_player импортирует builder из нового владельца. Не переносить доменные расчёты в API adapter.

Во frontend выделить общий request core (`ApiError`, verbs, JSON parsing), master clients по устойчивым доменам
и player client. `apiClient.ts` собрать как короткий compatibility facade. Общие API types остаются в
`types/api`; не дублировать request/error logic между domain clients.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] REST и WS player/event payloads сохраняют прежнюю форму и значения
- [ ] `GameSession` не владеет transport serialization helpers
- [ ] Frontend domain clients используют один request/error implementation
- [ ] Существующие импорты `api` и `ApiError` из `apiClient` продолжают работать
- [ ] `service/session.py` и `frontend/src/transport/apiClient.ts` заметно уменьшаются

## Status

`done`

## Developer Notes

Сериализация player/round/reaction payload вынесена в `service.transport_payloads`; `GameSession` оставил lifecycle, locks и callback wiring. Frontend разбит на общий request core и domain clients, а `apiClient.ts` сохранил прежние exports как 21-строчный facade. Покрыты wire paths для world/content/session/creature/save/player; полный local gate зелёный.
