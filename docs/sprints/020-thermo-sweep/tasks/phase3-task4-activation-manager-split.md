# Task: activation_manager split — encounters + materialization

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

## Description

`activation_manager.py` (626) несёт три разные ответственности: (1) собственно активация (`update_activation`: якорь-игрок, wake_at, dormant), (2) энкаунтеры (`_check_encounters`, `_roll_encounters`, `_is_daylight_at`, `_has_active_lair`, `_maybe_start_combat`), (3) материализация/дематериализация squad и lair (`_update_materialization`, `_materialize_squad`, `_dematerialize_squad`, `_update_lair_materialization`, `_materialize_lair`, `_treasury_core_alive`, `_sync_lair_treasury`, `_dematerialize_lair`).

**Важно (ре-скоуп):** саму activation-логику **не полировать и не переписывать** — её заменит машина намерений/триггеров ([simulation-core](../../brainstorms/simulation-core.md)). Цель — **изолировать** её от энкаунтеров и материализации, чтобы будущая замена била по одному модулю. Поведение строго неизменно.

Сделать:

1. **Вынести энкаунтеры** в `encounters.py` (`layers/entities/`): `_check_encounters`, `_roll_encounters`, `_is_daylight_at`, `_has_active_lair`, `_maybe_start_combat`. Как тонкий класс/функции над host'ом; `ActivationManager` делегирует.
2. **Вынести материализацию** в `materialization.py`: squad- и lair-материализация. Squad и lair — один алгоритм (роллы ростера, спавн temporary-существ, трекинг материализованных, дематериализация со сверкой). Свести к **общему трекеру материализации** (сейчас `_materialized_squads`/`_materialized_lairs` — параллельные позиционные структуры; один generic-трекер над обоими). Событийную запись смертей (`lair-death-event`) **не чинить** здесь — это будущая лестница детализации; сохранить текущее поведение как есть.
3. `ActivationManager` остаётся владельцем цикла активации (`update_activation`), зовёт encounters + materialization.

Вне скоупа: улучшение activation-логики, якорь-как-свойство (вместо isinstance-игрока), намерения, событийная запись лестницы детализации, `lair-death-event`-фикс. Всё это — будущая simulation-core модель; здесь только изоляция.

## Tests First

Поведение строго неизменно — пиновка (GREEN до рефактора, есть в `test_activation_manager`/`test_squads`/`test_lairs`/`test_materialization`):

- Вход игрока в локацию с активным сквадом материализует существ по member_templates/strength; выход дематериализует со сверкой (смерти учтены).
- Локация с ACTIVE-логовом: материализуется ростер + treasury-контейнер (treasure_items/gold); убийство core деплитит логово, treasury остаётся доступна.
- Энкаунтеры: вход в локацию с таблицей встреч роллит по таблице; `time_of_day`-тег фильтрует по дню/ночи (через IS_DAYLIGHT); регион-фолбэк работает.
- Активация: якорь-игрок активирует существ в своей локации, остальные dormant; combat-существа активны независимо; wake_at будит.

Новых поведенческих тестов не требуется (задача изоляционная) — но убедиться, что пиновка покрывает три вынесенных куска до дробления.

## Implementation

1. Убедиться, что пиновочная сетка покрывает activation + encounters + materialization; дописать недостающее (GREEN).
2. `encounters.py` — вынести 5 методов, `ActivationManager` делегирует.
3. `materialization.py` — вынести squad+lair материализацию под общий трекер. Свести `_materialized_squads`/`_materialized_lairs` к одному generic-трекеру (напр. `MaterializationTracker` с записями `{kind, source_id, spawned_ids, ...}`).
4. Прогнать всю пиновку + save-roundtrip (материализованное состояние переживает save/load неизменно).

Gotcha: `_materialized_squads`/`_materialized_lairs` могут сериализоваться в get_state/load_state слоя — если да, формат трекера в сейве не менять (пиновка round-trip из task 1). Squad и lair расходятся в деталях (lair: core/depletion/treasury) — общий трекер параметризовать, не насиловать в один тип. Изоляция ≠ рефактор алгоритма: копировать поведение 1:1.

## Acceptance Criteria

- [ ] Пиновка activation/encounters/materialization GREEN до дробления
- [ ] `encounters.py` и `materialization.py` созданы; `ActivationManager` — тонкий владелец цикла активации
- [ ] Общий трекер материализации для squad и lair (не два параллельных)
- [ ] Save/load материализованного состояния неизменён (round-trip зелёный)
- [ ] activation-логика по поведению не тронута (только перемещена/изолирована)
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- Split `activation_manager.py` (626 → 150). `ActivationManager` now owns only the activation passes (anchor players, activate/dormify creatures) + `update_activation`, which delegates to the two new sibling modules.
- **`encounters.py`** (191): `check_encounters`, `has_active_lair`, `roll_encounters`, `is_daylight_at`, `maybe_start_combat` — free functions taking the manager (`mgr`), same pattern as `combat_resolution`. `ENCOUNTER_COOLDOWN_SECONDS` moved here.
- **`materialization.py`** (344): squad + lair materialize/dematerialize (`update_squad_materialization`, `materialize_squad`, `dematerialize_squad`, `update_lair_materialization`, `materialize_lair`, `treasury_core_alive`, `sync_lair_treasury`, `dematerialize_lair`, `is_alive`) + shared `_any_in_combat` helper (dedups the "don't dematerialize mid-combat" guard the squad and lair paths both had).
- **Common materialization tracker — intentionally NOT unified.** The two trackers carry different roster metadata (squad: `(ids, strength, spawn_count)`; lair: `(ids, core_id, minion_templates)`) and are also read by `QueryHandler` (`_materialized_squads`) — forcing one union type would ripple there for a cosmetic gain. The shared *algorithm* is captured by the parallel function structure + `_any_in_combat`/`is_alive` helpers. Full unification is best done when the intents/triggers machine replaces this module (per [simulation-core](../../brainstorms/simulation-core.md)); the re-scope mandate is "isolate, don't polish."
- Activation logic itself untouched (behaviour-preserving move only).
- **Test contract change**: `test_spawn_engine` patched `activation_manager.random` → repointed to `encounters.random` (rolling moved there). `test_squad_events` called `_activation._materialize_squad(...)` → `materialization.materialize_squad(_activation, ...)`. All activation/materialization/encounter/lair pins green.
- `make check` green.
