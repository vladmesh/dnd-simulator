# Task: WorldOverview — generic EditableStatsTable + typed rows

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

`WorldOverview` (331) — три почти идентичные таблицы (`RegionsTable` read-only, `NationsTable`/`SettlementsTable` editable). Editable-пара дублирует один и тот же паттерн: `editing`/`values`/`saving`-стейт, `startEdit`/`saveEdit` с optimistic-revert через `.catch(→ startEdit(orig))`, рендер ячеек «Input в edit-режиме, иначе текст», actions-колонка (Check/✕ или Edit-кнопка). Строки типизированы как `Record<string, unknown>` со `String(...)`-кастами повсюду.

Цель — один generic + типы, поведение неизменно:

- `EditableStatsTable<T>` — generic-компонент: колонки-дескрипторы (`{ key, label, editable?, parse?, step?/min?/max? }`), `patch(id, values)`-колбэк, optimistic-revert. Заменяет `NationsTable` и `SettlementsTable`.
- `RegionsTable` остаётся отдельным (read-only, кастомный weather-рендер) либо использует read-only-режим той же таблицы — что проще.
- Типизировать строки: `Region`/`Nation`/`Settlement` (из task 5, общие типы). Убрать `String(...)`-касты там, где тип уже известен.

Вне скоупа: изменение колонок/patch-эндпоинтов, изменение i18n-ключей.

## Tests First

Тестов у `WorldOverview` сейчас нет — добавить пиновку до рефактора (это и есть страховка неизменности):

- Рендер таблицы наций → строки с id/name/wealth/military/stability, кнопка Edit.
- Клик Edit → появляются `<input>`; правка + Save → `api.master.patchNation` вызван с распарсенными числами.
- Save отклонён (reject) → строка возвращается в режим правки (optimistic-revert).
- То же для поселений (`patchSettlement`, `population` через `parseInt`).

## Implementation

1. `EditableStatsTable.tsx` — generic с колонками и optimistic-save.
2. `WorldOverview` собирает три таблицы через дескрипторы колонок; `patch`-колбэки оборачивают `api.master.patchNation/patchSettlement`.
3. Строки типизированы `Region`/`Nation`/`Settlement`.

## Acceptance Criteria

- [ ] Пиновочные тесты `WorldOverview` написаны до рефактора, зелёные после
- [ ] Editable-логика одна (`EditableStatsTable<T>`), не продублирована
- [ ] Строки типизированы, `String(...)`-касты убраны где тип известен
- [ ] `tsc --noEmit` + `eslint src/` чисто, `patchNation`/`patchSettlement` payload неизменны

## Status

`pending`
