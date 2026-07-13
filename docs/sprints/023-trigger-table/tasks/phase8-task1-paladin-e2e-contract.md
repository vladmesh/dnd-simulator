# Task: Контракт Paladin в E2E playbook

**Date:** 2026-07-14
**Sprint:** 023-trigger-table
**Phase:** 8 — Follow-up post-audit E2E Paladin

## Description

Исправить обязательный E2E playbook, который требует у Paladin L1 Fighting Style и spell slot.
Канонический продуктовый контракт проекта следует SRD/PHB 2014: Paladin L1 получает Lay on
Hands и стартовое снаряжение, а Fighting Style, Divine Smite и spell slots появляются при
подтверждённом повышении до L2. Этот контракт уже реализован в `PaladinFeatures`,
`perform_level_up`, API создания персонажа и LevelUpModal.

Граница задачи: поправить сценарии, а не добавлять selector в creation form и не менять backend
правила. Section 14.1 должен проверять L1 creation без Fighting Style и spell slots; сценарии
Lay on Hands, Fighting Style и Divine Smite должны явно использовать Paladin L2, созданного
через обязательный полный цикл §3.5.

## Tests First

- В playbook Paladin L1 creation проверяет d10 HP, Chain Mail, Shield, Longsword и пул Lay on
  Hands `5 × level`, но не требует selector Fighting Style или spell slot.
- Полный E2E путь создаёт Paladin L1, поднимает его до L2 через `level_up_test`, выбирает один
  из трёх Fighting Styles в LevelUpModal и видит первый spell slot только после подтверждения.
- Сценарий Lay on Hands проверяет ресурс L1 или L2 независимо от Fighting Style; сценарий Smite
  использует L2 Paladin с доступным spell slot и подтверждает расход слота и radiant damage.
- Никакой E2E expectation не утверждает, что Paladin L1 получает механику L2.

## Implementation

Обновить `docs/e2e-playbook.md`: разделить создание L1 от L2 feature path, сослаться из §14
на §3.5 и убрать устаревший L1 selector/slot expectation. Сохранить текущий набор Fighting
Styles (Defense, Dueling, Great Weapon Fighting) на границе LevelUpModal; не менять
`CharacterForm`, `CreatePlayerRequest`, `PaladinFeatures`, leveling или resource rules.

## Acceptance Criteria

- [ ] E2E expectations записаны и сначала сверены с существующими SRD/PHB 2014 backend tests
- [ ] §14.1 проверяет только Paladin L1 contract
- [ ] §3.5 остаётся единственным E2E выбором Paladin Fighting Style
- [ ] §§14.2–14.3 используют L2 prerequisite там, где требуется feature или spell slot
- [ ] Existing tests still pass (`make check`)
- [ ] Backend и frontend product code не менялись

## Status

`pending`
