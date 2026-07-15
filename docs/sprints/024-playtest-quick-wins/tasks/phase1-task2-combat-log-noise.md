# Task: Чистота боевого лога

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 1 — Читаемость и тактика боя

## Description

Два бэкенд-фикса про то, что попадает в логи во время боя.

### 1. `npc-action-errors-leak-to-log`

`on_action` (`service/session.py:372-382`) кладёт `msg["error"] = error` после действия любого существа, без фильтра по актору (бюджет там уже гейтится на `creature.id == player.id`, ошибка — нет). Фронт рендерит это в боевом логе игрока — технические отказы чужих ходов («Туда не пройти, путь заблокирован» от волка) текут игроку.

Фикс: проставлять `msg["error"]` только когда `creature.id == player.id` (тот же гейт, что у budget). Отказы чужих актёров в лог игрока не попадают.

### 2. `faction-hostility-check-cost`

`check_faction_hostility` (`layers/entities/awareness_builder.py:425-453`) вызывается на каждую пару существ при пересборке awareness (после каждого действия раунда) → O(N²) на ребилд. Две проблемы:

- **Лог-спам:** `logger.info("faction_hostility_check", ...)` на каждую пару. В живой партии 2026-07-15 с 11 волками — 70.8% всего backend-лога (3610/5102 строк), топит сигнал. Опустить до `logger.debug`.
- **Аллокация:** `make_relation_fn(query_fn)` конструируется заново на каждую пару (строка 433). Строить один раз на ребилд и переиспользовать.

Фикс: `logger.info` → `logger.debug` в `check_faction_hostility`; вынести построение `get_faction_relation = make_relation_fn(query_fn)` из per-pair пути так, чтобы на один ребилд awareness он создавался один раз, а не N² раз. Мемоизация faction-pair отношений на ребилд опциональна, но `relation_fn` точно строить единожды.

`get_faction_relation` (метод рядом, строка ~412) конструирует то же самое для другой ветки — свести к одному источнику при рефакторе, не меняя семантику `effective_relation`.

## Tests First

Продуктовые сценарии:

- **Error leak:** боевой ход, где NPC совершает действие с отказом (напр. заблокированное перемещение), а затем ход игрока. В событии, доставленном игроку по чужому действию, поля `error` нет. Для действия самого игрока с отказом `error` присутствует (регресс — гейт не ломает игроцкие ошибки).
- **Relation fn once:** пересборка awareness для наблюдателя среди N существ вызывает построение relation-функции (или нижележащий кросс-слойный faction-запрос) ограниченное число раз на ребилд, а не O(N²). Проверяется через spy/счётчик на `make_relation_fn` (или на `query_fn`): при N существах число построений `relation_fn` не растёт квадратично.
- Регресс: результат `check_faction_hostility` (hostile/не hostile) не изменился для дружественных/враждебных/нейтральных пар и пар с персональной репутацией.

## Implementation

- `service/session.py` — в `on_action` обернуть `msg["error"] = error` в гейт `creature.id == player.id`. Оставить `msg["actor"]`/`msg["action"]` как есть.
- `layers/entities/awareness_builder.py`:
  - `check_faction_hostility`: `logger.info` → `logger.debug`.
  - Построение `make_relation_fn(query_fn)` вынести на уровень ребилда (там, где идёт цикл по существам — вызовы на строках 243 и 336), передавать готовую `relation_fn` вниз вместо `query_fn`, либо мемоизировать per-rebuild. Не менять сигнатуру публичных методов сверх необходимого; не менять семантику `effective_relation`.
- Гоча: `make_relation_fn` строится и в `get_faction_relation` (строка 412), и в `check_faction_hostility` (433) — при выносе свести к одному построению на ребилд.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Отказы чужих ходов (не игрока) не попадают в `error` события игрока
- [ ] `faction_hostility_check` логируется на DEBUG, не на INFO
- [ ] `make_relation_fn` строится один раз на ребилд awareness, не на каждую пару
- [ ] Семантика hostility (дружба/вражда/нейтралитет/репутация) не изменилась

## Status

`done`

## Developer Notes

Done 2026-07-16. `make check` green (backend 2554, frontend 289).

**Error leak.** Extracted the `on_action` closure body into `build_action_result` (transport_payloads.py), matching the existing `build_round_state`/`build_turn_state` seam, so the gate is unit-testable without a live round thread. `actor`/`action` broadcast for any creature; `error` and `budget` gated on `creature.id == player.id`. Previously `error` had no gate (only budget did), so a wolf's blocked-path refusal leaked into the player's log. Dropped the now-unused `_budget_to_dict` import from session.py.

**Relation fn once.** `check_faction_hostility` and `_resolve_relation` each built `make_relation_fn(query_fn)` per pair → ~2N closures per awareness rebuild. Split the hostility logic into a private `_hostility_from_relation(observer, other, relation_fn)` that takes a prebuilt callback; `build_combat_awareness` and `build_nearby_entities` now build the relation fn once and pass it down. `check_faction_hostility(observer, other, query_fn)` kept its public signature (builds once, delegates) so the existing `test_reputation_awareness.py` regression tests pass unchanged. `_resolve_relation` is private, so its signature changed to take `relation_fn`.

**Log level.** `faction_hostility_check` moved from `logger.info` to `logger.debug` inside `_hostility_from_relation`. (`awareness_nearby` info-line is one-per-rebuild, not per-pair — left as is, out of scope.)

Test discriminates the allocation: 8 nearby creatures went from 16 relation-fn builds to 1.
