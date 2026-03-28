# Sprint 011 — Class Mechanics L1 Completion

**Goal:** Типизированное оружие/броня с D&D 5e свойствами, Great Weapon Fighting, Cunning Action с выбором cost, SA faction check, каталог экипировки, контент и тесты.

**Started:** 2026-03-28

## Context

Sprint 001 заложил инфраструктуру классовых механик (proficiency, armor/shield, ResourcePool, ClassFeatures, modifier pipeline) и реализовал Fighter/Rogue L1. Но Phase 4 (контент, тесты) не закрыта, а ключевые weapon properties (`is_two_handed`, `light`, `heavy`, `versatile`) отсутствуют — без них Dueling не может проверить "одноручное", Great Weapon Fighting невозможен. Cunning Action работает на бэкенде, но UI не даёт рогу выбрать bonus vs action. SA считает любое существо рядом с целью "союзником" — Sprint 004 добавил faction relations, зависимость закрыта.

**Ссылки:** [sprint 001](../001-class-mechanics/sprint.md), [ecs-and-content](../../brainstorms/ecs-and-content.md), [backlog](../../BACKLOG.md)

---

## Phase 1: Weapon Properties & Fighting Styles

Добавить D&D 5e свойства оружия на WeaponDef и использовать их в боевых механиках.

- `is_two_handed`, `is_light`, `is_heavy`, `versatile_damage` на WeaponDef
- Dueling style проверяет: оружие одноручное (`not is_two_handed`) и нет щита — только тогда +2
- Great Weapon Fighting: перебрасывать 1-2 на кубах урона для `is_two_handed` оружия. Новый FightingStyle + modifier pipeline
- Каталог оружия: longsword, greatsword, greataxe, shortsword, rapier, dagger, quarterstaff, longbow, shortbow, hand crossbow, mace, warhammer (SRD базовый набор). Все с корректными свойствами
- Каталог брони: padded, leather, studded leather, hide, chain shirt, scale mail, breastplate, half plate, ring mail, chain mail, splint, plate. Shield

**Верифицируем:** Unit tests: Dueling не даёт +2 для two-handed. GWF перебрасывает 1-2. Каталог загружается, все предметы имеют корректные свойства.

**Tasks:**

1. [Weapon Properties & Fighting Style Mechanics](tasks/phase1-task1-weapon-props-fighting-styles.md)
2. [SRD Weapon & Armor Catalogs](tasks/phase1-task2-weapon-armor-catalogs.md)

## Phase 2: Cunning Action Choice & SA Faction Check

Дать рогу реальный выбор cost_mode и исправить SA ally detection.

- `cost_mode` как опциональный ParamDef на DASH/DISENGAGE для существ с cost overrides
- ActionProvider строит варианты: если есть CostOverride — предлагает оба варианта (action и bonus_action)
- Фронтенд: кнопки Dash/Disengage показывают cost badge и позволяют выбрать
- SA ally-adjacency: проверять faction relations (Sprint 004) вместо "любое живое существо"
- Disengage остаётся заглушкой (нет opportunity attacks без системы реакций) — это ОК

**Верифицируем:** Unit tests: рог может Dash как bonus + Attack как action в одном ходу. Рог может Dash как action (без cost_mode). SA не срабатывает когда "союзник" — враг по faction. Фронтенд показывает выбор.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Content & Tests

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

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **Disengage — заглушка.** Без системы реакций (opportunity attacks) Disengage не имеет механического эффекта. Оставляем как есть — действие существует, бюджет тратится, при добавлении реакций заработает без изменений.
- **Thrown/ammunition/loading — вне скоупа.** Ranged weapon properties (thrown, ammunition, loading) требуют отдельной системы (боеприпасы, дальность). Longbow/shortbow добавляются в каталог, но без ammunition tracking.
- **Extra Attack, skill checks, Hide, Expertise, saving throws — вне скоупа.**

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
