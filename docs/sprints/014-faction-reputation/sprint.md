# Sprint 014 — Faction Relations & Reputation

**Goal:** Combat sides from faction relations, personal reputation per-faction with auto-hostility thresholds, friendly OA fix.

**Started:** 2026-04-02

## Context

Баг: opportunity attacks срабатывают между союзниками (гоблины бьют друг друга). Корень — `reactions.py` не знает о сторонах в бою. Шире: нет явной структуры "сторона в бою", targeting/OA/brain каждый решает по-своему (ad-hoc `_is_faction_friendly`).

Заодно закладываем reputation system: числовая репутация per-creature per-faction, пороги FRIENDLY/NEUTRAL/HOSTILE, omniscient reputation changes от kills. Архитектурно: `faction_id` = происхождение (не меняется), `reputation` dict = текущие отношения (sparse, fallback на faction-to-faction defaults).

Ключевое решение: `effective_relation(A, B)` — единая функция, personal reputation если есть, иначе faction relation fallback. Все системы (combat sides, OA, targeting, awareness) используют её.

**Ссылки:** [sprint 012 — reactions](../012-reactions-oa/sprint.md), [backlog](../../BACKLOG.md), [vision](../../VISION.md)

---

## Phase 0: Refactor — Prep for Faction Work ✓

Audit-driven cleanup of files sprint 014 will heavily modify. Reduces friction and prevents debt growth.

- `layers/politics/layer.py` (615 lines) — extract diplomacy/warfare/economy sub-modules. Sprint adds faction relation logic here.
- `layers/entities/combat_manager.py` (604 lines) — split initiative/damage/state. Sprint adds CombatSides here.
- `core/brain.py:165` `_choose_combat_action` (131-line if/elif) — decompose into per-action helpers or decision table. Sprint rewrites targeting logic.
- `layers/entities/perception.py` — replace 54x `.get()` silent defaults with `data["key"]` fail-fast. Sprint adds reputation events.
- `rules/proficiency.py:33-34` + `perception.py:29-31` — hardcoded weapon name strings → catalog/enum reference.
- `service/commands_politics.py` — add unit tests (0 test references). Sprint exercises politics commands heavily.

**Верифицируем:** `make check` green. No behavior changes — pure refactor + tests.

**Tasks:**

1. [Extract Politics Layer Submodules](tasks/phase0-task1-politics-extraction.md)
2. [Split Combat Manager](tasks/phase0-task2-combat-manager-split.md)
3. [Decompose Brain Combat Decision Tree](tasks/phase0-task3-brain-decompose.md)
4. [Small Fixes — Perception, Proficiency, Commands Tests](tasks/phase0-task4-small-fixes.md)

## Phase 1: Combat Sides + OA Fix

Фиксим баг с friendly OA, используя существующие faction_id + FactionRelation. Без репутации.

- `CombatSides` — при старте боя строим стороны из faction relations. Граф: FRIENDLY → merge в одну сторону, HOSTILE → разные стороны. "Друг обоих" → приоритет same faction, иначе higher relation number.
- `find_oa_triggers` / `can_opportunity_attack` фильтруют по сторонам — союзников не бьют.
- RuleBrain targeting через sides (формализация `_is_faction_friendly`).
- Combat end condition через sides (замена `_has_opposing_factions`).

**Верифицируем:** Unit tests — гоблины не бьют друг друга OA, mixed factions (3+ фракции) разрешаются корректно, "друг обоих" встаёт на правильную сторону.

**Tasks:**

1. [CombatSides Model + Build Algorithm](tasks/phase1-task1-combat-sides-model.md)
2. [Wire Sides into Combat — OA Fix + Combat End](tasks/phase1-task2-wire-sides-combat.md)
3. [Sides-Based Targeting + Awareness](tasks/phase1-task3-sides-targeting-awareness.md)

## Phase 2: Personal Reputation + effective_relation

Числовая репутация подменяет raw faction lookups.

- `reputation: dict[str, int]` на Creature (sparse dict, дефолт вычисляется из faction relations).
- `effective_relation(A, B)` — pure function: personal rep если есть, иначе faction-to-faction fallback. Пороги: 75+ FRIENDLY, 25-74 NEUTRAL, <25 HOSTILE.
- CombatSides переключается на `effective_relation` вместо raw faction relations.
- Изгнанник-паттерн: `faction_id` не меняется при падении репутации с своей фракцией. Faction_id = происхождение, reputation = текущие отношения.

**Верифицируем:** Unit tests — creature с personal override обрабатывается иначе чем faction default. Creature с низкой репутацией со своей фракцией = HOSTILE к бывшим союзникам. CombatSides корректно строятся из effective_relation.

**Tasks:**

1. [effective_relation Pure Function + Reputation Field](tasks/phase2-task1-effective-relation.md)
2. [CombatSides Uses effective_relation](tasks/phase2-task2-combat-sides-effective-relation.md)
3. [Awareness + Serialization for Reputation](tasks/phase2-task3-awareness-serialization.md)

## Phase 3: Reputation Dynamics + Auto-hostility

Репутация начинает двигаться от действий.

- Kill → reputation drop (omniscient). Множитель от репутации жертвы со своей фракцией: `delta = base_delta * (victim_rep_with_own_faction / 100)`. Изгнанника убил → ~0 падения. Вождя → полное.
- Атака NPC вне боя → auto-hostility: цель + союзники (по effective_relation) vs атакующий + союзники. Инициация боя с корректными CombatSides.
- Awareness показывает faction/reputation info для brain decisions.
- Frontend: изменения репутации в логе событий.

**Верифицируем:** Integration tests — убийство гоблина роняет репутацию с гоблинами, повторные убийства двигают порог в HOSTILE. Атака мирного NPC → бой с правильными сторонами. E2E: лог показывает reputation change.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 1 complete (2026-04-10). All 3 tasks done. Ready for phase 2.

## Decisions

- **Reputation-first модель.** `faction_id` = происхождение/идентичность, `reputation` dict = текущие отношения. Всё поведение через `effective_relation()`.
- **Sparse reputation.** Только фракции, с которыми creature лично взаимодействовал. У 99% гоблинов dict пустой — всё из faction defaults.
- **Omniscient reputation.** Фракция мгновенно знает о действиях. Witness-based — future scope.
- **Стороны заморожены на бой.** Смена стороны в бою — out of scope.
- **Пороги: 75/25.** 75+ FRIENDLY, 25-74 NEUTRAL, <25 HOSTILE. Числа тюнятся, но структура фиксирована.
- **"Друг обоих" → same faction priority, потом выше число.** Если FRIENDLY к обеим сторонам: сначала проверяем same faction_id, потом сравниваем reputation числа.
- **Изгнанник не теряет faction_id.** Низкая репутация со своей фракцией ≠ смена фракции. Интересный контент: NPC-изгнанник, которого бьют свои.

## Deferred

- Witness-based reputation (свидетели, побег, доклад)
- Typed crimes (murder, theft, assault) как события
- Settlement-level consequences (розыск, bounty)
- Friendly fire в бою (атака союзника)
- Смена стороны в бою
- Reputation decay / восстановление со временем

## Results

_(заполняется в конце спринта)_
