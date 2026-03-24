# Task: Deterministic Dice via DND_DICE_SEED

**Date:** 2026-03-24
**Sprint:** 002-meta-pipeline
**Phase:** 1 — Integration Tests

## Description

Добавить поддержку env var `DND_DICE_SEED` в `rules/dice.py`. Если переменная задана — module-level `_rng` инициализируется с этим seed. Все dice-функции (`roll_d20`, `roll`) уже используют `_rng` как fallback, поэтому достаточно изменить инициализацию.

Также нужно проверить `combat.py` (`roll_initiative`) и `action_handlers.py` (`roll`) — они вызывают dice-функции без передачи rng, значит подхватят seeded `_rng`.

**Файлы:** `src/dnd_simulator/rules/dice.py`

## Acceptance Criteria

- [ ] `DND_DICE_SEED=42` → все броски детерминированы при одинаковой последовательности вызовов
- [ ] Без env var — поведение не меняется (обычный random)
- [ ] Unit тест: два прогона с одним seed дают одинаковые результаты
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

Минимальное изменение: 2 строки в `dice.py` (import os + conditional seed). Все существующие dice-функции уже используют `_rng` как fallback — ничего протаскивать не пришлось. Pre-existing lint error в `core/__init__.py` (line too long) — не от наших изменений.
