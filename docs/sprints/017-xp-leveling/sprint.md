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

## Phase 3: Level-up UI + E2E ✓

Frontend level-up модалка. Пингуется из состояния (`level_up_available: true` в player/character payload), всплывает кнопкой / автоматически после боя. Для каждого класса — класс-условная форма с выборами: Fighter L2 (без выбора — подтверждение), Rogue L2 (без выбора), Paladin L2 (Fighting Style dropdown — Defense/Dueling/GWF). Показывается прирост HP, новые ресурсы (Action Surge slot, spell slots). По submit — API call, обновление панели персонажа. E2E через Playwright: полный цикл (kill → XP tick → modal → choice → features applied → visible в Character panel).

**Решение по scope:** отказались от "schema-driven" формы — `SchemaForm` избыточен для единственного enum dropdown. Используем plain class-switched `LevelUpModal` (паттерн как у `SmiteChoice`). `SchemaForm` остаётся зарезервирован для content editor до тех пор, пока у level-up не появятся богатые выборы (ASI/feats на L4).

**Tasks:**

1. [LevelUpModal + API client](tasks/phase3-task1-level-up-modal.md) — компонент, класс-условная форма, `apiClient.levelUp`, unit-тесты
2. [Dashboard integration](tasks/phase3-task2-dashboard-integration.md) — кнопка в `PlayerStats`, авто-открытие, sync Zustand
3. [E2E full cycle](tasks/phase3-task3-e2e-level-up.md) — отдельный тест-мир `level_up_test`, high-XP моб → modal → Dueling → второй бой (Smite + Dueling бонус)

---

## Phase 4: E2E follow-up bug sweep ✓

Багрепорт по итогам phase 3 E2E. Каждый таск — детальное расследование причины + исправление наилучшим архитектурным способом (не косметика, не «закостылять чтобы тест прошёл»). Перед фиксом — RCA в developer notes таска. Phase закроется только после того, как E2E phase 3 переигрывается без шероховатостей из списка.

**Tasks:**

1. [RuleBrain убегает у безоружных мобов](tasks/phase4-task1-rulebrain-flees.md) — `xp_dummy` дашит прочь от боя при низком WIS, ломает детерминизм арены. Расследовать триггер в RuleBrain → выбрать политику (stand-and-fight для определённого role / faction / brain hint, либо явный `combat_stance` на Creature).
2. [Координаты battle map vs combat_position](tasks/phase4-task2-battlemap-coords.md) — игрок в YAML на `[5,5]`, отрисовывается как `cell-11-7`. Найти где переворачивается/смещается ось, унифицировать систему координат, описать инвариант в комментарии и тесте.
3. [Per-location battle_map size в YAML](tasks/phase4-task3-battlemap-size.md) — арена описана 3×3, движок берёт `DEFAULT_BATTLE_MAP_SIZE`. Расширить geography schema на `battle_map: {width, height, walls?}` per-location (или per-region с явным маппингом), удалить `DEFAULT_BATTLE_MAP_SIZE` fallback в локациях, где это критично для теста.
4. [Combat sidebar — stale HP после level-up](tasks/phase4-task4-combat-sidebar-stale-hp.md) — top-bar HP обновляется сразу, `PlayerStats` в combat-сайдбаре держит старое значение до конца раунда. Найти источник (Zustand selector / WS turn payload / отдельный кеш) и починить так, чтобы оба компонента читали из одного места.
5. [Cancel level-up modal — поведение](tasks/phase4-task5-levelup-cancel.md) — кнопка Cancel есть, но контракт не задокументирован и не покрыт тестом. Определить семантику (закрыть и оставить `level_up_available=true`? повторно показать при следующем `turn`?), реализовать, добавить unit + E2E.
6. [Двойная Attack-кнопка в a11y-снапшоте](tasks/phase4-task6-attack-button-a11y.md) — DOM содержит две кнопки с одинаковым accessible name «Attack» (anchor + первый item submenu). Минор, но мешает скрин-ридерам и Playwright-селекторам. Выбрать корректный паттерн (role=menu / aria-haspopup), починить.

---

## Phase 5: Post-audit cleanup ✓

Триаж audit 2026-04-13 выявил 5 sprint-relevant пунктов в коде, который трогал sprint 017 (leveling/XP). Делаем дедикейтед фазой, чтобы не тащить долг в backlog и не накапливать нарушения чистоты `rules/` пока контекст ещё свежий.

**Tasks:**

1. [perform_level_up purity](tasks/phase5-task1-perform-level-up-purity.md) — переписать на `replace()`-pattern или явно задокументировать как stateful op + покрыть инвариантом
2. [Leveling unit tests](tasks/phase5-task2-leveling-unit-tests.md) — изолированные unit-тесты для `rules/leveling.py` (XP-by-CR, thresholds, edge cases)
3. [perform_level_up unit tests](tasks/phase5-task3-perform-level-up-unit-tests.md) — изолированные unit-тесты для каждого class-path level-up
4. [Level-up via GameService](tasks/phase5-task4-level-up-service-method.md) — `routes_player.py` перестать звать `perform_level_up`/`xp_to_next_level`/`effective_ac` напрямую из rules; добавить методы в GameService
5. [schemas.py Any → object/typed](tasks/phase5-task5-schemas-any-cleanup.md) — заменить 5 уз `Any` в `content_loader/schemas.py` на `object` или конкретные типы где возможно

## Status

**Current:** All phases complete (2026-04-13). Ready for sprint close.

## Decisions

- Rogue Cunning Action остаётся на L1 (divergence from PHB, documented).
- Fighter L2 Action Surge — включён в скоуп.
- Paladin Divine Sense — отложен в backlog (требует `CreatureType` enum).
- Старые save'ы не мигрируются, удаляются.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
