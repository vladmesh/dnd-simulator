# Frontend Architecture: Brainstorm & Design

## Status: Draft (2026-03-22)

## Tech Stack

```
React 19 + TypeScript + Vite
TailwindCSS 4
shadcn/ui (Radix primitives + Tailwind styling — копируемые компоненты, не библиотека)
Zustand (стейт-менеджер — минимальный бойлерплейт, один файл на стор)
React Router (client-side routing, без SSR)
```

---

## Core Idea

Backend уже определяет чёткий state machine через WebSocket:

```
[connecting] → turn → [player_acting] → action_result → [player_acting]
                                       → round_result  → turn → ...
                                       → game_over     → [done]
```

Frontend — это **проекция этого state machine на экран**.
Вся архитектура строится от этого принципа.

---

## Three-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  UI Components (рендеринг, анимации, CSS)   │  ← Тупые. Получают данные, рисуют.
├─────────────────────────────────────────────┤
│  Game Store (единый стейт игры)             │  ← Умный. Знает всё о состоянии.
├─────────────────────────────────────────────┤
│  Transport (WS client, REST client)         │  ← Тупой. Отправляет/получает JSON.
└─────────────────────────────────────────────┘
```

### Layer 1: Transport

Тонкая обёртка. Две вещи:
- **WS client**: connect, reconnect, send, subscribe by message type
- **REST client**: typed wrappers над fetch (замена текущего `api.js`)

Этот слой **ничего не знает** об UI. Он просто доставляет сообщения.

### Layer 2: Game Store (Zustand)

Единый реактивный стор, который:
1. **Подписывается** на WS-сообщения и обновляет себя
2. **Экспортирует** derived state для UI
3. **Предоставляет** actions (методы для отправки команд)

```typescript
GameStore
├── connection: { status, sessionId, error }
├── phase: "setup" | "character_creation" | "playing" | "game_over"
├── mode: "peaceful" | "combat"
├── player: { name, hp, maxHp, ac, gold, location, abilities, ... }
├── turn: { budget, awareness, events[], isMyTurn }
├── location: { name, description, paths[], regionId }
├── combat: { enemies[], round, battleMap }
├── log: PerceivedEvent[]
│
├── // Derived state (computed in hooks)
├── canAct: boolean
├── availableActions: Action[]
├── nearbyInteractable: Entity[]
│
├── // Actions (send to server)
├── sendCommand(text)
├── sendAction(name, params)
├── endTurn()
```

Ключ: `availableActions` — это **derived state** из `mode + budget + nearby`.
UI показывает только релевантные кнопки:

```
peaceful + nearby has NPC       → [Talk] [Inspect] [Attack]
combat + budget.actions > 0     → [Attack] [Dodge] [Flee]
combat + budget.actions == 0    → [Move] [End Turn]
any mode                        → [End Turn]
```

### Layer 3: UI Components

Компоненты **не содержат логики игры**. Они:
- Читают из стора
- Вызывают store actions при кликах
- Управляют только своей визуальной логикой (анимации, модалки, скролл)

---

## Project Structure

```
frontend/                          # отдельно от Python, свой package.json
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── components.json                # shadcn config
├── src/
│   ├── main.tsx                   # entry point
│   ├── App.tsx                    # routing by phase
│   │
│   ├── types/                     # зеркало бэкенд-контрактов
│   │   ├── api.ts                 # REST response types
│   │   ├── ws.ts                  # WS message types
│   │   └── game.ts                # domain types (Player, Entity, etc.)
│   │
│   ├── transport/                 # layer 1
│   │   ├── wsClient.ts            # connect, reconnect, typed events
│   │   └── apiClient.ts           # typed fetch wrappers
│   │
│   ├── store/                     # layer 2
│   │   ├── gameStore.ts           # main store (phase, player, turn)
│   │   └── masterStore.ts         # master panel store
│   │
│   ├── hooks/                     # React bridge between store and components
│   │   ├── useAvailableActions.ts # derived: what can be done right now
│   │   └── useWebSocket.ts        # lifecycle: connect/disconnect
│   │
│   ├── components/                # layer 3
│   │   ├── ui/                    # shadcn primitives (Button, Card, Dialog...)
│   │   ├── setup/                 # session selection, character creation
│   │   ├── game/                  # player game screen
│   │   │   ├── GameScreen.tsx
│   │   │   ├── Header.tsx         # HP bar, location, time
│   │   │   ├── EventLog.tsx       # event feed (main content)
│   │   │   ├── ActionBar.tsx      # dynamic action buttons
│   │   │   ├── Perception.tsx     # who's nearby (clickable)
│   │   │   ├── LocationPanel.tsx  # paths, description
│   │   │   ├── BattleMap.tsx      # combat grid
│   │   │   └── PlayerStats.tsx    # ability scores, details
│   │   └── master/                # DM panel
│   │       ├── MasterScreen.tsx
│   │       ├── WorldOverview.tsx
│   │       └── CreatureList.tsx
│   │
│   └── lib/                       # utilities
│       ├── utils.ts               # shadcn cn() helper
│       └── constants.ts
```

---

## Routing

```
/            → SetupScreen (выбор мира, создание сессии)
/play/:id    → GameScreen (игрок, WebSocket)
/master      → MasterScreen (список сессий, REST)
/master/:id  → MasterScreen (конкретная сессия, REST polling)
```

React Router, client-side only. Vite dev-сервер проксирует `/api/*` на бэкенд `:8001`.

---

## Deployment

```
Dev:   vite dev :5173  →  proxy /api/* → uvicorn :8001
Prod:  vite build → dist/  →  FastAPI serves via StaticFiles
```

Один сервер, один порт в продакшене. Никакого nginx.

---

## Backend API Contract Summary

### WebSocket (`/api/ws/{session_id}`)

Server → Client:
- `turn` — начало хода (awareness, events, player, location, budget)
- `action_result` — результат действия игрока (events, player, budget)
- `round_result` — что сделали NPC (events, player)
- `error` — ошибка
- `game_over` — конец раунд-лупа

Client → Server:
- `{ type: "action", name: "attack", params: { target_id: "goblin_1" } }` — structured
- `{ type: "command", text: "attack goblin_1" }` — text command

### REST

Player:
- `POST /api/player/sessions/{id}/character` — создать персонажа
- `GET /api/player/sessions/{id}/status` — статус игрока

Master:
- `GET/POST /api/master/worlds` — CRUD шаблонов миров
- `GET/POST/DELETE /api/master/sessions` — управление сессиями
- `GET /api/master/sessions/{id}` — полный snapshot мира (god-mode)
- `POST/PATCH/DELETE /api/master/sessions/{id}/creatures` — управление существами
- `POST /api/master/sessions/{id}/time/advance` — промотка времени
- Saves: GET/POST/DELETE

### Key Data Structures

```typescript
// Awareness (server → client, part of turn message)
PeacefulAwareness {
  hour, day, month, year
  weather: { condition, temperature }
  location_name, region_name
  nearby: NearbyEntity[]      // { id, description, is_wounded }
  settlements, territory_owner, nation_info
}

CombatAwareness {
  self_hp, self_max_hp, self_ac, self_speed
  self_weapon, self_weapon_damage
  nearby: CombatEntity[]      // { id, description, is_wounded, distance_ft, direction }
  round_number, walls
}

TurnBudget { actions, bonus_actions, movement_remaining, reaction }

PerceivedEvent { description, event_type, actor_id, target_id, data }

PlayerStatus { name, race, char_class, level, alignment, hp, max_hp, ac, gold, location_id, appearance, ability_scores }
```

---

## Extensibility Pattern

Добавление новой фичи (инвентарь, способности, квесты) следует одному паттерну:

1. **Backend** добавляет данные в существующие WS/REST сообщения
2. **types/** — добавить/обновить TypeScript типы
3. **store/** — добавить поля в стор, обновить обработчик WS-сообщений
4. **hooks/** — добавить derived state если нужно (e.g. `useAvailableSpells`)
5. **components/** — добавить UI-компонент, подключить к стору

Архитектура не меняется. Каждая фича — это поле в сторе + компонент в UI.

---

## MVP Scope (First Iteration)

Минимум для замены debug UI:

### Must Have
- [ ] Setup: выбрать мир → создать сессию → создать персонажа (form)
- [ ] GameScreen layout: Header + EventLog + ActionBar + Perception
- [ ] Header: HP bar, имя, локация, игровое время
- [ ] EventLog: scrollable лента PerceivedEvent с автоскроллом
- [ ] ActionBar: динамические кнопки по availableActions
- [ ] Perception: список nearby entities, кликабельный (→ Talk/Attack/Inspect)
- [ ] Location: текущая локация + список путей (кнопки "go {location_id}")
- [ ] Combat mode: переключение layout при mode === "combat"
- [ ] BattleMap: ASCII `<pre>` (как сейчас, заменим позже)
- [ ] Budget display: оставшиеся actions/movement в бою

### Nice to Have (v1.1)
- [ ] Master panel: таблица сущностей + spawn/edit в shadcn
- [ ] Reconnect logic: auto-reconnect WebSocket с backoff
- [ ] Command input: текстовое поле как fallback (secondary)
- [ ] Dark/light theme toggle (shadcn поддерживает из коробки)

### Later
- [ ] BattleMap: кликабельная 2D сетка (Canvas или SVG)
- [ ] Inventory panel
- [ ] Spell book / ability bar
- [ ] Quest journal
- [ ] NPC interaction menu (context menu on click)
- [ ] Master: interactive world map
- [ ] i18n (react-intl или react-i18next)

---

## Design Notes

### Visual Direction
- Тёмная тема по умолчанию (shadcn "slate" или "zinc" palette)
- Чистый, минималистичный UI — НЕ пергамент и свитки, а modern dark RPG aesthetic
- Моноширинный шрифт для EventLog (ощущение терминала / текстовой RPG)
- Пропорциональный шрифт для UI-элементов (stats, buttons)
- Accent color: тёплый золотой или приглушённый красный (D&D palette)

### Component Design Principles
- Компоненты не знают про WebSocket
- Компоненты не парсят сырые сообщения — только типизированный стор
- Никаких `document.querySelector` — только React state/refs
- Каждый компонент — один файл, < 150 строк
- shadcn компоненты кастомизируются через Tailwind classes, не через CSS overrides

---

## Agent Antigravity Notes & Feedback

**1. Подтверждение стека:**
Стек (React + Zustand + Tailwind + shadcn/ui) выбран идеально. Радует, что Next.js не используется ради хайпа, а взят легкий Vite (SPA), так как SEO и SSR нам не нужны, а вот быстрый HMR для работы с WebSockets критичен. Комбинация Zustand для "тяжелого" единого стейта и тупых компонентов React — это золотой стандарт.

**2. Архитектурные нюансы (на что обратить внимание):**
- **Формы (DM Panel и Создание персонажа):** Для сложных модалок в админке Мастера настоятельно рекомендую связку `react-hook-form` + `zod`. Она идеально интегрируется с `shadcn/ui` (компонент `<Form>`) и избавит от ручной валидации состояний. Мы (AI) генерируем такие формы безошибочно.
- **Интернационализация (i18n):** В документе это отнесено в раздел "Later", но добавлять `i18n` (например `react-i18next`) *после* написания UI очень больно. Лучше настроить пустой плагин сразу и писать `t('button.attack')` с 1-го дня.
- **Оптимизация (Event Log):** Поскольку события приходят по WS, стейт логов будет разрастаться. Чтобы React не начал тормозить на 1000-м сообщении, нужно заложить политику ротации (например, хранить в Zustand только последние 200 событий).

**3. Радость для AI:**
Строгое разделение слоев (Transport -> Store -> UI) позволит нам с Клодом писать код с невероятной скоростью. Мы берем на себя верстку `<BattleMap />` изолированно, вынося всю логику расчета в хуки/стор. Архитектура одобрена.

---

## Agent Claude Notes & Feedback

**1. По замечаниям Antigravity:**

- **react-hook-form + zod** — согласен. Для Master panel это must-have: spawn creature form имеет ~15 полей с валидацией. shadcn/ui `<Form>` уже построен поверх react-hook-form, так что это не дополнительная зависимость, а использование того что уже есть. Добавляем в стек.

- **i18n с первого дня — не согласен.** Бэкенд уже отдаёт все user-visible строки (event descriptions, awareness texts) на нужном языке через `gettext`. Фронтенд почти не генерирует текст сам — только лейблы кнопок и заголовки панелей. Это ~50 строк которые легко вынести в один файл `constants.ts` с объектом `labels`, а потом заменить на `react-i18next` когда понадобится. Тащить i18n-фреймворк ради 50 строк в MVP — оверинжиниринг. Но: завести `labels.ts` с первого дня и никогда не хардкодить строки в JSX — это да.

- **Ротация Event Log** — согласен. 200 событий в сторе, при добавлении нового — `shift()` старого. Плюс: `EventLog` компонент должен использовать `virtualization` (например `@tanstack/react-virtual`) чтобы рендерить только видимые строки. Это бесплатно по сложности и снимает проблему раз и навсегда.

**2. Что пропущено в документе:**

- **Error boundary и состояния загрузки.** Каждый экран имеет минимум 3 состояния: loading, ready, error. В MVP достаточно одного глобального `<ErrorBoundary>` на уровне App + skeleton/spinner на уровне GameScreen. shadcn имеет `<Skeleton>` из коробки.

- **WS reconnect стратегия — это Must Have, не Nice to Have.** WebSocket оборвётся. Это не вопрос "если", а "когда". Без reconnect игрок теряет сессию. Минимум: exponential backoff (1s, 2s, 4s, 8s, max 30s) + toast "Reconnecting..." + при восстановлении запросить `GET /status` чтобы пересинхронизировать стейт. Перемещаю в Must Have.

- **Оптимистичный UI для действий.** Когда игрок нажимает [Attack], кнопка должна задизейблиться мгновенно (до ответа сервера). Это уже заложено в `canAct` derived state — при отправке действия ставим `isMyTurn: false`, сервер вернёт новый `turn` или `action_result`.

- **Responsive layout.** Не mobile-first, но GameScreen должен работать на планшете (D&D за столом). Предлагаю: desktop — sidebar справа (Perception + Location + Stats); планшет — collapsible drawer; мобайл — табы внизу. Tailwind breakpoints (`md:`, `lg:`) решают это без дополнительных библиотек.

**3. Уточнение по структуре стора:**

Zustand store не должен быть монолитным. Рекомендую slices pattern:

```typescript
// store/gameStore.ts — собирает слайсы
export const useGameStore = create<GameState>()((...a) => ({
  ...createConnectionSlice(...a),   // WS lifecycle
  ...createPlayerSlice(...a),       // player state + actions
  ...createTurnSlice(...a),         // turn, budget, awareness
  ...createLogSlice(...a),          // event log with rotation
}))
```

Каждый slice — отдельный файл, тестируется изолированно. Store растёт без превращения в god-object.

**4. Обновлённый стек (консенсус):**

```
React 19 + TypeScript + Vite
TailwindCSS 4
shadcn/ui (включая Form → react-hook-form + zod)
Zustand (slices pattern)
React Router
@tanstack/react-virtual (для EventLog)
```
