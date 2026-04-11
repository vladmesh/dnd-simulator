# Sprint 016 — Tech Sweep

**Goal:** Fix 6 E2E/backlog bugs, resolve 5 architecture violations, add 3 enums + harden fail-fast across codebase.

**Started:** 2026-04-12

## Context

Последний техспринт — 005 (10 спринтов назад). Аудит post-015 выявил 32 issue, E2E отчёт — 5 findings. Баги влияют на играбельность (AC в бою, фантомные кнопки), архитектурные нарушения накопились (round→layers, core→rules, llm→layers, thick adapter). Строковые сравнения вместо enum'ов в 5+ файлах, 54 .get() с silent defaults в perception.

**Ссылки:** [audit](../../audit.md), [e2e report](../../e2e-reports/2026-04-12-regression.md), [backlog](../../BACKLOG.md)

---

## Phase 1: Bug Sweep

Все баги из E2E 2026-04-12 + backlog. AC в бою (Defense style не применяется в combat resolution), фантомная кнопка "3" на Fighter action bar, raw snake_case имена экшенов (`long_rest`, `lay_on_hands`), raw `bonus_action` в тултипе, missing frontend formatter для `entity_second_wind`, battle map configs из regions.yaml не подключены.

**Верифицируем:** Re-run E2E сценарии: 4.2 (AC=19), 3.2 (AC в бою), action bar (no mystery button), action names localized, Second Wind log readable, battle map размер из regions.yaml.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: Adapter & Routes

Оба касаются routes_master.py. Вынос `get_session_state()` в GameService (thick adapter → thin). Split routes_master.py на 2-3 модуля: session-control, content-editing, world-management.

**Верифицируем:** Integration tests pass, routes_master удалён или < 200 строк, новые модули < 250 строк каждый.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Core Boundaries

Три нарушения зависимостей. round.py → EntitiesLayer прямой импорт — через World/Layer interface. core/brain.py lazy-imports rules/ — RuleBrain в rules/ или inject. llm/ imports Npc/NpcMemory из layers — Protocol или pass data.

**Верифицируем:** `grep -rn "from.*layers" src/dnd_simulator/round.py src/dnd_simulator/core/brain.py src/dnd_simulator/llm/` → пусто. mypy + tests pass.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Enums & Fail-Fast

EntityType(StrEnum) — убрать "player"/"npc"/"creature" строковые сравнения. BrainType(StrEnum) — убрать `ai_type == "rule_based"`. LayerSource enum — убрать `source == "library"`. Perception 54x .get() → fail-fast. Silent failures: movement ValueError pass → error, autosave suppress → log. Test bare status codes → HTTPStatus.

**Верифицируем:** grep для удалённых паттернов → пусто. mypy + tests pass.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
