# Task: Ручка ГМ для активности и триггеров

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 4 — Ручка ГМ + failure containment

## Description

Добавить доменную и master API ручку для управления активностью существа и взведённостью его trigger table.
Обычный `Creature.active` не подходит как состояние команды ГМ: его пересчитывает каждый activation pass. Нужен
сохраняемый трёхпозиционный override (`active`, `dormant`, `automatic`), который немедленно влияет на удалённое
существо и переживает save/load. Принудительное гашение подавляет trigger-only активность, но не может погасить
мёртвое/боевое противоречие, awake anchor scene или контентный `always_active`.

Master API должен также взводить и снимать с взведения конкретную существующую пару по `trigger_id`, возвращать
текущий override и состояния пар в `CreatureResponse`. Все изменения живого мира выполняются под session
world-mutation gate, чтобы REST-команда не гонялась с round loop и autosave.

## Tests First

- Через реальный service/API перевести далёкого dormant NPC в ручной `active`, провести несколько activation pass
  и проверить, что он остаётся активным; затем поставить `dormant` и проверить гашение trigger-only NPC.
- Вернуть override в `automatic` и проверить, что итог снова определяется парой `{on, until}`. Отдельно закрепить,
  что ручной `dormant` не выключает живое существо в бою, awake anchor scene или с `always_active`.
- Сохранить и загрузить все три состояния override. После load ручная причина и автоматический режим должны
  продолжать давать тот же результат без зависимости от исходного YAML.
- Снять с взведения конкретную активную пару через master API: она перестаёт держать существо активным и не
  матчится на новые события. Повторное взведение возвращает ту же пару без потери её определения и runtime-state.
- Запрос неизвестного существа/trigger ID возвращает контролируемую 4xx-ошибку без частичной мутации. Ответ
  списка/детали существа содержит стабильные IDs, `armed`/`active` пар и текущий GM override.
- Заблокировать world gate в тесте, отправить команду управления из другого потока и убедиться, что мутация ждёт
  освобождения gate, а не меняет объект параллельно с round/save.

## Implementation

Добавить отдельное runtime/save-поле GM override на `Creature`, протянуть его через строгие entity save models и
`entity_serialization.py`. В `ActivationManager` учитывать его явно: `active` добавляет ручную причину,
`dormant` подавляет trigger-only причину, `automatic` не вмешивается; смерть, combat, anchor scene и
`always_active` сохраняют существующие инварианты.

В `CreatureCommands` оформить узкие операции управления override и `ActivationTrigger.armed`, оборачивая поиск и
мутацию в `session.mutate_world()`. Не менять определения `on`/`until` из live API и не перестраивать весь trigger
index при одном переключении `armed`: индекс уже проверяет runtime-флаг при матчинге. Добавить строгие request/
response схемы и master routes; расширить entity detail wire contract данными, нужными минимальной панели.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Ручной `active`/`dormant` немедленно влияет на trigger-only существо и не теряется на activation pass
- [x] `automatic` возвращает существу штатные причины активности
- [x] Combat, anchor scene и `always_active` нельзя случайно погасить ручкой ГМ
- [x] Override и trigger runtime-state проходят строгий save/load round-trip
- [x] Master API управляет существующим trigger ID и отдаёт состояния панели
- [x] Все live-world мутации этой ручки проходят под session world gate

## Status

`done`

## Developer Notes

Добавлен сохраняемый `GmActivationOverride` и две узкие master API команды под `session.mutate_world()`.
Переключение override или `armed` сразу запускает activation pass без materialization/event side effects; определение
пары и её `active` state при disarm сохраняются. Полный backend gate зелёный (2526 unit). Frontend suite не затронут:
на загруженной машине четыре старых теста упёрлись в штатный 5s timeout; повтор проблемных файлов подтвердил 26/26,
а `CreatureForm` отдельно прошёл 2/2 с timeout 15s.
