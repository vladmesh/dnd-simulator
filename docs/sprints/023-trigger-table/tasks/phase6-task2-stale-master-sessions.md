# Task: Не показывать stale saved sessions в Master

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 6 — Post-audit E2E fixes

## Description

Закрыть E2E-блокер Master Sessions: список не должен выдавать Manage-ссылку для дискового
`session_<id>` сейва, который не загружен в `GameService` и поэтому возвращает 404 по
`/api/master/sessions/{id}`. Master list должен отображать только управляемые active sessions, пока
отдельного пользовательского flow загрузки saved session нет.

Граница задачи: контракт `GET /api/master/sessions`, service list и тесты frontend/API. Не удалять
сейвы с диска, не менять save/load API и не подменять Manage неявной загрузкой мира.

## Tests First

- Создать active session и отдельный сохранённый `session_<id>` на диске, затем запросить Master
  session list: active session присутствует, stale saved id отсутствует.
- Проверить, что идентификатор active in-memory session, для которого также существует autosave,
  появляется ровно один раз и Manage endpoint возвращает world state.
- В Master UI отрендерить ответ со списком active sessions и проверить, что каждая видимая Manage-ссылка
  ведёт на доступную session; stale saved entry не создаёт ссылку и не вызывает 404 при загрузке экрана.
- Сохранить существующие сценарии list/delete session: удаление active session убирает её из списка и
  не меняет независимые save files.

## Implementation

Сделать `GameService.list_sessions()` источником управляемых active sessions, а scanning дисковых
`session_` autosave не включать в Master response. Если save metadata требуется в будущем, выделить
отдельный read-only listing/load flow вместо смешивания его с live-session contract.

Обновить API и компонентные тесты под чёткую семантику `GET /api/master/sessions`; frontend transport
и маршрутизация остаются прежними, поскольку response больше не содержит неуправляемых id.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Master list содержит только session ids, доступные через Manage endpoint
- [x] Stale `session_<id>` files не создают строку или 404-ссылку в Master UI
- [x] Active session с autosave появляется в list ровно один раз
- [x] Existing save/load commands сохраняют своё поведение

## Status

`done`

## Developer Notes

`GameService.list_sessions()` теперь возвращает только sessions из in-memory registry. Регрессия создаёт
active autosave и независимый stale `session_` save: active id виден один раз и доступен через Manage,
stale id в список не попадает.
