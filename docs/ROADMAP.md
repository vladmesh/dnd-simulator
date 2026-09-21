# Roadmap

Здесь только то, что ещё не сделано. История спринтов (Phase 1 … Sprint 024 и далее sprint:1439,
sprint:1440) живёт в knowledge инстанса секретаря — `state/knowledge/projects/dnd-simulator/`
(таблица Sprint History в `README.md`, документы `sprints/NNN-*.md`, снимок прежнего раздела Done —
`archive/roadmap-2026-09-21.md`). Баги, tech debt и «что болит» — issue продукта на доске:
`issue list --product dnd-simulator`.

## Planned

### Level 2 — Расходуемые ресурсы
Spell slots, ki, rage. Дополнительные типы брони и оружия.
→ брейншторм `brainstorms/ecs-and-content.md` в knowledge

### Level 3 — Заклинания, пропсы
Заклинания как YAML, интерактивные объекты (двери, сундуки).
→ брейншторм `brainstorms/ecs-and-content.md` в knowledge; issue «Заклинания как контент»

### Simulation Core — лестница детализации и квесты
Заменяет прежний план «Phase 3 — Автономные тики» (периодические тики отброшены в пользу
decision-точек). Цепочка эпиков: ~~единая схема сейва~~ (Sprint 021) → ~~якорь-как-свойство +
намерения~~ (Sprint 022) → ~~парные триггеры `{on, until}` активации/гашения~~ (Sprint 023) →
~~внутреннее я NPC: цели, отношения, живой alignment, переваривание + правиловый близнец~~
(sprint:1440, issue:31d690479658e3a80c1d) → лестница детализации поселений (событийная запись,
храповик субъектности) → квесты как контент поверх целей и триггеров.

Боевой статус как единый источник истины закрыт sprint:1439 (issue:0eaae2e74620d18ca1b0); открытый
продуктовый остаток той же линии — редизайн побега (issue:163d78f9e6ed548c25af).
→ брейншторм `brainstorms/simulation-core.md` в knowledge; issue «Лестница детализации поселений
и инструменты ГМ», «Квесты как типизированные цели поверх inner-self»

### World Builder (advanced)
Расширенный world builder: редактор слоёв (YAML editor в UI), превью мира перед стартом,
маркетплейс шаблонов. Базовый wizard (выбор из библиотеки) реализован в Sprint 006.
→ план `archive/plan-world-builder.md` в knowledge (карта файлов устарела)

### Мультиплеер
Несколько игроков в одном мире. Механика активности уже поддерживает это — игре всё равно,
PlayerBrain или LlmBrain. Темп: опциональный таймер хода (как в Героях), по таймауту «продолжаю
намерение / end_turn» (`brainstorms/simulation-core.md`). Предпосылка — issue про контур доступа
(identity / ownership / roles).

## Где искать остальное

- **Что болит** (баги, tech debt, тестовые дыры, фичи-кандидаты) — доска:
  `issue list --product dnd-simulator`.
- **История и дизайн** — knowledge инстанса, `state/knowledge/projects/dnd-simulator/`
  (`README.md` — точка входа, `brainstorms/` — живые дизайн-документы, `archive/` — реализованное
  и отменённое, `decisions/` — решения, `e2e-reports/` — отчёты живых прогонов).
