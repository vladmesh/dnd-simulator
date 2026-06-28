# Task: Lair depletion — core death & optional chance

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 1 — Логова (Lairs)

## Description

Логово можно зачистить навсегда. Это замыкает машину состояний `ACTIVE → DEPLETED` и делает мир динамичным: убил ядро (босса) — логово мертво и больше не восстанавливается. Для логов без выраженного босса — опциональный шанс «иссякнуть» после полного вайпа.

Конкретно:

- **Деплит по ядру (основной, детерминированный).** Если существо-ядро гибнет во время визита, при синке дематериализации логово переходит в `DEPLETED`. `DEPLETED` логово больше никогда не материализуется (ни ядро, ни миньоны) и не респавнит на тике. Состояние терминальное.
- **Деплит по шансу (опциональный, для логов без ядра).** Для логова с `core is None`: после полного вайпа населения (0 живых миньонов при визите) кинуть `get_global_rng().random() < depletion_chance`; выпало → `DEPLETED`, иначе логово восстановится как обычно (задача 2). По умолчанию `depletion_chance = 0.0` → логово вечное.
- **Персистенс.** `DEPLETED` сохраняется в `EcologyLayer.get_state`/`load_state` (поле уже заведено в задаче 2; здесь — выставление и проверка терминальности после reload).

Это завершает Verify Фазы 1 из `sprint.md`: убил ядро → респавн выключен навсегда и переживает save/load.

## Tests First

Integration (для шанса — сидировать RNG через `set_global_seed`, чтобы ролл был детерминированным):

- Игрок входит в логово, убивает чифтейна (ядро) и всех гоблинов, уходит. Промотать время на несколько `respawn_interval` → при возврате логово пустое и **остаётся пустым** (ни ядро, ни миньоны не вернулись).
- Тот же сценарий, но ядро **не** убито (убиты только миньоны) → после интервала миньоны восстанавливаются (логово ещё `ACTIVE`, регрессия на задачу 2).
- Save/load после смерти ядра: убил ядро, ушёл, сохранил, загрузил, промотал время, вернулся → логово пустое (DEPLETED пережил reload).
- Логово без ядра (`core: null`) с `depletion_chance: 1.0`: полный вайп → уход → логово `DEPLETED`, респавна нет. С `depletion_chance: 0.0`: полный вайп → миньоны восстанавливаются.

## Implementation

- Детект смерти ядра — на синке дематериализации (`ActivationManager`): трекнутый instance-id ядра отсутствует среди живых в `_entities` → ядро погибло → в `LAIR_DEMATERIALIZED` передать `core_dead=True`; `EcologyLayer.handle_event` выставляет `DEPLETED`.
- Шанс деплита — тоже на синке: если `core is None` и живых миньонов 0, кинуть `get_global_rng().random()` против `depletion_chance`. Использовать **сидируемый** RNG (`rules/dice.get_global_rng`), а не `random.*` напрямую — иначе тест недетерминирован и нарушается `DND_DICE_SEED` (см. фикс sprint 017).
- Материализация и тик-респавн: ранний выход, если `state is DEPLETED` (ничего не спавнить, ничего не доливать).
- Gotcha: ядро тоже `temporary=True` и удаляется из `_entities` на смерти — поэтому «ядро живо?» определяется как «instance-id ядра ещё в `_entities` и alive», вычисляется в тот же момент, что и подсчёт выживших миньонов (задача 2).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Смерть ядра → `DEPLETED` навсегда, респавн выключен
- [ ] `depletion_chance` работает для логов без ядра, ролл сидируемый
- [ ] `DEPLETED` переживает save/load
- [ ] Логово с живым ядром продолжает респавнить (нет регрессии задачи 2)

## Status

`done`

## Developer Notes

- **Минимальная задача.** Вся инфраструктура легла в задаче 2 (`LAIR_DEMATERIALIZED` несёт `core_alive`/`alive_members`; респавн и материализация уже гейтят по `state is ACTIVE`; `state` уже персистится). Деплит это одно решение в `EcologyLayer._apply_lair_dematerialize`.
- **Логика.** `core_died = lair.core is not None and not core_alive` (детерминированный основной триггер); `chance_ran_dry` для безбоссовых: `core is None and not alive_members and depletion_chance > 0 and get_global_rng().random() < depletion_chance` (ролл только при полном вайпе, через short-circuit). Любой из них → `state = DEPLETED`. `DEPLETED` терминально: респавн/материализация уже пропускают не-ACTIVE логова, `state` уже в save/load.
- **Сидируемый RNG.** `get_global_rng()` из `rules.dice` (ecology уже импортирует из rules — `abstract_combat`, так что граница слоёв не нарушена). Для `depletion_chance` 1.0/0.0 пороги детерминированы и без seed (`random()` ∈ [0,1)), поэтому тесты не зависят от конкретного seed.
- **Тесты.** 5 новых в `TestLairDepletion` (core death деплитит навсегда; minion-only оставляет ACTIVE — регрессия задачи 2; core-death переживает save/load; coreless chance=1.0 деплитит; chance=0.0 респавнит). Хелперы вынесены на уровень модуля (`_reenter`, `_enter_kill_leave(kill_minions=, kill_core=)`), тесты задачи 2 переписаны под них (свои же тесты, поведение то же).
- **Линт.** ruff SIM102/SIM114 заставили схлопнуть вложенные/дублирующие ветки в два именованных булева + один `if core_died or chance_ran_dry`.
