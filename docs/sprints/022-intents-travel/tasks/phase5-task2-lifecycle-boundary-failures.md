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

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] Failed stop never replaces world or evicts the live session
- [ ] Конкурентный reconnect не создаёт второй round loop
- [ ] Фоновый timeout залогирован и не теряется в Timer thread
- [ ] После завершения callback load и eviction можно успешно повторить

## Status

`pending`
