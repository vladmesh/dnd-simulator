# Task 2.5: Разделить запрос и результат атаки

**Date:** 2026-07-12
**Sprint:** 023-trigger-table
**Phase:** 1 — Типизированная таксономия событий

## Description

Разделить перегруженный `ENTITY_ATTACK`: команда на resolution получает отдельный
`ENTITY_ATTACK_REQUESTED`, а `ENTITY_ATTACK` остаётся фактом завершённой атаки для лога,
perception и будущего trigger matching.

## Tests First

- Боевой handler и opportunity attack эмитят `ENTITY_ATTACK_REQUESTED`.
- EntitiesLayer разрешает только запрос и пишет отдельный `ENTITY_ATTACK` с результатом.
- Запрос и результат отклоняют payload друг друга.

## Architecture Decision

События различаются по смыслу, а не по стадии заполнения одного payload. Requested-событие
содержит только actor/target и опциональный smite slot. Итоговое событие содержит бросок,
AC, оружие, critical и компоненты урона. Это сохраняет один fail-fast контракт на EventType
и не заставляет trigger table матчить внутреннюю команду как свершившийся мировой факт.

## Status

`done`

## Developer Notes

Добавлены `AttackRequestedPayload` и `AttackResolvedPayload`. Боевые handlers эмитят
`ENTITY_ATTACK_REQUESTED`, EntitiesLayer разрешает его и пишет `ENTITY_ATTACK` в лог.
Флаг opportunity attack переносится в итоговый payload. Старые dict-конструкторы запросов
временно нормализуются в requested-тип на границе `Event`; production producers используют
явный payload. Полный `make check`: backend 2484, frontend 283 теста.
