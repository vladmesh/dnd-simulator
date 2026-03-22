# Frontend: React SPA

Замена debug UI на полноценный React-фронтенд.
Браinstorm: `docs/brainstorms/frontend-architecture.md`

## Stack

```
React 19 + TypeScript + Vite
TailwindCSS 4 + shadcn/ui
Zustand (slices pattern)
React Router
react-hook-form + zod (формы)
@tanstack/react-virtual (EventLog)
```

## Architecture

```
Transport (wsClient, apiClient)  — тупая доставка JSON
    ↓
Game Store (Zustand slices)      — единый стейт, derived state, actions
    ↓
UI Components                    — тупые, читают стор, вызывают actions
```

## Phases

### Phase 0: Scaffold

Цель: пустой React-проект собирается, проксирует API, рендерит "Hello".

```
frontend/
├── package.json
├── vite.config.ts          # proxy /api/* → localhost:8001
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   └── lib/utils.ts        # shadcn cn() helper
```

Шаги:
- [x] `npm create vite@latest frontend -- --template react-ts`
- [x] Установить tailwind 4, shadcn/ui, zustand, react-router, zod
- [x] Настроить vite proxy на :8001
- [x] Настроить shadcn (dark theme, zinc palette)
- [x] Добавить `make frontend-dev` и `make frontend-build` в Makefile
- [x] FastAPI: отдавать `frontend/dist/` через StaticFiles в проде
- [x] Проверить: `make frontend-dev` → открывается пустая страница, `/api/master/worlds` проксируется

Результат: фронтенд собирается и проксирует бэкенд.

---

### Phase 1: Transport + Types

Цель: типизированные клиенты для REST и WebSocket, зеркалящие бэкенд-контракт.

```
src/
├── types/
│   ├── api.ts              # PlayerStatusResponse, CreatureResponse, WorldStateResponse...
│   ├── ws.ts               # TurnMessage, ActionResultMessage, RoundResultMessage...
│   └── game.ts             # TurnBudget, PeacefulAwareness, CombatAwareness, PerceivedEvent
├── transport/
│   ├── apiClient.ts        # typed fetch: api.master.getSessions(), api.player.createCharacter()
│   └── wsClient.ts         # connect(sessionId), send(msg), on('turn', cb), reconnect with backoff
```

Шаги:
- [x] Описать все TypeScript-типы по бэкенд-контракту (schemas.py + awareness.py)
- [x] apiClient: обёртки над fetch для всех REST-эндпоинтов
- [x] wsClient: класс с connect/disconnect/send/on, exponential backoff reconnect
- [x] Проверить: вручную вызвать `apiClient.master.getWorlds()` из консоли браузера

Результат: фронтенд может общаться с бэкендом через типизированные функции.

---

### Phase 2: Game Store

Цель: Zustand стор, который управляет всем состоянием игры.

```
src/store/
├── gameStore.ts            # create() с slices, экспорт useGameStore
├── slices/
│   ├── connectionSlice.ts  # status, sessionId, connect(), disconnect()
│   ├── playerSlice.ts      # player data, updateFromStatus()
│   ├── turnSlice.ts        # mode, budget, awareness, isMyTurn, events
│   └── logSlice.ts         # event log, append with 200-event cap
```

Шаги:
- [x] connectionSlice: статусы connecting/connected/disconnected/error, привязка к wsClient
- [x] playerSlice: обновляется из каждого WS-сообщения (turn, action_result, round_result)
- [x] turnSlice: парсит awareness (peaceful/combat), обновляет mode, budget, nearby
- [x] logSlice: append events, cap 200, каждый event получает unique id для React keys
- [x] Подписка на WS-сообщения: wsClient.on('turn') → store.onTurn(), и т.д.
- [x] Derived state: `useAvailableActions()` hook — вычисляет кнопки из mode + budget + nearby
- [x] Проверить: подключиться к существующей сессии, убедиться что стор обновляется в React DevTools

Результат: всё состояние игры живёт в сторе и реактивно обновляется от WS.

---

### Phase 3: Setup Flow

Цель: игрок может выбрать мир, создать сессию и персонажа через UI.

```
src/components/
├── setup/
│   ├── SetupScreen.tsx     # точка входа: список миров → создать сессию → создать персонажа
│   ├── WorldPicker.tsx     # GET /worlds → список карточек
│   ├── CharacterForm.tsx   # react-hook-form + zod, все поля CreatePlayerRequest
│   └── SessionConnect.tsx  # ввести session_id для подключения к существующей
```

Шаги:
- [ ] Роутинг: `/` → SetupScreen, `/play/:id` → GameScreen (пока заглушка)
- [ ] WorldPicker: загрузить миры, показать карточки с именем и описанием
- [ ] Кнопка "New Session" → POST /sessions → получить session_id
- [ ] CharacterForm: имя, раса, класс, уровень, alignment, ability scores, HP, AC
- [ ] Валидация через zod-схему (например: HP > 0, ability scores 1-30)
- [ ] После создания персонажа → navigate(`/play/${sessionId}`)
- [ ] SessionConnect: альтернативный путь — ввести ID существующей сессии
- [ ] Проверить: от открытия страницы до попадания на /play/:id без ошибок

Результат: полный onboarding flow работает.

---

### Phase 4: Game Screen — Peaceful Mode

Цель: рабочий игровой экран для мирного режима.

```
src/components/game/
├── GameScreen.tsx           # layout: Header + MainPanel + SidePanel + ActionBar
├── Header.tsx               # HP bar (shadcn Progress), имя, локация, время, погода
├── EventLog.tsx             # virtualized список PerceivedEvent, автоскролл вниз
├── ActionBar.tsx            # кнопки из useAvailableActions(), disable при !canAct
├── Perception.tsx           # nearby entities, клик → контекстное меню (Talk/Attack/Inspect)
├── LocationPanel.tsx        # текущая локация, описание, кнопки путей ("go {id}")
└── PlayerStats.tsx          # ability scores, AC, gold, level — collapsible panel
```

Layout (desktop):
```
┌──────────────────────────────────────────────┐
│  Header: [HP ████░░] Aldric | Crossroads | Y1 M3 D15 14:00  │
├────────────────────────────┬─────────────────┤
│                            │  Perception     │
│  EventLog                  │  LocationPanel  │
│  (scrollable)              │  PlayerStats    │
│                            │                 │
├────────────────────────────┴─────────────────┤
│  ActionBar: [Look] [Wait 1h] [End Turn]  [Talk ▾] [Go ▾]   │
└──────────────────────────────────────────────┘
```

Шаги:
- [ ] GameScreen: useWebSocket hook — connect при mount, disconnect при unmount
- [ ] Header: HP bar с цветом (green > 50%, yellow > 25%, red), данные из player slice
- [ ] EventLog: @tanstack/react-virtual, автоскролл, моноширинный шрифт
- [ ] Perception: список nearby из awareness, при клике — popover с действиями
- [ ] LocationPanel: имя + описание + список путей как кнопки
- [ ] PlayerStats: ability scores в сетке, AC/gold/level
- [ ] ActionBar: кнопки из useAvailableActions, disable + spinner при ожидании ответа
- [ ] ErrorBoundary: глобальный на App, toast для WS ошибок (shadcn Sonner)
- [ ] Responsive: sidebar → drawer на md breakpoint
- [ ] Проверить: создать сессию → мирный ход → look → go → wait → всё работает

Результат: можно играть в мирном режиме через новый UI.

---

### Phase 5: Combat Mode

Цель: боевой режим с budget tracking и battle map.

```
src/components/game/
├── BattleMap.tsx            # ASCII grid в <pre> (MVP), потом заменим
├── CombatPanel.tsx          # враги: имя, расстояние, направление, ранен?
└── BudgetDisplay.tsx        # actions: 1/1, movement: 30/30, bonus: 1/1
```

Шаги:
- [ ] GameScreen: переключать layout при mode === "combat" (показать BattleMap + CombatPanel)
- [ ] BattleMap: рендерить ASCII из бэкенда в <pre> с моноширинным шрифтом
- [ ] CombatPanel: список врагов из combat awareness, расстояние + направление
- [ ] BudgetDisplay: визуализация оставшихся ресурсов (иконки или прогресс-бары)
- [ ] ActionBar в бою: Attack (dropdown с целями), Dodge, Flee, Move (dropdown с направлениями), Dash, End Turn
- [ ] Disable кнопок по budget (нет actions → disable Attack/Dodge, нет movement → disable Move)
- [ ] Проверить: войти в бой → атаковать → передвинуться → закончить ход → NPC ходят → новый раунд

Результат: можно воевать через новый UI.

---

### Phase 6: Master Panel

Цель: DM может управлять сессиями и миром.

```
src/components/master/
├── MasterScreen.tsx         # layout: SessionList + WorldView
├── SessionList.tsx          # список сессий, создать/удалить
├── WorldOverview.tsx        # регионы, нации, поселения — таблицы с фильтрами
├── CreatureList.tsx         # все существа, фильтры по типу/локации
├── CreatureForm.tsx         # spawn/edit creature — react-hook-form + zod
└── TimeControl.tsx          # advance time slider + button
```

Шаги:
- [ ] Роутинг: `/master` → список сессий, `/master/:id` → управление конкретной
- [ ] masterStore: отдельный Zustand store, REST polling каждые 5s
- [ ] SessionList: карточки сессий, кнопки Create/Delete
- [ ] WorldOverview: shadcn Table для регионов/наций/поселений
- [ ] CreatureList: таблица с фильтрами, кнопки Edit/Delete/Spawn
- [ ] CreatureForm: Dialog с формой, все поля SpawnCreatureRequest
- [ ] TimeControl: input hours + кнопка "Advance"
- [ ] Saves: список сейвов, Save/Load/Delete
- [ ] Проверить: создать сессию → заспавнить NPC → поменять HP → промотать время

Результат: DM может управлять игрой без curl/Swagger.

---

### Phase 7: Polish

Цель: довести до приемлемого уровня качества.

Шаги:
- [ ] Toast notifications: подключение/отключение WS, ошибки, успех операций
- [ ] Loading states: Skeleton для всех async-данных
- [ ] Keyboard shortcuts: Enter → отправить команду, Escape → закрыть модалку
- [ ] Command input: текстовое поле внизу как fallback (для опытных пользователей)
- [ ] Favicon + title с именем персонажа
- [ ] Убрать старый debug UI из FastAPI static (или переместить в /debug)
- [ ] Обновить Makefile: `make serve` поднимает бэкенд + отдаёт frontend/dist
- [ ] Обновить README / docs

---

## Out of Scope (future)

- Кликабельная 2D battle map (Canvas/SVG)
- Инвентарь и экипировка
- Книга заклинаний / ability bar
- Журнал квестов
- Контекстное меню NPC (торговля, квесты)
- Интерактивная карта мира для DM
- i18n фреймворк (react-i18next)
- Тесты фронтенда (vitest + testing-library)
- Mobile-specific layout
