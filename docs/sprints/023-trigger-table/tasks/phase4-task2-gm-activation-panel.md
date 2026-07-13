# Task: Минимальная панель активности ГМ

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 4 — Ручка ГМ + failure containment

## Description

Добавить в существующую master-панель существ минимальные live controls поверх API из задачи 1: перевести
существо в ручной active/dormant или вернуть в automatic, а также взвести/снять каждую его trigger-пару. Панель
остаётся локальной частью `CreatureList`, без отдельного списка всех активных, истории причин и аналитики из
отложенного `gm-actives-panel`.

## Tests First

- Открыть список с dormant NPC в automatic, нажать «Активировать» и проверить API-команду, обновлённый badge и
  доступность обратных команд после refresh.
- Погасить trigger-only NPC, затем вернуть его в automatic; интерфейс должен отличать фактический `active` от
  выбранного GM override и не обещать, что `always_active`/combat существо стало dormant.
- Для существа с двумя парами снять с взведения одну по её ID: только её badge и кнопка меняются, вторая остаётся
  нетронутой. Ошибка API показывает toast и не оставляет оптимистическое ложное состояние.
- Проверить RU и EN labels для режимов активности, взведения и ошибок; все новые пользовательские строки идут
  через i18next/gettext-контракт проекта.

## Implementation

Расширить frontend API types/client контрактами задачи 1. В `CreatureList` вынести компактные controls так, чтобы
таблица не получила ещё одну крупную встроенную ветку JSX; после успешной команды перечитывать серверное
состояние. Показывать отдельно фактическую активность и ручной режим, а trigger IDs и их `armed`/`active` состояния
раскрывать только у существ, у которых есть пары.

Добавить component-level product flow tests с реальным пользовательским кликом и mock transport boundary. При
закрытии фазы проверить тот же путь в браузере через master session view; полноценную `gm-actives-panel` не
строить.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] ГМ может выбрать active, dormant и automatic для существа из master session view
- [x] Фактическая активность и GM override показаны как разные состояния
- [x] Каждая trigger-пара взводится/снимается независимо по стабильному ID
- [x] Ошибки API видимы и не оставляют ложное состояние UI
- [x] Новые RU/EN строки проходят штатную локализацию
- [x] Полная панель активных и история причин не попали в scope

## Status

`done`

## Developer Notes

Frontend-контракт расширен типами и двумя API-командами задачи 1. Компактный `ActivationControls` вынесен из
таблицы: фактическая активность, GM override и runtime-state каждой trigger-пары показаны раздельно. После
успешной команды список перечитывается с сервера; при ошибке показывается локализованный toast без оптимистической
мутации. Добавлены три component-flow теста, включая независимое переключение двух trigger ID, rollback-free error
path и RU/EN labels. `make check`: backend 2526 passed, frontend 286 passed.
