# Task: Lifecycle boundary failure handling

**Date:** 2026-07-12
**Sprint:** 022-intents-travel
**Phase:** 5 — Bounded round shutdown

## Description

Провести bounded-stop контракт через три пользовательских lifecycle-пути: disconnect последнего игрока,
`load_game()` и deferred eviction. Ни один путь не должен зависать, заменять мир или удалять сессию, пока
старый round thread жив. Ошибка остановки должна быть видна в логах и оставлять сессию в состоянии, которое
можно восстановить повторной остановкой или реконнектом после завершения callback.

Успешные пути не меняются: disconnect сразу паузит round и ставит eviction timer, load очищает cached
transport state и атомарно восстанавливает snapshot только после завершения старого round, eviction делает
autosave и удаляет только уже остановленную сессию.

## Tests First

- При блокирующем callback disconnect последнего player listener возвращается за ограниченное время,
  не запускает второй round при конкурентном reconnect и не маскирует timeout в логах.
- `load_game()` при timeout не вызывает loader: world, dice RNG, brains и cached turn остаются от старого
  состояния; после завершения callback повторный load полностью восстанавливает snapshot.
- Deferred eviction при timeout не вызывает `_on_empty`, не autosave-ит потенциально изменяемый мир и не
  удаляет сессию из registry; следующий успешный empty-check может завершить eviction.
- Обычные disconnect, load и eviction продолжают проходить существующие happy-path проверки.

## Implementation

Обработать lifecycle-ошибку в `remove_listener()`, `replace_world_state()` и `_run_evict_check()` на границах,
где различается политика продолжения. Load должен пробрасывать понятную ошибку вызывающему API и не входить
в loader. Фоновый eviction должен логировать отказ и не вызывать `_on_empty`; при необходимости безопасно
поставить повторную проверку, не создавая busy loop. Disconnect не должен считать round остановленным и
разрешать новый loop, пока сохранённый thread жив.

Использовать существующие `_round_transition_lock`, eviction timer и session registry. Не добавлять
transport-specific флаги и не расширять фазу общей декомпозицией `session.py`.

Ключевые файлы: `service/session.py`, `service/commands_save.py`, `service/game_service.py`,
`tests/unit/test_session_lifecycle.py`, `tests/unit/test_commands_save.py`, lifecycle/autosave tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check-backend`)
- [x] Failed stop never replaces world or evicts the live session
- [x] Конкурентный reconnect не создаёт второй round loop
- [x] Фоновый timeout залогирован и не теряется в Timer thread
- [x] После завершения callback load и eviction можно успешно повторить

## Status

`done`

## Developer Notes

Disconnect теперь перехватывает `RoundStopTimeoutError`, пишет `disconnect_stop_failed` и всё равно ставит
deferred empty-check; reconnect сериализован тем же `_round_transition_lock`, а живой loop остаётся привязан к
сессии. Eviction при timeout пишет `evict_stop_failed`, не вызывает `_on_empty` и планирует повторную проверку
через обычный grace interval, поэтому autosave и удаление registry entry не происходят на живом round.

Load сохранил правильную fail-fast семантику: `replace_world_state()` пробрасывает timeout до очистки cached turn
и входа в loader. Новый round-trip тест фиксирует неизменность world, dice RNG, brain/lifecycle и transport cache,
затем успешную повторную загрузку. Полный `make check` зелёный: backend 2479, frontend 282.
