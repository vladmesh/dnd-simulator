# Sprint 004 — Monster Encounters

**Goal:** Рандомные энкаунтеры с монстрами в опасных локациях, логова с persistent существами, автолут.

**Started:** 2026-03-25

## Context

Sprint 001 дал боевую систему и предметы, Sprint 003 — инвентарь и торговлю. Но в мире нечего убивать — нет враждебных существ, которые появляются органически. Этот спринт закрывает core gameplay loop: исследование → встреча с монстрами → бой → лут → торговля. Разблокирует квестовую систему (kill quests нужны монстры) и делает боевую систему востребованной в обычной игре.

Два типа монстров:
- **Random encounters** — таблицы встреч на локациях, при входе игрока бросок на шанс, спавн temporary creatures из шаблонов. После смерти исчезают.
- **Lair monsters** — полноценные Creature из YAML с hostile-флагом. Живут в конкретной локации, при смерти исчезают навсегда.

Всё определяется контентом: статблоки, таблицы встреч, уровень опасности, логова — YAML, не код.

**В скоупе:**
- MonsterTemplate (frozen dataclass из YAML): HP, AC, attacks, CR, loot table
- Encounter tables на локациях (chance, monster refs, count)
- Spawn engine: вход игрока → бросок → temporary Creatures на EntitiesLayer
- Hostile AI в RuleBrain: враждебные существа инициируют бой
- Cleanup temporary creatures после смерти
- Loot tables: предметы + золото, автодроп в инвентарь убийцы
- Lair monsters: persistent Creature, hostile, permanent death
- YAML-контент: 5-8 статблоков, опасные локации + логово в Sword Vale
- Frontend: энкаунтеры в event log, монстры в nearby panel

**Вне скоупа:**
- Scripted/triggered encounters (квестовая система)
- Wandering monsters (autonomous NPC ticks)
- CR-балансировка по размеру партии
- Corpse entity + loot action (сейчас автодроп)
- AoE, damage types, resistance
- Respawn таблиц (кулдаун есть, но без восстановления убитых lair monsters)

**Ссылки:** [ROADMAP.md](../../ROADMAP.md), [BACKLOG.md](../../BACKLOG.md), [Sprint 003](../003-inventory-trading/sprint.md), [ecs-and-content.md](../../brainstorms/ecs-and-content.md)

---

## Phase 1: Spawn Foundation

MonsterTemplate (frozen dataclass из YAML), таблицы встреч на локациях, spawn engine (вход игрока → бросок → спавн temporary Creatures). Hostile AI в RuleBrain — враждебные существа инициируют бой. Удаление temporary creatures после смерти.

**Верификация:** зайти в опасную локацию → монстры появляются → бой начинается автоматически → убитые монстры исчезают. `make test-unit` зелёный.

**Tasks:**

1. [MonsterTemplate + EncounterTable Models & YAML Loading](tasks/phase1-task1-monster-template-model.md)
2. [Spawn Engine + Temporary Creature Lifecycle](tasks/phase1-task2-spawn-engine.md)
3. [Hostile AI — RuleBrain Initiates Combat](tasks/phase1-task3-hostile-ai.md)

## Phase 2: Loot + Lairs

Лут-таблицы на темплейтах (предметы + золото), автодроп в инвентарь убийцы. Lair monsters — обычные Creature в YAML с hostile-флагом, при смерти исчезают навсегда. YAML-контент: 5-8 статблоков монстров, опасные локации + логово в Sword Vale.

**Верификация:** убил монстра → золото/предметы в инвентаре. Убил lair monster → он больше не появляется при возвращении. `make test-unit` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Frontend + E2E

Отображение энкаунтеров в event log, монстры в nearby panel, encounter-специфичные сообщения. E2E прогон всех сценариев.

**Верификация:** в браузере видно появление монстров, бой, лут. E2E зелёный.

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
