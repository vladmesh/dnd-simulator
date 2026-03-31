# Sprint 013 — Character Creation Overhaul

**Goal:** Экран создания персонажа из "впиши любые цифры" → D&D-подобный flow: раса/класс → point buy характеристик → вычисленные HP/AC + стартовое снаряжение по классу.

**Started:** 2026-04-01

## Context

Fighter и Rogue полностью прописаны (sprints 001, 011, 012), SRD каталоги оружия/брони есть (sprint 011), AC calculation с DEX caps работает, modifier pipeline на месте. Единственный backend gap — HP формула (сейчас raw number). Остальное — wiring существующих систем в creation flow + переделка UI.

Контентный fix: Kingdom Patrol спавнит бандитов вместо стражников.

**Ссылки:** [sprint 011](../011-class-mechanics-l1/sprint.md), [sprint 012](../012-reactions-oa/sprint.md), [backlog](../../BACKLOG.md)

---

## Phase 1: HP Formula + Starting Equipment Rules

Чистые rules-функции без UI. Всё в `rules/` как pure functions, unit-тестами покрыто.

- `calculate_max_hp(char_class, level, con_modifier)` — level 1 = max hit die + CON mod (Fighter d10, Rogue d8). Min 1 HP per level.
- `starting_equipment(char_class)` — возвращает список item refs для класса. Fighter: chain mail, longsword, shield. Rogue: leather armor, rapier, shortbow, dagger.
- `validate_point_buy(scores)` — D&D 5e point buy: 27 очков, каждая характеристика 8-15, стоимость нелинейная (14→7pts, 15→9pts). Возвращает ошибку если бюджет превышен или характеристика вне диапазона.
- `starting_gold()` → 100.

**Верифицируем:** Unit тесты. Fighter L1 CON 14 (+2) → 12 HP. Rogue L1 CON 12 (+1) → 9 HP. Point buy {15,14,13,12,10,8} = ровно 27 pts. Point buy {16,x,...} = rejected.

**Tasks:**

1. [HP Formula + Hit Dice](tasks/phase1-task1-hp-formula.md)
2. [Point Buy Validation](tasks/phase1-task2-point-buy.md)
3. [Starting Equipment + Gold](tasks/phase1-task3-starting-equipment.md)

## Phase 2: Creation API + Frontend Form

Бэкенд и фронтенд вместе — вертикальный срез.

- **API:** `create_player` принимает name, race, char_class, ability_scores, fighting_style (optional для Fighter). HP/AC/equipment/gold **вычисляются** сервером. Валидация: point buy budget, class ∈ {fighter, rogue}, fighting_style только для fighter.
- **Frontend CharacterForm:**
  - Убрать поля: level, hp, ac, gold, attacks.
  - Классы: только Fighter и Rogue.
  - Point buy UI: 6 характеристик с +/− кнопками, отображение оставшихся очков и модификатора.
  - Fighting Style selector (появляется при выборе Fighter): Defense, Dueling, Great Weapon Fighting.
  - Preview: показать вычисленные HP и AC до сабмита (клиентский расчёт или preview endpoint).
  - Стартовое снаряжение показать текстом ("Starting equipment: Chain Mail, Longsword, Shield").

**Верифицируем:** E2E: создать Fighter с point buy → персонаж с правильными HP/AC/equipment/gold. Создать Rogue → leather, rapier, sneak attack dice. Попытка отправить невалидный point buy → ошибка.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Content Fixes + Polish

Контентные правки и интеграционная проверка.

- Guard monster template (`content/catalogs/monsters/guard.yaml`) — стражник со статами стражника (hp 11, ac 16 chain mail + shield, spear/sword).
- Kingdom Patrol squad: `members: [guard, guard, guard]` вместо bandit.
- Bandit template оставить (банды разбойников используют его корректно).
- Прочие мелкие контентные фиксы по результатам ревью.
- Integration тесты: материализация Kingdom Patrol → стражники с правильными статами.

**Верифицируем:** Integration тесты. Kingdom Patrol спавнит guard, не bandit. Guard имеет chain mail + shield (AC 18). E2E: полный flow создания персонажа → бой со стражниками.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **Расовые бонусы к характеристикам отложены.** Раса — косметический выбор (пока). D&D 5.5e отменил фиксированные расовые бонусы, можно добавить как optional rule позже.
- **Level всегда 1.** Level up — отдельная фича. Убираем выбор уровня из формы.
- **Point buy, не standard array.** Больше гибкости, стандартный D&D 5e подход. 27 очков, диапазон 8-15.
- **Стартовое снаряжение фиксировано по классу.** Без выбора (упрощение). Fighter: chain mail + longsword + shield. Rogue: leather + rapier + shortbow + dagger.
- **Guard — отдельный template.** Bandit остаётся для банд, guard для патрулей.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
