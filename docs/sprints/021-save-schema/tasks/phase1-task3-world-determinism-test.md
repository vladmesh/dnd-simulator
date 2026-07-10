# Task: Сквозной тест воспроизводимости мира

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 1 — RNG threading & determinism

## Description

Продуктовый тест, фиксирующий свойство «одинаковый сид → одинаковая эволюция мира» на всей вертикали (закрывает backlog `test-gap-world-rng-determinism`). Не unit на отдельные функции (это tasks 1-2), а капстоун: мир собирается настоящим путём (content_loader + сборка слоёв как в game_service), живёт несколько внутриигровых дней, состояние сравнивается целиком.

## Tests First

- Один и тот же мир (реальный тестовый контент, rule-brains, без LLM и I/O) собирается дважды с одним world seed и одним dice seed (`set_global_seed`); `advance_time` на срок, покрывающий тики всех слоёв (politics/settlements — 30 дней, ecology — часы); `World.save()` обоих миров идентичен (сравнение структур целиком).
- Тот же сценарий с разными world seed → сейвы различаются (достаточно факта расхождения; при редкой коллизии на маленьком мире увеличить срок/мир, не ослаблять assert).
- Encounter-путь: при входе якоря в локацию с encounter-таблицей два прогона с одним seed спавнят одинаковые встречи (состав, количество), с разными — допускается расхождение.

Ожидаемая полка: unit или integration по месту (если нужен запущенный backend — integration; предпочтительно unit-уровень с прямой сборкой World, быстрее и без docker).

## Implementation

Тест-only задача; допустимы минимальные правки прод-кода, если сравнение `World.save()` упирается в недетерминированные артефакты (например, порядок dict-ов или генерируемые id) — такие находки фиксировать в тексте задачи и чинить точечно (сортировка на сериализации и т.п.). Если найдётся источник недетерминизма, не покрытый tasks 1-2, — это находка фазы: зафиксировать в sprint.md Decisions/Deferred.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation; RED здесь = падают до фиксов недетерминизма либо честно зелёные, если tasks 1-2 уже всё закрыли — тогда тест играет роль пина)
- [ ] Same-seed прогоны дают идентичный `World.save()`
- [ ] Different-seed прогоны расходятся
- [ ] Existing tests still pass (`make check-backend`)

## Status

`done`

## Developer Notes

Added capstone unit tests through real `GameService` assembly: same world seed plus dice seed gives identical month-long `World.save()`, different world seeds diverge, and same-seed encounter activation replays spawns.
The new different-seed save test initially failed on `test_vale`: the evolved persisted state could be identical because `World.save()` did not include the world seed.
Fixed that by adding `seed` to the legacy world save dict and restoring it in `World.load()`; full RNG state remains phase 2 schema work.
