# Task: SchemaForm decomposition — FieldShell + localizedCodec

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

`SchemaForm` (488) повторяет `<Label>{title}{required*}</Label>`-обёртку в ~7 ветках `SchemaField` и держит логику localized-text (unwrap `{lang: value}` → строку на входе, wrap обратно на сабмите) размазанной по `SchemaForm` и `onFormSubmit`. Схемо-резолв (`resolveRef`/`resolveProperty`/`isLocalizedText`/`buildDefaults`) стоит вынести в отдельный модуль, чтобы файл был про рендер.

Цель — убрать дубли, поведение неизменно:

- `<FieldShell label required>{children}</FieldShell>` — единый label-wrapper, заменяет повторяющийся `<div className="space-y-1"><Label>…</Label>…</div>`.
- `localizedCodec`: `decodeLocalized(value, lang)` (unwrap для формы) + `encodeLocalized(value, lang)` (wrap на сабмите) — один источник, заменяет инлайн-логику в `SchemaForm` (строки 118-129) и `onFormSubmit` (148-149).
- Вынести схемо-хелперы (`resolveRef`, `resolveProperty`, `isLocalizedText`, `buildDefaults`) в `schemaResolve.ts`; `buildDefaults` при этом становится единственным (сейчас есть второй ad-hoc «rowDefaults» в `ArrayOfObjectsField:434-442` — переиспользовать `buildDefaults(itemSchema, rootDefs)`).

Вне скоупа: изменение формата данных формы, изменение set полей/типов ввода, RefSelect/enum-ветки по существу.

## Tests First

- Существующий `SchemaForm.test.tsx` — зелёный без правок (пиновка формата ввода/вывода, localized-обёртки).
- `schemaResolve` юнит: `buildDefaults` на схеме с default/boolean/array; `resolveProperty` unwrap anyOf-null и $ref-merge.
- `localizedCodec` юнит: `decodeLocalized({en:"hi"}, "en") === "hi"`; `encodeLocalized("hi","en")` deep-equals `{en:"hi"}`.

## Implementation

1. `schemaResolve.ts` — перенести 4 хелпера, экспортировать; `SchemaForm` импортирует.
2. `localizedCodec.ts` — `decodeLocalized`/`encodeLocalized`; заменить инлайн.
3. `FieldShell.tsx` (или локальный компонент в `SchemaForm`) — заменить дубли label-обёртки в `SchemaField`.
4. `ArrayOfObjectsField` использует общий `buildDefaults(itemSchema, rootDefs)` для новой строки.

## Acceptance Criteria

- [ ] label-обёртка одна (`FieldShell`), localized-логика одна (`localizedCodec`), `buildDefaults` один
- [ ] `SchemaForm.tsx` заметно короче, схемо-резолв в своём модуле
- [ ] `SchemaForm.test.tsx` зелёный без правок; новые юниты зелёные
- [ ] `tsc --noEmit` + `eslint src/` чисто

## Status

`done`

## Developer Notes

- Схемо-резолв (`resolveRef`/`resolveProperty`/`isLocalizedText`/`buildDefaults`) вынесен в `schemaResolve.ts`; localized-логика — в `localizedCodec.ts` (`decodeLocalized`/`encodeLocalized`); label-обёртка — `FieldShell.tsx`. `SchemaForm.tsx`: 488 → 388 строк.
- `ArrayOfObjectsField` теперь строит новую строку через общий `buildDefaults(itemSchema, rootDefs)` — поведение эквивалентно (array-поля инициализируются `[]`, что совпадает с `val ?? []` на сабмите).
- `SchemaForm.test.tsx` зелёный без правок (22); новые `schemaResolve.test.ts` + `localizedCodec.test.ts`. `tsc -b` без новых ошибок, `eslint` чисто.
