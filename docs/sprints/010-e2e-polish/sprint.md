# Sprint 010 — E2E Polish + ActionBar Decomposition

**Goal:** Закрыть UX-баги из e2e-отчёта sprint 009 + разобрать ActionBar.tsx на субкомпоненты.

**Started:** 2026-03-28

## Context

Sprint 009 оставил 9 minor findings в e2e-отчёте — мелкие UX-баги, каждый изолирован. ActionBar.tsx (532 строк) — крупнейший frontend-компонент, будет расти с добавлением spell slots и новых drawers. Разбиваем до того, как станет неуправляемым.

**Ссылки:** [e2e-отчёт sprint 009](../../e2e-reports/2026-03-27-sprint009-post-audit.md), [audit](../../audit.md), [backlog](../../BACKLOG.md)

---

## Phase 1: E2E UX Fixes

7 фиксов из e2e-отчёта + расширение click-on-occupied-cell до inspect card на карте.

1. **Combat log i18n** — боевые строки (verbs, damage types, item names) через gettext. Все сообщения в логе на одном языке.
2. **NPC inspect faction display** — модалка показывает display name фракции вместо raw ID.
3. **Click occupied cell → creature inspect** — клик по занятой клетке на BattleMap открывает карточку существа (та же NPC inspect modal, адаптированная для боя). Список участников боя (combatants list) в CombatPanel убирается — ориентация чисто по карте.
4. **HP edit: current/max** — диалог редактирования HP в мастер-панели получает раздельные поля current и max.
5. **Brain toggle toast** — при отсутствии LLM ключа показывать warning toast вместо success.
6. **Consumable drawer label** — tooltip на кнопке drawer, label "🧪 N" вместо голой цифры.
7. **Log overlay backfill** — при открытии expand overlay подгружать уже полученные события, а не показывать "Ожидание событий...".

**Верифицируем:** Каждый пункт проверяется соответствующим сценарием из e2e-отчёта. Бой: карта — единственный источник информации об участниках, клик по фигурке → карточка.

**Tasks:**

1. [Combat log i18n](tasks/phase1-task1-combat-log-i18n.md)
2. [BattleMap click-to-inspect + faction display](tasks/phase1-task2-battlemap-inspect.md)
3. [Master panel + drawer UX polish](tasks/phase1-task3-master-panel-ux.md)

**Note:** Item 7 (log overlay backfill) fixed in commit 91d7200 before sprint started. Verified as part of task 3.

## Phase 2: ActionBar Decomposition

Разобрать ActionBar.tsx (532 строк) на субкомпоненты. Визуально идентичный результат.

- Выделить: CoreActions, DrawerButton + DrawerPopup, BudgetDisplay, CostBadge
- Убрать prop drilling — composition или context
- Каждый субкомпонент < 150 строк
- Существующие тесты ActionBar.test.tsx остаются зелёными

**Верифицируем:** Визуально идентичный action bar. Все существующие тесты зелёные. ActionBar.tsx < 150 строк (оркестрация). Субкомпоненты покрыты тестами.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **2026-03-28:** Click on occupied cell расширен до inspect card на карте. Combatants list убирается из CombatPanel — карта становится primary UI для боя.
- **2026-03-28:** Skip: "target too far" feedback (нужен дизайн), WS warning (косметика).

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
