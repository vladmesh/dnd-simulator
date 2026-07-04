# Task: TargetDropdown decomposition + shared smite/attack params

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

`TargetDropdown` (354) держит внутри три разных UI: target-picker, инлайн-копию smite-панели (дубль уже существующего `<SmiteChoice>`) и Lay-on-Hands amount-picker. Плюс параметры атаки со смайтом собираются вручную в трёх местах (`TargetDropdown`, `Perception`, `NpcInspectModal`).

Цель — убрать дубли, поведение неизменно:

- Инлайн smite-панель (`TargetDropdown.tsx:141-194`) заменить на существующий `<SmiteChoice>`. Один источник smite-UI.
- Ввести общий `buildAttackParams(targetId, slotLevel)` (новый `attackParams.ts` рядом с `attackCard.ts`), заменить три ручных сборки `{ target_id, smite_slot_level? }` (`TargetDropdown`, `Perception:101-105`, `NpcInspectModal:190-193`).
- Вынести `LayOnHandsAmountPicker` в отдельный файл (`action-bar/LayOnHandsAmountPicker.tsx`) — он уже автономный внутри `TargetDropdown`, просто отделить.
- `buildTargets` — оставить как есть (чистая функция), можно вынести в `action-bar/targets.ts`, если это упрощает тест.

Вне скоупа: изменение wire-параметров действий, изменение DOM-контрактов, за которые цепляются существующие тесты (`data-testid="smite-choice"`, `lay-on-hands-*`, `role="menu"`).

## Tests First

Рефактор с неизменным поведением — сначала пиновка, потом мелкие юнит-тесты на извлечённое:

- `buildAttackParams`: без слота → `{ target_id }`; со слотом → `{ target_id, smite_slot_level }`.
- Существующие `ActionButton.test.tsx` (smite panel, `smite_slot_level`, single-target auto-send, lay-on-hands slider/confirm) остаются зелёными без правок.
- `Perception.test.tsx` (smite через `SmiteChoice`) зелёный.

## Implementation

1. `attackParams.ts`: `export function buildAttackParams(targetId, slotLevel: number | null): Record<string, unknown>`.
2. В `TargetDropdown` заменить инлайн smite-`<div role="menu">` на `<SmiteChoice slots={slots} targetName={smiteTargetId} onChoice={handleSmiteChoice} onCancel={...}/>`, сохранив внешний anchor (relative + основная Button).
3. `handleSmiteChoice` → через `buildAttackParams`. `Perception`/`NpcInspectModal` — тоже.
4. Вынести `LayOnHandsAmountPicker` в свой файл, импортировать.

## Acceptance Criteria

- [ ] `buildAttackParams` покрыт юнит-тестом; smite-панель одна (`<SmiteChoice>`), инлайн-копии нет
- [ ] `TargetDropdown.tsx` заметно короче; амаунт-пикер и smite вынесены
- [ ] `npx vitest run` (затронутые файлы) зелёный, `tsc --noEmit` + `eslint src/` чисто
- [ ] DOM-контракты тестов не сломаны

## Status

`pending`
