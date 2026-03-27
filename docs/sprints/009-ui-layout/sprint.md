# Sprint 009 — Peaceful Dashboard Layout

**Goal:** Переработать игровой экран из «лог + sidebar» в dashboard: все панели видны одновременно, лог компактный, действия и зелья в action bar. Фокус на мирном режиме. Боевой layout — отдельный спринт после этого.

**Started:** 2026-03-27

## Context

Sprint 008 довёл DM-сторону до рабочего состояния. Игровой экран не менялся с момента создания и имеет проблемы:
- Лог занимает 60–80% экрана, хотя нужны только последние несколько строк
- Полезная информация (nearby, character, location) спрятана за скроллом или вкладками
- Action bar — плоский список кнопок без группировки
- Зелья доступны только через инвентарь (3 клика), хотя это боевое действие

**Принятый подход:** Dashboard — все панели на экране одновременно, каждая компактная. Лог уходит из центра в узкую горизонтальную полосу. Expand любой панели — overlay поверх dashboard.

**Ссылки:** [UI layout brainstorm](../../brainstorms/ui_layout.md), [sprint 008](../008-content-schema/sprint.md), [VISION.md](../../VISION.md)

---

## Target Layout (Peaceful Mode)

```
┌─────────────────────────────────────────────────────┐
│  Header (player name, time, location, HP bar)       │
├─────────────────────────────────────────────────────┤
│  Log: > Guard: "Welcome!"  > You look around.  [▼] │
├─────────────────┬──────────────┬────────────────────┤
│  Nearby         │  Character   │  Location          │
│  ├ Guard  [🔍]  │  HP: 20/20   │  📍 Town Square    │
│  ├ Merchant [🔍]│  AC: 15      │  → Forest (200m)   │
│  └ Traveler [🔍]│  STR 16 ...  │  → Bridge (150m)   │
│                 │              │                    │
│                 │  Equipment   │                    │
│                 │  ⚔ Longsword │                    │
│                 │  🛡 Chain     │                    │
│                 │  [inventory] │                    │
├─────────────────┴──────────────┴────────────────────┤
│  Action Bar: [Wait] [Look] [Say] · 🧪 Heal Potion  │
└─────────────────────────────────────────────────────┘
```

**Ключевые принципы:**
- **Всё видно сразу.** Ни одна панель не скрыта за табами или скроллом в default state.
- **Лог минимален.** Горизонтальная полоса на 1–2 строки. Последнее событие всегда видно. Expand → overlay с полным виртуализированным логом.
- **Три колонки панелей.** Nearby (левая), Character + Equipment (центр), Location (правая). Каждая занимает равную долю.
- **Trade через NPC.** TradePanel убирается с dashboard. Торговля — через inspect карточку мерчанта (sprint фаза 3 или следующий спринт). Пока оставляем кнопку trade в Nearby рядом с мерчантом.
- **Зелья в action bar.** Consumables (зелья) отображаются как кнопки рядом с основными действиями. Не нужно лезть в инвентарь чтобы выпить зелье.

---

## Phase 1: Dashboard Layout + Compact Log ✓

Переход от двухколоночного layout (log | sidebar) к dashboard. Лог — узкая полоса сверху. Три панели в ряд под ним. Табы из task 1 заменяются на dashboard grid.

**Что делаем:**
- Новый `GameScreen` layout: header → log strip → panel grid (3 col) → action bar
- `EventLog` получает два режима: compact (полоса, последние N событий, без виртуализации) и expanded (overlay, полный лог с виртуализацией)
- `SidebarTabs` удаляется — табы больше не нужны, все панели видны одновременно
- Панели (Nearby, Character+Equipment, Location) рендерятся в grid, каждая с ограниченной высотой и `overflow-y-auto`

**Верифицируем:** Все три панели видны одновременно. Лог занимает 1–2 строки. Expand лога показывает overlay с полной историей. Страница не скроллится. Работает на экранах ≥ 1024px.

**Tasks:**

1. [Dashboard Grid Layout](tasks/phase1-task1-dashboard-grid.md)
2. [Log Expand Overlay](tasks/phase1-task2-log-expand-overlay.md)

## Phase 2: Log Formatting ✓

Форматирование событий в логе: цветовое кодирование, иконки по типу события, заголовки ходов/раундов в бою, агрегация последовательных перемещений. Работает и в compact, и в expanded режиме лога.

**Что делаем:**
- `processLogEntries()` — transforms `LogEntry[]` → `DisplayEntry[]` (turn headers, aggregated moves, colored events with icons)
- Цвета и иконки для всех `EventType` (attack → red/sword, say → blue/message, move → muted/footsteps, death → bold red/skull, etc.)
- Агрегация: consecutive `entity_move` от одного actor → "Goblin moved (25 ft)" с `<details>` expander
- Turn headers в бою: визуальный разделитель между ходами разных существ

**Верифицируем:** В бою лог визуально разделён по ходам. Последовательные перемещения свёрнуты в одну строку. Все типы событий имеют иконки и цвета. Виртуализация не ломается при 200+ событиях.

**Tasks:**

1. [processLogEntries Transform](tasks/phase2-task1-process-log-entries.md)
2. [Render DisplayEntry in EventLog](tasks/phase2-task2-render-display-entries.md)

## Phase 3: Action Bar Redesign + Potions ✓

Action bar с core-кнопками, категориями, визуальным разделением по типу действия. Зелья и consumables вынесены прямо на панель.

**Что делаем:**
- Core-кнопки всегда видны: Attack, Dash, Disengage, Dodge, End Turn
- Категории (drawers): классовые умения (Second Wind, Cunning Action), инвентарь (equip/unequip) — popup над панелью
- Зелья и consumables: drawer-кнопка на action bar (`🧪 3`), popup со списком. Клик по предмету = use_item сразу. Не отдельные кнопки — не масштабируется при много предметах.
- Визуальное разделение: action (обычные), bonus action (другой стиль), потраченные — серые
- Budget display интегрирован

**Верифицируем:** Core-кнопки видны. Consumables/class features/inventory в drawer-popup (2 клика = использование). Потраченные типы действий серые. Работает для Fighter и Rogue.

**Tasks:**

1. [Action Bar Core Layout + Cost Styling](tasks/phase3-task1-action-bar-core-layout.md)
2. [Consumable, Class Feature, and Inventory Drawers](tasks/phase3-task2-action-drawers.md)

## Phase 4: NPC Inspect Card

Кнопка "осмотреть" на NPC открывает модальную карточку: имя, раса, описание, фракция, HP (если в бою), кнопки действий (торговать, атаковать). Backend отдаёт `description` через awareness.

**Что делаем:**
- Поле `description` на `Npc`/`MonsterTemplate` в content-моделях + YAML
- Модальная карточка NPC: имя, раса, описание, фракция, кнопки (Trade → TradePanel overlay, Attack → initiate combat)
- У мерчантов: кнопка Trade в карточке открывает TradePanel как modal/overlay
- Backend: описание через awareness или отдельный query

**Верифицируем:** Inspect → модалка с описанием и фракцией. Мерчант → кнопка Trade → TradePanel. Attack → бой. Description из YAML.

**Tasks:**

1. [NPC Description Field + Structured Inspect Data](tasks/phase4-task1-npc-inspect-backend.md)
2. [NPC Inspect Modal with Actions](tasks/phase4-task2-npc-inspect-modal.md)

---

## Status

**Current:** Replanned. Phase 1 task 1 (SidebarTabs) done but will be replaced by dashboard layout.

## Decisions

- **2026-03-27:** Отказ от табов в пользу dashboard layout. Все панели на экране одновременно. Лог — узкая полоса, не центральный элемент.
- **2026-03-27:** Trade panel уходит с dashboard. Торговля — через inspect карточку мерчанта (фаза 4).
- **2026-03-27:** Зелья выносятся на action bar как отдельные кнопки (фаза 3).
- **2026-03-27:** Боевой layout — отдельный спринт. Этот спринт фокусируется на мирном режиме. Action bar и inspect card переиспользуются.
- **2026-03-27:** Drag-and-drop панели — deferred. Фиксированный layout достаточен.

## Deferred

- Боевой layout (map + combat panel + enemies) — следующий спринт, переиспользует action bar и inspect card
- Drag-and-drop / resizable панели — не нужен на текущем этапе
- Фильтрация лога табами (Все/Бой/Диалоги) — когда будет больше типов событий
- Мобильная адаптация — отдельная история

## Results

_(заполняется в конце спринта)_
