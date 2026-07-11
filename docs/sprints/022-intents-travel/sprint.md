# Sprint 022 — Intentions & Travel

**Goal:** Любое существо может быть якорем и сохраняемым носителем намерения; ожидание, сон и путешествие исполняются во времени, travel движется по графу без телепортации, а save/load согласован с жизненным циклом раунда.

**Started:** 2026-07-10

## Context

Второй эпик цепочки simulation-core после единой схемы сейва Sprint 021. Текущая активация знает тип `PlayerCharacter`, ожидание хранится как частный `wake_at_seconds`, а путешествие замаскировано под `WAIT` и телепортирует существо в конечную точку. Это расходится с player-agnostic вижном и не позволяет существам пересекаться в дороге.

Спринт вводит якорь как свойство существа и первоклассное сохраняемое намерение для ожидания, сна и путешествия. Travel идёт по рёбрам графа, каждое существо остаётся в конкретной локации, базовые встроенные причины могут прервать намерение. Декларативные trigger-table, Brain gate/decide, динамические маршруты NPC, LLM-планирование, цели и квесты остаются за границей спринта.

Параллельно закрываются связанные дефекты жизненного цикла. Save/load/autosave получают общую с раундом критическую секцию; ожидание без бодрствующего якоря быстро переводит мир к ближайшей wake-точке; загруженный бой не продолжается до подключения игрока. Небольшой фикс различимых accessible names у Attack-кнопок допустим как финальный polish, но не является целью спринта.

**Ссылки:** [simulation-core](../../brainstorms/simulation-core.md), [BACKLOG](../../BACKLOG.md#simulation-core-брейншторм-2026-07-04), [Sprint 021](../021-save-schema/sprint.md)

## Phase 1: Safe session lifecycle ✓

Save, load, autosave, evict и round loop согласованы одной session-level критической секцией. Загруженная посреди боя сессия остаётся на сохранённом ходе и запускается только после подключения игрока. Проверка: конкурентный autosave не получает порванный мир; сохранённый Round 1 после load остаётся Round 1 до реконнекта.

Почему первой: следующие фазы добавляют изменяемое и сохраняемое состояние намерения, которое нельзя строить поверх известной гонки. Закрывает `save-round-concurrency` и `load-combat-round-resume`.

**Tasks:**

1. [Session-owned dice RNG](tasks/phase1-task1-session-dice-rng.md)
2. [World-state mutation gate](tasks/phase1-task2-world-state-gate.md)
3. [Consistent save and eviction paths](tasks/phase1-task3-consistent-save-paths.md)
4. [Atomic load and connection-driven resume](tasks/phase1-task4-atomic-load-resume.md)

## Phase 2: Anchors, wait and sleep intents ✓

Якорь становится свойством существа, активация больше не проверяет `PlayerCharacter`. Wait и sleep представлены сохраняемыми намерениями с длительностью и wake-точкой. Проверка: любое назначенное якорем существо удерживает локальную сцену активной; wait/sleep переживает save/load; без бодрствующего якоря мир быстро переходит к ближайшему пробуждению.

Почему второй: фаза формирует минимальную модель Intent и исправляет активацию до появления движения по графу. Закрывает `anchor-as-property`, базовую часть `intents`, `wait-no-fastforward-with-npc` и `test-gap-ws-fastforward`.

**Tasks:**

1. [Persisted anchors and timed intents](tasks/phase2-task1-persisted-anchors-intents.md)
2. [Anchor-driven activation and fast-forward](tasks/phase2-task2-anchor-activation-fast-forward.md)
3. [Wait and sleep intent lifecycle](tasks/phase2-task3-wait-sleep-lifecycle.md)

## Phase 3: Travel as an intent ✓

Игрок начинает настоящее travel-намерение. Путешественник проходит маршрут по рёбрам графа, остаётся в конкретной локации на каждом шаге и прибывает после игрового времени, а не телепортируется через `WAIT`. UI показывает текущее путешествие и его завершение. Проверка: маршрут из нескольких рёбер виден по шагам; save/load в середине дороги продолжает тот же маршрут; два активных существа могут оказаться в одной промежуточной точке.

Почему третьей: travel переиспользует Intent, wake-точки и player-agnostic активацию из Phase 2. Закрывает `travel-action-type`, основную оставшуюся часть `intents` и старый `WAIT + travel_to` хак.

**Tasks:**

1. [Travel route contract](tasks/phase3-task1-travel-route-contract.md)
2. [Travel action and leg progression](tasks/phase3-task2-travel-action-progression.md)
3. [Journey status and UI](tasks/phase3-task3-journey-ui.md)

## Phase 4: Interruptible journeys and E2E closure ✓

Wait, sleep и travel штатно прерываются базовыми встроенными причинами: телесное событие, втягивание в сцену или бой, прибытие и таймер. После прерывания существо остаётся в согласованной локации и получает управление без потери или двойного исполнения намерения. Проверка: сохранение, загрузка, реконнект и прерывание в середине пути дают одно и то же состояние; полный пользовательский сценарий проходит через UI. Здесь же закрывается `attack-buttons-accessible-names`, чтобы E2E однозначно выбирал цель.

Почему последней: прерывания проверяют совместную работу всех предыдущих фаз, не вводя декларативную trigger-table.

**Tasks:**

1. [Built-in intent interruptions](tasks/phase4-task1-built-in-intent-interruptions.md)
2. [Interruption lifecycle consistency](tasks/phase4-task2-interruption-lifecycle.md)
3. [Target accessibility and journey E2E](tasks/phase4-task3-accessibility-e2e.md)

## Phase 5: Bounded round shutdown ✓

Остановка round thread получает ограниченное время ожидания и явный отказ вместо бессрочного
зависания disconnect, load или eviction. Пока старый поток жив, сессия сохраняет его lifecycle-состояние
и не позволяет запустить новый раунд или заменить world. Проверка: зависший callback быстро возвращает
контролируемую ошибку, а после освобождения callback повторная остановка штатно очищает сессию.

Почему отдельной refactor-фазой: post-sprint audit обнаружил, что `_stop_round()` делает безлимитный
`join()` и заранее теряет ссылки на ещё живой поток. Это нарушает атомарный load-контракт Phase 1 и может
заблокировать disconnect/eviction. Фаза ограничена lifecycle-путём; общая декомпозиция `session.py`,
`round.py` и entities layer остаётся в существующем backlog.

**Tasks:**

1. [Bounded round-stop contract](tasks/phase5-task1-bounded-round-stop.md)
2. [Lifecycle boundary failure handling](tasks/phase5-task2-lifecycle-boundary-failures.md)

---

## Status

**Current:** Phase 5 complete. All phases complete; ready for fresh audit.

## Decisions

- Граница Sprint 022: anchors + сохраняемые intents для wait/sleep/travel + встроенные прерывания. Декларативные trigger-table, Brain gate/decide, NPC wandering, LLM-планирование, цели и квесты остаются за пределами спринта (2026-07-10).
- Связанные lifecycle-дефекты `save-round-concurrency`, `load-combat-round-resume` и `wait-no-fastforward-with-npc` входят в основной scope; `attack-buttons-accessible-names` закрывается как E2E-polish (2026-07-10).
- Phase 1: session-level world gate недостаточен, пока dice RNG process-global. Dice RNG переводится во владение сессии до синхронизации snapshot; модульный fallback остаётся только для изолированных правиловых тестов (2026-07-10).
- Post-sprint audit: bounded round shutdown выделен в Phase 5. Общая декомпозиция lifecycle/payload responsibilities и растущих entities/round modules остаётся в каноническом backlog, без расширения refactor-фазы (2026-07-12).

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
