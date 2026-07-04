# Task: round.py — awareness-сборка в AwarenessBuilder, чистка loop

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

## Description

`round.py` (623) — оркестратор, в который просочилась сборка awareness и накопились дефекты цикла активации. **Слияние combat/peaceful turn-loop в этой задаче НЕ делаем** — отменено ре-скоупом (peaceful-ход будет переписан намерениями по [simulation-core](../../brainstorms/simulation-core.md), боевой останется PHB). Чистим только следующее (поведение неизменно):

1. **Awareness-сборка → `AwarenessBuilder`.** Билдеры в `Round` (`_build_available_items:103`, `_build_equipped:117`, `_compute_reachable:139`, `_build_merchants:158`, `_build_combat_awareness:270`) патчат `replace()`-ом DTO, который `AwarenessBuilder` только что собрал (`round.py:270-296`), а `_build_equipped` в цикле переимпортирует `Item` ради assert. Перенести эти билдеры в `AwarenessBuilder` (`layers/entities/awareness_builder.py`), `Round` зовёт один метод. `_build_merchants` читает merchant-провайдер — провайдер уже развязан в фазе 1 (`purity-providers`), передать world-query аргументом, не тянуть I/O в builder.
2. **`resolve_abstract_move` → `rules/movement.py`.** `round.py:341` лениво импортирует его из `service.session` — оркестратор лезет вверх в слой, от которого `CreatureHost` Protocol и должен развязывать. Функция чистая — перенести в `rules/movement.py`, `service.session` реэкспортирует для обратной совместимости, `round.py` зовёт из rules.
3. **Одна активация за итерацию loop.** `run_loop` (`:576`) зовёт `_activate()`, затем `run_round()` активирует повторно (`:530`) — тяжелейшая пороундовая операция гоняется дважды, латентный дабл-спавн. Сделать одного владельца активации за итерацию; query/emit fns строить один раз и передавать.
4. **Выкинуть dead-параметр.** `_build_available_items` (`:103-113`) несёт неиспользуемый `available_actions` (зовётся `:283,398`). Убрать (или реально фильтровать по нему — но по ре-скоупу минимально: убрать).

Вне скоупа: `_run_turn_loop` merge (отменён), рефактор самой логики активации (изолируем в task 4, не полируем), inbox/намерения (будущая модель).

## Tests First

Поведение неизменно (пиновка, большинство есть в `test_round`):

- Боевой ход: multi-action loop с бюджетом, end_turn, OA-каллбэк, consecutive-failures → end. Awareness, которую видит brain, идентична до/после переноса билдеров (пиновка полей: available_items, equipped, reachable, merchants).
- Peaceful ход не сломан переносом билдеров.
- Активация: за одну итерацию `run_loop` `update_activation` вызывается ровно один раз (счётчик вызовов через spy/фейк host) — RED до фикса дабл-активации, GREEN после.
- `abstract move` (toward/away_from) резолвится в конкретное направление тем же результатом после переноса в rules.

## Implementation

1. Пиновка awareness-полей + счётчик активаций (RED на дабл-активацию).
2. Перенести `resolve_abstract_move` в `rules/movement.py` (+реэкспорт). Снять ленивый импорт в round.
3. Перенести билдеры в `AwarenessBuilder`; `Round._build_combat_awareness` схлопнуть в вызов builder-метода, убрать `replace()`-патчи и цикловой реимпорт `Item`.
4. Дедуп активации в `run_loop`/`run_round`: один вызов за итерацию, fns строятся один раз. Убрать dead `available_actions`.

Gotcha: `AwarenessBuilder` уже владеет `build_awareness/build_combat_awareness/build_nearby_entities` — билдеры round встраиваются рядом, не создавать второй класс. Merchant/reachable читают world-query — прокинуть callback, не импортировать слой в builder (инвариант направления зависимостей). Дабл-активация: следить, чтобы fast-forward-ветка (`_fast_forward` тоже зовёт `_activate`) не потеряла активацию.

## Acceptance Criteria

- [ ] Awareness-билдеры перенесены из `Round` в `AwarenessBuilder`; `replace()`-патчи и цикловой реимпорт `Item` убраны
- [ ] `resolve_abstract_move` в `rules/movement.py`, `round.py` не импортирует из `service.session`
- [ ] `update_activation` — ровно один вызов за итерацию loop (тест-счётчик GREEN)
- [ ] Dead `available_actions`-параметр убран
- [ ] Combat/peaceful-цепочки в `test_round` GREEN; awareness-поля идентичны
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- **Awareness builders → AwarenessBuilder**: moved `_build_available_items` (dead `available_actions` param dropped), `_build_equipped` (in-loop `Item` re-import + assert gone), `_compute_reachable`, `_build_merchants` out of `Round` into `AwarenessBuilder` as `build_available_items`/`build_equipped`/`compute_reachable`/`build_merchants`. Exposed on the `CreatureHost` protocol + `EntitiesLayer` delegation so `Round` stays layer-agnostic (it can't import the concrete layer). `Round` now calls `self._host.build_*`; the two `replace()` assembly sites keep only the dispatcher-sourced `available_actions`/`turn_budget` (legitimately Round's — the dispatcher is Round-owned).
- **Merchant filter dedup**: extracted `active_merchants_at(entities, location_id, hour)` (module-level in `awareness_builder.py`); both `EntitiesLayer.get_merchants_at` and `AwarenessBuilder.build_merchants` call it.
- **resolve_abstract_move → rules/movement**: pure version takes `combat: CombatState | None` directly. `service.session.resolve_abstract_move` kept as a host-aware compat wrapper (delegates after `host.get_combat`), so `session.py:522` and `test_session_lifecycle` are unchanged. `round.py` imports the rules version top-level and passes `self._host.get_combat(...)` — no more reaching up into `service.session`.
- **One activation per loop iteration**: `run_round(*, skip_activation=False)`; `run_loop` passes `skip_activation=True` (it already `_activate()`d for the active/fast-forward check). Standalone `run_round()` callers (many tests) still activate. Pinned by new `test_round_activation_once` (standalone→1, skip→0, one loop iteration→1; was 2 before).
- **Hidden caller**: `session.build_equipped_payload` used `Round._build_equipped` → repointed to `AwarenessBuilder.build_equipped`. Tests `test_inventory_awareness` updated (Round static methods → AwarenessBuilder).
- **Not done (per re-scope)**: combat/peaceful `_run_turn_loop` merge — explicitly cancelled. `round.py` 623 → ~548.
- `make check` green.
