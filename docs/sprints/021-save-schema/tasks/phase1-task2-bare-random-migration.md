# Task: Миграция bare-random сайтов на слоевой RNG

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 1 — RNG threading & determinism

## Description

Убрать процесс-глобальный `random` из симуляции мира (backlog `layer-rng-threading`). Сайты:

- `layers/entities/encounters.py:112,123` — `random.random()` (шанс встречи), `random.randint()` (количество монстров) → RNG `EntitiesLayer` (появился в task 1), прокинуть в encounter-roller явно.
- `layers/ecology/movement.py:83` — `random.choice(candidates)` (roam) → RNG `EcologyLayer`, параметром функции (обязательным, без дефолта на глобальный).
- `layers/ecology/squad_combat.py:106` — `random.choice(edges)` (отступление проигравшего) → так же.
- `layers/ecology/lairs.py:33` — `get_global_rng().random()` (depletion chance) использует dice-RNG для мировой симуляции; перевести на RNG `EcologyLayer` для консистентности (dice-RNG — только броски костей правил).

После миграции `grep -rn "random\." src/dnd_simulator/layers/` не должен находить обращений к модульному глобальному `random` (только `random.Random` в конструкторах). Функции в `movement.py`/`squad_combat.py` остаются чистыми: RNG приходит параметром, состояние владеет слой.

## Tests First

- Encounter rolls детерминированы: `EntitiesLayer`/roller с фиксированным seed на одной encounter-таблице выдаёт одну и ту же последовательность (встреча/нет, число монстров) за K заходов; другой seed — другую.
- Roam movement детерминирован: squad на графе локаций с seeded RNG проходит один и тот же маршрут за N тиков ecology.
- Retreat детерминирован: тот же проигравший на тех же рёбрах с тем же seed отступает в одну и ту же локацию.
- Изоляция от глобального RNG (урок флака PR #31): вызов `random.seed(...)` / потребление глобального `random` между тиками НЕ меняет исходы seeded-слоя — последовательности совпадают с прогоном без вмешательства.

## Implementation

После красных тестов: сигнатуры функций encounters/movement/squad_combat/lairs получают `rng: random.Random`, слои передают свой `self._rng`. Проверить вызывающие сайты (ActivationManager для encounters — см. `layers/entities/` после декомпозиции sprint 020 phase 3).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] В `src/dnd_simulator/layers/` нет обращений к глобальному `random` и к `get_global_rng()` вне бросков костей правил
- [ ] Тест изоляции от глобального RNG зелёный

## Status

`pending`
