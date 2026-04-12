# Task: Pure leveling rules — XP-by-CR and level thresholds

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 1 — XP & Leveling Core

## Description

Создать `src/dnd_simulator/rules/leveling.py` с чистыми функциями для XP: таблица XP-by-CR (стандарт DMG), таблица XP-thresholds по уровню (PHB p.15), и производные функции.

Никаких обращений к Creature/world — только функции над числами. Это фундамент для задач 2-3.

**Таблицы (жёстко — как в книге):**

XP-by-CR (DMG p.275):
```
0    → 10    1/8 → 25   1/4 → 50    1/2 → 100
1    → 200   2   → 450  3   → 700   4   → 1100
5    → 1800  6   → 2300 7   → 2900  8   → 3900
9    → 5000  10  → 5900 ...
```

На sprint 017 нам нужен диапазон до level 2 → threshold 300 XP. Монстры CR 0–5 покрывают все кейсы. Хранить полную таблицу DMG до CR 10 (дальше — out of scope).

Level thresholds (PHB p.15, total XP для уровня):
```
1 → 0      2 → 300    3 → 900    4 → 2700   5 → 6500
6 → 14000  7 → 23000  8 → 34000  ... 20 → 355000
```

## Tests First

`tests/unit/test_leveling_rules.py`:

1. **XP-by-CR базовая корректность**
   - CR 0 → 10 XP; CR 1/8 → 25; CR 1/4 → 50; CR 1/2 → 100; CR 1 → 200; CR 5 → 1800.
2. **CR вне таблицы — fail-fast**
   - `xp_for_cr(-1)` → `ValueError`; `xp_for_cr(50)` → `ValueError`. Нет тихого дефолта.
3. **Level thresholds**
   - `level_for_xp(0)` = 1; `level_for_xp(299)` = 1; `level_for_xp(300)` = 2; `level_for_xp(899)` = 2; `level_for_xp(900)` = 3.
4. **XP past max level**
   - `level_for_xp(10_000_000)` = 20 (cap, не исключение — большие значения ок).
5. **`xp_to_next_level`**
   - Игрок с 0 XP → 300 до L2; с 250 XP → 50 до L2; с 300 XP (ровно L2) → 600 до L3; на L20 → 0 (нет следующего).
6. **`can_level_up(xp, current_level)`**
   - Игрок L1 с 250 XP → False; L1 с 300 XP → True; L1 с 1000 XP → True (доступен L2 — повышение по одному за раз, как в PHB).
   - L20 с любым XP → False.

## Implementation

Новый файл `src/dnd_simulator/rules/leveling.py`:

```python
from typing import Final

# Fractional CRs — используем float keys (0.125, 0.25, 0.5)
_XP_BY_CR: Final[dict[float, int]] = {
    0.0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
    1.0: 200, 2.0: 450, 3.0: 700, 4.0: 1100, 5.0: 1800,
    6.0: 2300, 7.0: 2900, 8.0: 3900, 9.0: 5000, 10.0: 5900,
}

_XP_THRESHOLDS: Final[tuple[int, ...]] = (
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
)  # index i → XP needed to BE level (i+1)

MAX_LEVEL: Final[int] = 20


def xp_for_cr(cr: float) -> int:
    if cr not in _XP_BY_CR:
        raise ValueError(f"CR {cr} not in XP table")
    return _XP_BY_CR[cr]


def level_for_xp(xp: int) -> int:
    for level in range(MAX_LEVEL, 0, -1):
        if xp >= _XP_THRESHOLDS[level - 1]:
            return level
    return 1


def xp_to_next_level(xp: int) -> int:
    current = level_for_xp(xp)
    if current >= MAX_LEVEL:
        return 0
    return _XP_THRESHOLDS[current] - xp


def can_level_up(xp: int, current_level: int) -> bool:
    return current_level < MAX_LEVEL and level_for_xp(xp) > current_level
```

## Acceptance Criteria

- [ ] `tests/unit/test_leveling_rules.py` написан и RED
- [ ] `src/dnd_simulator/rules/leveling.py` реализован, тесты GREEN
- [ ] `make check` проходит (ruff, mypy, все тесты)
- [ ] Модуль не импортирует ничего из `core/`, `layers/`, `service/` — только stdlib
- [ ] Fractional CR (0.125, 0.25, 0.5) корректно обрабатываются как float keys

## Status

`pending`
