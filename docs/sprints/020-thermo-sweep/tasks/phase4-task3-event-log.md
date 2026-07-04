# Task: EventLog decomposition — sticky-scroll & interaction hooks

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

`EventLog` (324) держит два почти одинаковых контейнера — `CompactLog` и `FullLog`. Различаются они только виртуализацией (Full рендерит через `useVirtualizer`, Compact — плоским `map`), но каждый заново реализует: sticky-scroll (track «прижат ли к низу» + auto-scroll на новый entry), expand-state для aggregated-move, modal-state для attack-card, извлечение `cardData`.

Цель — вынести общее в хуки, поведение неизменно:

- `useStickyScroll(scrollRef, entryCount, threshold, onPin)` — хук, инкапсулирующий `stickyRef` + `handleScroll` + auto-scroll `useEffect`. Compact скроллит `el.scrollTop = el.scrollHeight`, Full — `virtualizer.scrollToIndex`; хук принимает колбэк «доскроллить до низа», чтобы обе реализации переиспользовали трекинг sticky/threshold.
- `useLogInteraction()` — `expandedEntries` (Set + toggle) + `modalEntry` (set/clear) + производный `cardData`. Общий для обоих режимов.
- `DisplayEntryRow` и `EventIcon` уже общие — оставить.

После этого Compact и Full различаются только контейнером/виртуализацией; дубли трекинга и interaction-стейта исчезают.

Вне скоупа: изменение виртуализации, оценок размеров строк, DOM-testid (`compact-log`, `round-header`, `turn-header`, `aggregated-move-expand`, `attack-row`, `log-expand-btn`).

## Tests First

- Существующий `EventLog.test.tsx` — зелёный без правок (иконки, turn-headers, aggregated-move collapse/expand, full-mode 200 entries).
- Опционально: юнит на `useLogInteraction` (toggle expand, set/clear modal) через `renderHook`, если это дёшево.

## Implementation

1. `useStickyScroll.ts` — вынести sticky-трекинг; параметризовать threshold (Compact 8, Full 16) и «scroll-to-bottom» колбэком.
2. `useLogInteraction.ts` — expand-set + modal-entry + `cardData` (через `extractAttackCardData`).
3. Переписать `CompactLog`/`FullLog` на хуки; общую разметку строки не трогать.

## Acceptance Criteria

- [ ] sticky-scroll и interaction-стейт — в хуках, не продублированы в двух компонентах
- [ ] `EventLog.tsx` короче; Compact/Full различаются только виртуализацией
- [ ] `EventLog.test.tsx` зелёный без правок
- [ ] `tsc --noEmit` + `eslint src/` чисто (hook-deps без новых disable, где можно)

## Status

`pending`
