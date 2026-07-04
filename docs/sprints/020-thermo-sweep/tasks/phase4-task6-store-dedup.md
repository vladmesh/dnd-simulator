# Task: Store/transport dedup — turnSlice, ApiError.detailMessage, connection reset

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

Три дубля в store/transport:

1. **turnSlice** — `onTurn`/`onActionResult`/`onRoundResult` повторяют один и тот же блок: `updatePlayer` + `appendEvents` + `clearDismissIfCombatEnded` + сборка `updates` (mode/awareness/location) + extract game-time из peaceful-awareness (`if ("hour" in a) updates.gameTime = {...}`). Вынести `applyCommon(msg)` и `extractGameTime(awareness)`.
2. **ApiError** (`transport/apiClient.ts`) — разбор `err.body.detail` дублируется в `CreatureForm` (массив-ветка pydantic-ошибок), `LayerEditor`, `GiveItemDialog`. Добавить метод `ApiError.detailMessage()` — единый разбор `detail` (строка / массив `{loc,msg}` / fallback на `message`).
3. **connectionSlice** — `connect()` вручную перечисляет reset всех turn-полей (`mode/awareness/location/budget/gameTime/isMyTurn/waitingForAction/gameOver/lastError/reactionPrompt`). Это дубль дефолтов `turnSlice`. Вынести `turnSliceResetState` (объект начальных значений) и использовать его в обоих местах.

Цель — один источник на каждый дубль, поведение неизменно.

Вне скоупа: изменение WS-протокола, поведения toast'ов, семантики reset.

## Tests First

- `extractGameTime`: peaceful-awareness с `hour` → `GameTime`; combat-awareness без `hour` → `null`/undefined (не трогает поле).
- `ApiError.detailMessage()`: строковый detail → строка; массив pydantic → `"field: msg; …"`; отсутствие body → `message`.
- turnSlice-пиновка: `onTurn`/`onActionResult`/`onRoundResult` дают те же поля (game-time из peaceful, budget-fallback). Использовать/расширить существующий store-тест.
- connectionSlice: после `connect()` turn-поля сброшены к дефолтам (пиновка reset).

## Implementation

1. `turnSlice`: `extractGameTime(awareness): GameTime | null`, `applyCommon(get, msg)` для повторяющегося блока; экспортировать `turnSliceResetState`.
2. `ApiError` → добавить `detailMessage(): string`; заменить три ad-hoc разбора. Внимание: `CreatureForm` показывает массив pydantic-ошибок — `detailMessage` должен покрыть этот формат.
3. `connectionSlice.connect()` использует `turnSliceResetState`.
4. Заодно чинится баг типов `turnSlice.ts:158` (`as ReactionMessage` cast) — собрать `ReactionMessage` типизированно.

## Acceptance Criteria

- [ ] `turnSlice` три хендлера через общий `applyCommon`/`extractGameTime`; reset-дефолты — один объект
- [ ] `ApiError.detailMessage()` покрывает строку/массив/fallback; три сайта используют его
- [ ] Новые юниты + существующие store-тесты зелёные
- [ ] `tsc --noEmit` + `eslint src/` чисто; поведение WS/toast неизменно

## Status

`done`

## Developer Notes

- `turnSlice`: `extractGameTime(awareness)` (экспортирован) + локальный `applyCommon(msg, events, extra)` — три хендлера свёрнуты к общему блоку (player/events/mode/awareness/location/gameTime). `turnSliceResetState` экспортирован; используется и в дефолтах слайса, и в `connectionSlice.connect()` (десять полей больше не перечисляются вручную).
- `ReactionMessage`-каст на строке 158 убран (типизированный литерал) — снял pre-existing `tsc -b` ошибку (28 → 27).
- `ApiError.detailMessage()` — строка / массив pydantic `{loc,msg}` / fallback на message; три сайта (`CreatureForm`, `LayerEditor`, `GiveItemDialog`) переведены на него.
- Тесты: `turnSlice.test.ts` (extractGameTime + onTurn budget-fallback + onRoundResult combat + connect-reset), `apiClient.test.ts` (detailMessage). `eslint` чисто.
