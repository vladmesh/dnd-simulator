# Sprint 011 — Class Mechanics L1 Completion

**Goal:** Structured dice pipeline, типизированное оружие/броня с D&D 5e свойствами, Great Weapon Fighting, Cunning Action с выбором cost, SA faction check, каталог экипировки, кликабельный лог бросков, контент и тесты.

**Started:** 2026-03-28

## Context

Sprint 001 заложил инфраструктуру классовых механик (proficiency, armor/shield, ResourcePool, ClassFeatures, modifier pipeline) и реализовал Fighter/Rogue L1. Но Phase 4 (контент, тесты) не закрыта, а ключевые weapon properties (`is_two_handed`, `light`, `heavy`, `versatile`) отсутствуют — без них Dueling не может проверить "одноручное", Great Weapon Fighting невозможен. Cunning Action работает на бэкенде, но UI не даёт рогу выбрать bonus vs action. SA считает любое существо рядом с целью "союзником" — Sprint 004 добавил faction relations, зависимость закрыта.

Параллельно: `roll()` возвращает голый `int`, теряя face values отдельных кубиков, рероллы, и advantage dice. Для GWF нужен механизм реролла, а для UX — кликабельный лог бросков с полной трассировкой модификаторов. Phase 0 строит structured dice pipeline как фундамент для обоих.

**Ссылки:** [sprint 001](../001-class-mechanics/sprint.md), [ecs-and-content](../../brainstorms/ecs-and-content.md), [backlog](../../BACKLOG.md)

---

## Phase 0: Structured Dice & Roll Breakdown

Рефактор dice pipeline: каждый бросок возвращает structured data с individual die faces, рероллами, advantage dice. Event data несёт полный breakdown. Фронтенд рендерит кликабельный лог с раскрывающейся детализацией.

- `core/rolls.py` — `DieRoll` (sides, result, original), `DiceResult` (expression, dice tuple, flat, total), `D20Result` (die, alt, advantage/disadvantage)
- `rules/dice.py` — `roll()` → `DiceResult`, `roll_d20()` → `D20Result`, `reroll_below` для GWF-style рероллов
- `rules/checks.py` / `rules/combat.py` — threading structured results through `CheckResult`, `DamageResult`, `AttackResult`
- `combat_manager` — event serialization с `d20`, `d20_alt`, `dice_detail` (individual faces + originals)
- Frontend — attack events expandable, `RollBreakdown` component с d20, модификаторами, dice faces, reroll indicators

**Верифицируем:** `roll("2d6+3")` returns structured `DiceResult` with individual dies. Attack events in frontend are clickable and show full modifier breakdown. GWF rerolls visible as `[1→5]`.

**Tasks:**

1. [Structured Dice Results](tasks/phase0-task1-structured-dice.md)
2. [Attack & Damage Breakdown Pipeline](tasks/phase0-task2-breakdown-pipeline.md)
3. [Frontend Clickable Roll Breakdown](tasks/phase0-task3-frontend-clickable-log.md)
4. [Attack Card Modal](tasks/phase0-task4-attack-card-modal.md)

## Phase 1: BattleMap Reachability

Единый расчёт reachability на бэкенде. Устранить дублирование BFS между фронтом и бэком. Фронт становится тупым рендерером — рисует то, что бэк посчитал.

- `rules/movement.py` — `compute_reachable(start, budget, battle_map, mover_id)` → `dict[Position, list[Position]]` (позиция → кратчайший путь). Dijkstra с D&D 5e diagonal costs (5/10 чередование)
- `find_path` → обёртка над `compute_reachable` (убирает дублирование алгоритма)
- `move_to` handler → берёт path из reachable map, гарантия согласованности фронт/бэк
- `AwarenessBuilder` → добавляет `reachable: list[[x, y]]` в `CombatAwareness`
- Frontend `BattleMap.tsx` → убрать `computeReachable()` и `buildBlockedEdges()`, рисовать reachable по данным с бэка
- RuleBrain → использовать reachable для умного движения (обход стен, проверка достижимости цели)

**Верифицируем:** Unit tests: reachable совпадает с ожидаемым при стенах и diagonal movement. `move_to` на edge cell работает корректно (баг из Gemini report). Фронт подсвечивает ровно те клетки, что бэк вернул. RuleBrain не ходит в стену.

**Tasks:**

1. [Backend Reachability Engine](tasks/phase1-task1-reachability-engine.md)
2. [Awareness Pipeline + Frontend Simplification](tasks/phase1-task2-awareness-frontend.md)

## Phase 2: Weapon Properties & Fighting Styles ✓

Добавить D&D 5e свойства оружия на WeaponDef и использовать их в боевых механиках.

- `is_two_handed`, `is_light`, `is_heavy`, `versatile_damage` на WeaponDef
- Dueling style проверяет: оружие одноручное (`not is_two_handed`) и нет щита — только тогда +2
- Great Weapon Fighting: перебрасывать 1-2 на кубах урона для `is_two_handed` оружия. Новый FightingStyle + modifier pipeline
- Каталог оружия: longsword, greatsword, greataxe, shortsword, rapier, dagger, quarterstaff, longbow, shortbow, hand crossbow, mace, warhammer (SRD базовый набор). Все с корректными свойствами
- Каталог брони: padded, leather, studded leather, hide, chain shirt, scale mail, breastplate, half plate, ring mail, chain mail, splint, plate. Shield

**Верифицируем:** Unit tests: Dueling не даёт +2 для two-handed. GWF перебрасывает 1-2. Каталог загружается, все предметы имеют корректные свойства.

**Tasks:**

1. [Weapon Properties & Fighting Style Mechanics](tasks/phase2-task1-weapon-props-fighting-styles.md)
2. [SRD Weapon & Armor Catalogs](tasks/phase2-task2-weapon-armor-catalogs.md)

## Phase 3: Cunning Action Choice & SA Faction Check ✓

Дать рогу реальный выбор cost_mode и исправить SA ally detection.

- `cost_mode` как опциональный ParamDef на DASH/DISENGAGE для существ с cost overrides
- ActionProvider строит варианты: если есть CostOverride — предлагает оба варианта (action и bonus_action)
- Фронтенд: кнопки Dash/Disengage показывают cost badge и позволяют выбрать
- SA ally-adjacency: проверять faction relations (Sprint 004) вместо "любое живое существо"
- Disengage остаётся заглушкой (нет opportunity attacks без системы реакций) — это ОК

**Верифицируем:** Unit tests: рог может Dash как bonus + Attack как action в одном ходу. Рог может Dash как action (без cost_mode). SA не срабатывает когда "союзник" — враг по faction. Фронтенд показывает выбор.

**Tasks:**

1. [Sneak Attack Faction-Aware Ally Detection](tasks/phase3-task1-sa-faction-check.md)
2. [Cunning Action Cost Choice (Backend + Frontend)](tasks/phase3-task2-cunning-action-cost-choice.md)

## Phase 4: Content & Tests

Закрыть долг Sprint 001 Phase 4. Контент + полное тестовое покрытие.

- Fighter и Rogue NPC в village.yaml (или sword_vale) с полной экипировкой и class features
- Оружие/броня на существующих NPC (guard → chain mail + longsword, etc.)
- Unit tests для всех механик Sprint 001 + этого спринта: ClassFeatures, Fighting Styles (Defense, Dueling, GWF), Second Wind, Sneak Attack, Cunning Action, weapon properties, proficiency
- Audit + cleanup по результатам

**Верифицируем:** `make check` зелёный. NPC в контенте используют class features и экипировку. Аудит без critical findings.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 0 tasks generated. Ready to start Phase 0 Task 1.

## Decisions

- **`roll()` returns `DiceResult`, not `int`.** Single source of truth — no parallel `roll_detailed()`. All callers use `.total` for arithmetic. Clean, no dual paths to maintain.
- **`D20Result` is separate from `DiceResult`.** Advantage picks best/worst (not sum). Different semantics warrant different type.
- **`reroll_below` on `roll()` — generic parameter.** Handles GWF (reroll ≤ 2), Halfling Lucky (reroll ≤ 1), and future per-die reroll effects. Single reroll, records `DieRoll.original`. Not recursive.
- **GWF reroll, not range reduction.** `max(roll, 3)` changes the probability distribution (E[d6]=4.0 vs reroll E[d6]=4.17). Reroll is D&D RAW and gives better UX (visible reroll in log).
- **Skill checks don't crit.** D&D 5e RAW — only attack rolls crit on nat 20.

- **Disengage — заглушка.** Без системы реакций (opportunity attacks) Disengage не имеет механического эффекта. Оставляем как есть — действие существует, бюджет тратится, при добавлении реакций заработает без изменений.
- **Thrown/ammunition/loading — вне скоупа.** Ranged weapon properties (thrown, ammunition, loading) требуют отдельной системы (боеприпасы, дальность). Longbow/shortbow добавляются в каталог, но без ammunition tracking.
- **Extra Attack, skill checks, Hide, Expertise, saving throws — вне скоупа.**
- **Clickable log — только attack events в Phase 0.** Skill checks, healing, Second Wind — данные в event data будут (dice_detail), но UI expand только для атак. Расширяем позже.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
