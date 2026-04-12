# Sprint 016 — Tech Sweep

**Goal:** Fix 6 E2E/backlog bugs, resolve 5 architecture violations, add 3 enums + harden fail-fast across codebase.

**Started:** 2026-04-12

## Context

Последний техспринт — 005 (10 спринтов назад). Аудит post-015 выявил 32 issue, E2E отчёт — 5 findings. Баги влияют на играбельность (AC в бою, фантомные кнопки), архитектурные нарушения накопились (round→layers, core→rules, llm→layers, thick adapter). Строковые сравнения вместо enum'ов в 5+ файлах, 54 .get() с silent defaults в perception.

**Ссылки:** [audit](../../audit.md), [e2e report](../../e2e-reports/2026-04-12-regression.md), [backlog](../../BACKLOG.md)

---

## Phase 1: Bug Sweep ✓

Все баги из E2E 2026-04-12 + backlog. AC в бою (Defense style не применяется в combat resolution), фантомная кнопка "3" на Fighter action bar, raw snake_case имена экшенов (`long_rest`, `lay_on_hands`), raw `bonus_action` в тултипе, missing frontend formatter для `entity_second_wind`, battle map configs из regions.yaml не подключены.

**Верифицируем:** Re-run E2E сценарии: 4.2 (AC=19), 3.2 (AC в бою), action bar (no mystery button), action names localized, Second Wind log readable, battle map размер из regions.yaml.

**Tasks:**

1. [Fix class_features lost on save/load (AC Defense bug)](tasks/phase1-task1-class-features-save-load.md) ✓
2. [Fix 26 pre-existing frontend test failures](tasks/phase1-task2-frontend-test-mocks.md) ✓
3. [Fix action bar display issues (raw names, cost labels, drawer clarity)](tasks/phase1-task3-action-bar-display.md) ✓
4. [Second Wind perception formatter + battle map content configs](tasks/phase1-task4-second-wind-log-battlemap.md) ✓

## Phase 2: Adapter & Routes ✓

Оба касаются routes_master.py. Вынос `get_session_state()` в GameService (thick adapter → thin). Split routes_master.py на 2-3 модуля: session-control, content-editing, world-management.

**Верифицируем:** Integration tests pass, routes_master удалён или < 200 строк, новые модули < 250 строк каждый.

**Tasks:**

1. [Extract get_session_state() to GameService](tasks/phase2-task1-extract-session-state.md) ✓
2. [Split routes_master.py into routes_world + routes_session](tasks/phase2-task2-split-routes-master.md) ✓

**E2E:** [phase2-report.md](e2e/phase2-report.md) — 134/134 integration tests, UI smoke pass, no blockers.

## Phase 3: Core Boundaries ✓

Три нарушения зависимостей + 1 рефакторинг модификаторов.

1. round.py → EntitiesLayer прямой импорт — через World/Layer interface.
2. core/brain.py lazy-imports rules/ — RuleBrain в rules/ или inject.
3. llm/ imports Npc/NpcMemory из layers — Protocol или pass data.
4. Fighting style modifiers scattered: `rules/modifiers.py` вручную проверяет каждый ClassFeatures (FighterFeatures, PaladinFeatures) для Defense/Dueling/GWF. Добавление нового класса (Ranger) требует правки modifiers.py — забудешь и будет баг (уже было с Paladin Defense AC). Решение: `ClassFeatures.collect_modifiers(creature) → list[Modifier]` — каждый класс декларирует свои модификаторы сам, `collect_self_modifiers()` итерирует `creature.class_features` без знания о конкретных типах. Shared logic (`_fighting_style_modifiers`) пишется один раз.

**Верифицируем:** `grep -rn "from.*layers" src/dnd_simulator/round.py src/dnd_simulator/core/brain.py src/dnd_simulator/llm/` → пусто. `grep -rn "get_feature(FighterFeatures)" src/dnd_simulator/rules/modifiers.py` → пусто. mypy + tests pass.

**Tasks:**

1. [Decouple round.py from EntitiesLayer via Layer interface](tasks/phase3-task1-round-layer-interface.md) ✓
2. [Move RuleBrain to rules/ (remove lazy rules imports from core/brain.py)](tasks/phase3-task2-rulebrain-to-rules.md) ✓
3. [Remove llm/ → layers/ dependency (move NpcMemory, Protocol for Npc)](tasks/phase3-task3-llm-layers-decouple.md) ✓
4. [ClassFeatures.collect_modifiers() — push fighting style logic into classes](tasks/phase3-task4-class-features-collect-modifiers.md) ✓

**E2E:** [phase3-report.md](e2e/phase3-report.md) — 134/134 integration tests, combat/AC/reputation pipeline verified via UI, no blockers. One pre-existing backlog item (combat.py KeyError on targetless attack click).

## Phase 4: Enums & Fail-Fast

EntityType(StrEnum) — убрать "player"/"npc"/"creature" строковые сравнения. BrainType(StrEnum) — убрать `ai_type == "rule_based"`. LayerSource enum — убрать `source == "library"`. Perception 54x .get() → fail-fast. Silent failures: movement ValueError pass → error, autosave suppress → log. Test bare status codes → HTTPStatus. Attack dispatch без `target_id` крашит в `rules/handlers/combat.py:23` (logger до валидации) — валидировать на входе в dispatcher (fail-fast с понятным сообщением), найдено E2E phase 3 2026-04-13.

**Верифицируем:** grep для удалённых паттернов → пусто. mypy + tests pass.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 3 complete 2026-04-13. Ready for Phase 4 (Enums & Fail-Fast) task generation.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
