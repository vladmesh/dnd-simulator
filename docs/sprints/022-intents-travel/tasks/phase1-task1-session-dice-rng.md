# Task: Session-owned dice RNG

**Date:** 2026-07-10
**Sprint:** 022-intents-travel
**Phase:** 1 — Safe session lifecycle

## Description

Убрать process-global dice RNG из runtime игрового процесса. Каждая `GameSession` владеет своим генератором костей; `Round` и `ActionContext` используют его для инициативы, атак, реакций, лечения и остальных правиловых бросков. `DND_DICE_SEED` сохраняет назначение детерминированного стартового сида, но одна сессия больше не сдвигает последовательность другой. Сейв и восстановление autosave работают с RNG конкретной сессии.

Модульный fallback в `rules/dice.py` можно оставить для изолированных правиловых unit-тестов, но session runtime не должен обращаться к `get_global_rng()`.

## Tests First

- Две сессии с одинаковым seed получают одинаковую начальную последовательность, даже если между их бросками другая сессия выполняет дополнительные действия.
- После save/load следующая кость в конкретной сессии совпадает с продолжением её сохранённой последовательности и не зависит от бросков соседней сессии.
- Реальный round/action path использует session RNG, а не модульный fallback.

## Implementation

Добавить RNG во владение `GameSession` и передать его в `Round`, затем использовать при построении всех `ActionContext` и при инициативе. Перенести чтение/инициализацию `DND_DICE_SEED` к созданию сессии вместо мутации module-global состояния в API lifespan. В `commands_save.py` и autosave restore сериализовать и восстанавливать состояние `session.dice_rng`. Не менять чистые правила: их существующий явный параметр `rng` остаётся точкой инъекции.

Ключевые файлы: `service/session.py`, `service/game_service.py`, `round.py`, `service/commands_save.py`, `adapters/api/app.py`, тесты dice/save/session lifecycle.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Runtime `Round` не вызывает `get_global_rng()`
- [ ] Броски одной сессии не меняют dice-последовательность другой
- [ ] Save/load продолжает dice-последовательность своей сессии

## Status

`pending`
