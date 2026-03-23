# Frontend: React SPA

Замена debug UI на полноценный React-фронтенд.
Браinstorm: `docs/brainstorms/frontend-architecture.md`

## Stack

```
React 19 + TypeScript + Vite
TailwindCSS 4 + shadcn/ui (base-nova style)
Zustand (slices pattern)
React Router 7
react-hook-form + zod (формы)
react-i18next (en/ru, namespaced JSON)
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
- [x] Роутинг: `/` → SetupScreen, `/play/:id` → GameScreen (пока заглушка)
- [x] WorldPicker: загрузить миры, показать карточки с именем и описанием
- [x] Кнопка "New Session" → POST /sessions → получить session_id
- [x] CharacterForm: имя, раса, класс, уровень, alignment, ability scores, HP, AC
- [x] Валидация через zod-схему (например: HP > 0, ability scores 1-30)
- [x] После создания персонажа → navigate(`/play/${sessionId}`)
- [x] SessionConnect: альтернативный путь — ввести ID существующей сессии
- [x] Проверить: от открытия страницы до попадания на /play/:id без ошибок

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
- [x] GameScreen: useWebSocket hook — connect при mount, disconnect при unmount
- [x] Header: HP bar с цветом (green > 50%, yellow > 25%, red), данные из player slice
- [x] EventLog: @tanstack/react-virtual, автоскролл, моноширинный шрифт
- [x] Perception: список nearby из awareness, при клике — popover с действиями
- [x] LocationPanel: имя + описание + список путей как кнопки
- [x] PlayerStats: ability scores в сетке, AC/gold/level
- [x] ActionBar: кнопки из useAvailableActions, disable + spinner при ожидании ответа
- [x] ErrorBoundary: глобальный на App + отправка ошибок на бэкенд (POST /api/frontend-error)
- [x] Responsive: sidebar → drawer на md breakpoint
- [x] Проверить: создать сессию → мирный ход → look → go → wait → всё работает (Playwright)

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
- [x] GameScreen: переключать layout при mode === "combat" (показать BattleMap + CombatPanel)
- [x] BattleMap: рендерить ASCII из бэкенда в <pre> с моноширинным шрифтом
- [x] CombatPanel: список врагов из combat awareness, расстояние + направление
- [x] BudgetDisplay: визуализация оставшихся ресурсов (иконки или прогресс-бары)
- [x] ActionBar в бою: Attack (dropdown с целями), Dodge, Flee, Move (dropdown с направлениями), Dash, End Turn
- [x] Disable кнопок по budget (нет actions → disable Attack/Dodge, нет movement → disable Move)
- [x] Проверить: войти в бой → атаковать → передвинуться → закончить ход → NPC ходят → новый раунд

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
- [x] Роутинг: `/master` → список сессий, `/master/:id` → управление конкретной
- [x] masterStore: отдельный Zustand store, REST polling каждые 5s
- [x] SessionList: карточки сессий, кнопки Create/Delete
- [x] WorldOverview: shadcn Table для регионов/наций/поселений
- [x] CreatureList: таблица с фильтрами, кнопки Edit/Delete/Spawn
- [x] CreatureForm: Dialog с формой, все поля SpawnCreatureRequest
- [x] TimeControl: input hours + кнопка "Advance"
- [x] Saves: список сейвов, Save/Load/Delete
- [x] Проверить: создать сессию → заспавнить NPC → поменять HP → промотать время

Результат: DM может управлять игрой без curl/Swagger.

---

### Phase 7: Polish

Цель: довести до приемлемого уровня качества.

Шаги:
- [ ] Toast notifications: подключение/отключение WS, ошибки, успех операций
- [ ] Loading states: Skeleton для всех async-данных
- [ ] Keyboard shortcuts: Escape → закрыть модалку
- [x] Command input: текстовое поле внизу как fallback (для опытных пользователей) + Enter → отправить
- [ ] Favicon + title с именем персонажа
- [ ] Убрать старый debug UI из FastAPI static (или переместить в /debug)
- [ ] Обновить Makefile: `make serve` поднимает бэкенд + отдаёт frontend/dist
- [ ] Обновить README / docs

---

## Отклонения от плана

### i18n — добавлен досрочно (между Phase 4 и Phase 5)

Изначально `react-i18next` был в Out of Scope. Перенесён в скоуп, т.к. бэкенд и контент полностью двуязычные (en/ru) — бессмысленно не использовать.

Реализация:
- `react-i18next` + `i18next`, неймспейсы: `common`, `setup`, `game`, `master`
- JSON-файлы в `src/i18n/locales/{en,ru}/`
- Автодетект по `navigator.language`, кнопка переключения EN/RU на экране выбора мира
- `lang` передаётся в `getWorlds()` и `createSession()` → бэкенд отдаёт переведённый контент
- Все компоненты Phase 3-4 переведены на `t()`
- Новые компоненты пишутся сразу с `t()`

### ErrorBoundary — расширен

План предусматривал ErrorBoundary + toast (Sonner). Реализовано:
- ErrorBoundary ловит React-краши, показывает ошибку, отправляет POST /api/frontend-error
- window.onerror + unhandledrejection → тоже POST на бэкенд
- Бэкенд логирует `FRONTEND ERROR: ...` — видно в серверных логах без браузера
- Toast (Sonner) отложен на Phase 7

### WebSocket — исправлена совместимость с StrictMode

- Vite proxy: объединён `/api` + `/ws` в один proxy с `ws: true`
- wsClient: добавлена защита от stale onclose (проверка `this.ws !== ws`)
- connectionSlice: store updates из WS-коллбэков через `setTimeout(0)` (useSyncExternalStore tearing)
- GameScreen: `useRef` guard против двойного подключения в StrictMode

### BattleMap ASCII — генерируется на бэкенде

Добавлен метод `BattleMap.render_ascii(observer_id)` в `core/combat.py`. Генерирует ASCII-карту с `@` (игрок), `1-9` (враги), `|`/`-` (стены). Передаётся через новое поле `battle_map_ascii` в `CombatAwareness` → автоматически сериализуется в WS-сообщение. Фронтенд рендерит в `<pre>`.

### BudgetDisplay — вынесен в отдельный компонент

Изначально budget отображался inline в ActionBar. Вынесен в `BudgetDisplay.tsx` с иконками (Swords/Zap/Footprints/Shield) и визуальным затемнением исчерпанных ресурсов. Используется и в мирном, и в боевом режиме.

### Master Panel — без отдельного Zustand store

План предусматривал `masterStore` (отдельный Zustand store с REST polling). Реализовано проще: каждый компонент (`MasterScreen`, `SessionView`, `CreatureList`, `SavesPanel`) управляет своим состоянием через `useState` + `useCallback` + `useEffect`. Автообновление через `setInterval` в `SessionView` (каждые 5s). Отдельный store не нужен — master-компоненты не делят состояние между собой, а REST-ответы не требуют cross-component реактивности.

### Master Panel — shadcn Dialog установлен для CreatureForm

`CreatureForm` использует shadcn Dialog (`@base-ui/react/dialog`): фокус-трап, Escape для закрытия, aria-атрибуты, анимации. `DialogContent` с `max-h-[85vh] overflow-y-auto` для длинных форм.

### Playwright MCP — добавлен для отладки

Не был в плане. Добавлен headless Playwright через MCP для автоматизированного тестирования UI без ручного открытия браузера.

---

## Что дальше

Следующая фаза: **Phase 7 — Polish**. Toast, loading states, keyboard shortcuts, favicon, cleanup.

---

## Out of Scope (future)

- Кликабельная 2D battle map (Canvas/SVG)
- Инвентарь и экипировка
- Книга заклинаний / ability bar
- Журнал квестов
- Контекстное меню NPC (торговля, квесты)
- Интерактивная карта мира для DM
- ~~i18n фреймворк (react-i18next)~~ → реализовано
- Тесты фронтенда (vitest + testing-library)
- Mobile-specific layout
