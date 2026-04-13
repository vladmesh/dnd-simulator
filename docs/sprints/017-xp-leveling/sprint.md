# Sprint 017 — XP & Leveling

**Goal:** Ввести XP (за убийства по CR) и систему уровней с level-up модалкой; исправить уровни Paladin (FS/slots/smite на L2), добавить L2 для всех трёх классов (Fighter Action Surge, Paladin L2 features, Rogue L2 HP).

**Started:** 2026-04-13

## Context

После sprint 015 Paladin получил Fighting Style, spell slots и Divine Smite на L1 — это ошибка относительно PHB (всё это фичи L2). Sprint 016 это не трогал. Параллельно в проекте отсутствует система опыта и уровней как таковая: `Character.level` есть как поле, но ни начисления XP, ни level-up flow нет. Монстры в каталоге имеют `cr`, абстрактный бой использует CR для encounter_power, но игрок не получает XP за kill.

Этот спринт закрывает оба пробела: добавляет XP/leveling как механику и использует её для честной выдачи классовых фич на L2. Распаковывает существующие классы до L2 и даёт UX-точку входа — level-up модалку с классовыми выборами (первый кандидат на schema-driven форму вне content editor).

**Решения по скоупу (из диалога планирования):**
- Rogue L1: Cunning Action остаётся на L1 (дивергенция от PHB, задокументирована). L2 добавляет только HP.
- Fighter L2: Action Surge включён (extra action 1/short rest).
- Paladin L1: Divine Sense отложен в backlog (требует `CreatureType` enum) — L1 остаётся с одним Lay on Hands.
- Save migration: не делаем. Старые save'ы чистим — там мусор.

**Ссылки:** [Sprint 015](../015-paladin-spell-slots/sprint.md), [Sprint 011](../011-class-mechanics-l1/sprint.md), [BACKLOG: divine-sense, divine-smite-scaling](../../BACKLOG.md)

## Phase 1: XP & Leveling Core ✓

Фундамент опыта и уровней на бэке. `experience: int` на Character, XP-by-CR таблица (стандарт D&D 5e Monster Manual), XP threshold таблица для уровней (PHB p.15), начисление XP при kill (интеграция в combat-side kill detection, omniscient как и reputation drop), детект "ready to level up" флагом на Character. Никакого UI и переноса фич классов в этой фазе — только механика и точки интеграции. Верификация: integration-тест — бой, убил монстра известного CR, `experience` и `level_up_available` корректны.

**Tasks:**

1. [Pure leveling rules](tasks/phase1-task1-leveling-rules.md) — `rules/leveling.py`: XP-by-CR + level thresholds + unit tests
2. [Wire XP to creatures and grant on kill](tasks/phase1-task2-xp-grant-on-kill.md) — поля на моделях, начисление в `_handle_death`, save/load
3. [Expose XP in player state](tasks/phase1-task3-xp-in-state.md) — payload (experience, level_up_available, xp_to_next) через REST/WS + frontend типы

## Phase 2: Level-up mechanics + Paladin L2 fix ✓

Backend-операция level-up: метод применяет классовые фичи по целевому уровню, расходует флаг `level_up_available`. Переезд Paladin L1→L2: Fighting Style, Divine Smite, spell slots становятся доступны только при level ≥ 2; L1 Paladin остаётся только с Lay on Hands. Добавляются Fighter L2 Action Surge (новый ResourcePool + action, bonus extra action, reset on short rest) и Rogue L2 (только HP + proficiency; Cunning Action уже на L1). `PaladinFeatures` / `FighterFeatures` становятся уровнево-зависимыми: `collect_*_modifiers` и pools фильтруются по текущему level. Сохранения чистим (drop legacy saves). Верификация: integration-тесты — Paladin L1 не может smite; level up до L2 → smite доступен; Fighter L2 может activate action surge; short rest восстанавливает.

**Tasks:**

1. [Level-aware class features](tasks/phase2-task1-level-aware-features.md) — `level` field on features, gate Paladin FS/smite at L2
2. [Level-aware resource pools](tasks/phase2-task2-level-aware-pools.md) — Paladin L1 no slots, Fighter L2 gets `action_surge` pool
3. [Action Surge action + handler](tasks/phase2-task3-action-surge.md) — Fighter L2 bonus action grants extra Action
4. [Level-up operation + endpoint](tasks/phase2-task4-level-up-operation.md) — `perform_level_up` + `POST /level-up`, drop legacy saves

## Phase 3: Level-up UI + E2E

Frontend level-up модалка. Пингуется из состояния (`level_up_available: true` в player/character payload), всплывает кнопкой / автоматически после боя. Для каждого класса — класс-условная форма с выборами: Fighter L2 (без выбора — подтверждение), Rogue L2 (без выбора), Paladin L2 (Fighting Style dropdown — Defense/Dueling/GWF). Показывается прирост HP, новые ресурсы (Action Surge slot, spell slots). По submit — API call, обновление панели персонажа. E2E через Playwright: полный цикл (kill → XP tick → modal → choice → features applied → visible в Character panel).

**Решение по scope:** отказались от "schema-driven" формы — `SchemaForm` избыточен для единственного enum dropdown. Используем plain class-switched `LevelUpModal` (паттерн как у `SmiteChoice`). `SchemaForm` остаётся зарезервирован для content editor до тех пор, пока у level-up не появятся богатые выборы (ASI/feats на L4).

**Tasks:**

1. [LevelUpModal + API client](tasks/phase3-task1-level-up-modal.md) — компонент, класс-условная форма, `apiClient.levelUp`, unit-тесты
2. [Dashboard integration](tasks/phase3-task2-dashboard-integration.md) — кнопка в `PlayerStats`, авто-открытие, sync Zustand
3. [E2E full cycle](tasks/phase3-task3-e2e-level-up.md) — отдельный тест-мир `level_up_test`, high-XP моб → modal → Dueling → второй бой (Smite + Dueling бонус)

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- Rogue Cunning Action остаётся на L1 (divergence from PHB, documented).
- Fighter L2 Action Surge — включён в скоуп.
- Paladin Divine Sense — отложен в backlog (требует `CreatureType` enum).
- Старые save'ы не мигрируются, удаляются.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
