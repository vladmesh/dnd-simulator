# Sprint 004 — Living World: Squads & Encounters

**Goal:** Мир, который живёт сам. Абстрактные группы (squads) перемещаются по графу локаций, сталкиваются друг с другом и с active characters. Encounter tables — свойство зоны, срабатывают на любого путешественника. Фракции определяют кто враг, кто союзник.

**Started:** 2026-03-25

> **Pivot note (2026-03-25):** Спринт был переписан в процессе. Исходный план (player-centric random encounters) заменён на living world архитектуру после обсуждения [living-world.md](../../brainstorms/living-world.md) и обновления [VISION.md](../../VISION.md). Задачи Phase 1 (tasks 1-2) выполнены до пивота — MonsterTemplate и spawn engine переиспользуются в новом дизайне. Task 3 (hostile AI) не начата, переносится в Phase 2 нового плана.

## Context

Sprint 001 дал боевую систему, Sprint 003 — инвентарь и торговлю. Но мир завязан на игрока: ничего не происходит без его присутствия. Нужна инфраструктура живого мира — фракции, группы, зоны опасности, которые работают одинаково для игрока, NPC и абстрактных сквадов.

Две ключевых абстракции:

1. **Active Character** — "наблюдатель", при котором мир рендерится детально. Обычно игрок, но может быть LLM/Rule NPC с пробуждённым мозгом. Квантовые энкаунтеры коллапсируют, сквады материализуются, NPC активируются.

2. **Squad** — абстрактная группа (1-15 членов) со своими механиками: перемещение, абстрактный бой, рост/потери. Существует как запись с полями, пока не встретится с active character → материализуется в конкретных Creature.

Отдельно: **faction_id** на Creature — принадлежность к стороне (kingdom, orcs, bandits, wildlife). Определяет союзников/врагов. Два стражника из разных патрулей — союзники (одна фракция). Не путать со squad_id — это разные вещи. Глубокая проработка фракций (репутация, дипломатия, переходы) — отдельный спринт.

**В скоупе:**
- Faction relations: `faction_id` на Creature/Squad, матрица отношений на PoliticsLayer
- Squad model: абстрактная группа с movement, strength, behavior
- Encounter tables как свойство зоны — срабатывают на любого active character и на squads
- Hostile AI: faction-aware, враг по faction relations → атака
- Abstract combat: squad vs encounter, squad vs squad (формулы)
- Materialization: squad при контакте с active character → конкретные Creature
- EcologyLayer: tick-based движение сквадов по графу
- YAML контент: фракции, 3-4 сквада, 5-8 monster templates для Sword Vale

**Вне скоупа:**
- Фракционная репутация, дипломатия, переход из фракции в фракцию
- Loot tables и автодроп (следующий спринт)
- Lair monsters (следующий спринт)
- Respawn сквадов, recruitment из поселений
- CR-балансировка
- Travel through intermediate locations (пока travel мгновенный)
- Settlement-as-squad unification

**Ссылки:** [VISION.md](../../VISION.md), [living-world.md](../../brainstorms/living-world.md), [ROADMAP.md](../../ROADMAP.md), [Sprint 003](../003-inventory-trading/sprint.md)

---

## Completed before pivot

Tasks 1-2 из оригинального Phase 1. Код переиспользуется:
- **MonsterTemplate** + YAML loading → используется для member_templates сквадов и encounter spawning
- **Spawn engine** (`_check_encounters`, `temporary` flag, death cleanup) → обобщается на всех active characters в Phase 2
- **EncounterEntry/EncounterTable** → остаётся, encounter tables — свойство зоны

---

## Phase 1: Data Foundation ✓

`faction_id` на Creature и MonsterTemplate. Матрица отношений фракций на PoliticsLayer с запросом `get_relation()`. `Squad` model (frozen dataclass): id, faction_id, group_type, behavior, route/territory, strength, member_templates. `squads.yaml` в контенте мира. `squad_id` на Creature (заполняется при материализации).

**Верификация:** faction relation query работает. Squad парсится из YAML. Creature с faction_id корректно определяет враг/союзник. `make check` зелёный.

**Tasks:**

1. [Factions — faction_id + Faction Relations](tasks/phase1-task3-factions.md)
2. [Squad Model + squads.yaml](tasks/phase1-task4-squad-model.md)

## Phase 2: Generalize Encounters + Hostile AI

Encounter table rolls для любого active character (не только PlayerCharacter). Encounter table rolls для сквадов (абстрактный бой: squad strength vs encounter strength по формуле). Hostile AI в RuleBrain: faction-aware, враг по faction relations → атака. Abstract combat formula.

**Верификация:** LLM NPC приходит в опасную локацию → монстры спавнятся → бой. Сквад стражников входит в болото → абстрактный бой, сквад теряет strength. Hostile creature видит врага по faction → атакует. `make check` зелёный.

**Tasks:**

1. [Generalize Encounter Triggers](tasks/phase2-task1-generalize-encounters.md)
2. [Faction-Aware Hostile AI](tasks/phase2-task2-hostile-ai.md)
3. [Abstract Squad Combat Formula](tasks/phase2-task3-abstract-combat.md)

## Phase 3: Squad Movement + Materialization

EcologyLayer (новый слой между Settlements и Entities): tick-based движение сквадов по графу локаций. Squad + active character в одной локации → материализация (MonsterTemplate.spawn для каждого члена, squad_id на Creature). Squad + hostile squad → абстрактный бой. Dematerialization при уходе active character. YAML контент: 3-4 сквада для Sword Vale (патруль стражников, банда бандитов, стая волков, орочий рейд).

**Верификация:** сквады двигаются по маршрутам. Игрок приходит в локацию со сквадом → сквад материализуется. Два враждебных сквада в одной локации → абстрактный бой, проигравший теряет strength. `make check` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Frontend + E2E

Отображение сквад-событий в event log ("Орочий патруль прошёл через Лесную дорогу", "Стража разбила стаю волков на болоте"). Материализованные сквады в nearby panel. E2E прогон всех сценариев.

**Верификация:** в браузере видно перемещение сквадов, бои, материализацию. E2E зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Sprint replanned. Phase 1 ready for task generation.

## Decisions

- **Pivot (2026-03-25):** Player-centric encounters → living world. Encounter tables остаются, но как свойство зоны для всех, не только для игрока.
- **Squad ≠ alliance:** `squad_id` — принадлежность к абстрактной группе (механика). `faction_id` — принадлежность к стороне (alliance/hostility). Не смешивать.
- **Village ≠ squad:** Поселения не моделируются как сквады. NPC поселений — именованные Entity с расписаниями. `faction_id` определяет их сторону.

## Deferred

- Loot tables + автодроп — отдельный спринт
- Lair monsters — отдельный спринт
- Фракционная репутация, дипломатия — отдельный спринт
- Travel through intermediate locations
- Squad respawn / recruitment

## Results

_(заполняется в конце спринта)_
