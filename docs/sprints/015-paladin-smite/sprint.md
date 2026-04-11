# Sprint 015 — Paladin & Divine Smite

**Goal:** Paladin class с Divine Smite, spell slots как reusable resource system, multi-damage weapons и breakdown в UI.

**Started:** 2026-04-11

## Context

Spell slots — Level 2c из brainstorm (последний неготовый блок перед заклинаниями). Paladin — идеальный первый потребитель: Divine Smite = "потратить slot → добавить radiant damage к атаке". Это валидирует архитектуру ресурсов через реальный use case. Попутно: magic weapons с несколькими типами урона (flaming sword = slashing + fire) и красивый multi-damage breakdown в UI.

ResourcePool уже существует как структура (`core/resource.py`), но ни один потребитель не подключен. DamageType enum (13 типов), DamageComponent, AttackResult с tuple[DamageResult] — всё готово на уровне данных. Нужно замкнуть цепочку: ресурсы тратятся → extra damage добавляется → UI показывает breakdown.

Следующий спринт (016) — tech sprint.

**Ссылки:** [brainstorm: граница кода и контента](../../brainstorms/ecs-and-content.md), [sprint 014](../014-faction-reputation/sprint.md), [roadmap](../../ROADMAP.md)

---

## Phase 1: Spell Slots as ResourcePool ✓

ResourcePool перестаёт быть мёртвым кодом. Spell slots создаются, тратятся, восстанавливаются при Long Rest. Second Wind (Fighter) уже подключен к ResourcePool — добавляем rest actions для recovery. Action provider не показывает действие если pool пуст.

**Верифицируем:** Unit tests — создать creature с spell slots, потратить, проверить current_uses, rest → восстановились. Second Wind тратит pool. Action provider не показывает действие если pool пуст.

**Tasks:**

1. [Long Rest & Short Rest Actions](tasks/phase1-task1-rest-actions.md)
2. [Spell Slot Pool Infrastructure](tasks/phase1-task2-spell-slot-pools.md)

## Phase 2: Paladin Class Foundation ✓

`PaladinFeatures` в class_features, proficiency (all armor, shields, simple+martial weapons), Lay on Hands (heal, pool = 5×level, action cost), Divine Sense (bonus action, detect nearby creature types). Paladin в character creation (point buy, starting equipment). YAML контент: Paladin NPC в Sword Vale.

**Верифицируем:** Unit tests — proficiency, Lay on Hands heal + pool depletion, Divine Sense returns info. Integration — создать Paladin через API, проверить starting equipment и HP.

**Tasks:**

1. [Paladin Class Infrastructure](tasks/phase2-task1-paladin-class-infra.md)
2. [Lay on Hands Action](tasks/phase2-task2-lay-on-hands.md)
~~3. [Divine Sense Action](tasks/phase2-task3-divine-sense.md)~~ — deferred, see backlog `divine-sense`

## Phase 3: Divine Smite ✓

Smite как модификатор атаки: при попадании — потратить spell slot → +2d8 radiant (slot 1). Реализуем для level 1 Paladin — один уровень слотов. Масштабирование по уровням слотов (slot 2 → +3d8) и бонус vs undead/fiend — в бэклоге (`divine-smite-scaling`), когда будет система уровней. `extra_damage` в `resolve_attack` уже принимает дополнительные компоненты — smite добавляет `DamageComponent(dice="2d8", type=DamageType.RADIANT)`.

**Верифицируем:** Unit tests — smite добавляет radiant damage, тратит slot 1, нет слотов → smite недоступен. Frontend — damage log показывает "2d8 radiant (smite)" отдельной строкой.

**Design:** Smite is an optional `smite_slot_level` param on the attack action, not a separate ActionType. Brain declares intent when choosing attack; slot spent only on hit.

**Tasks:**

1. [Divine Smite Rules & Attack Param](tasks/phase3-task1-smite-rules.md)
2. [Divine Smite Combat Integration & Brain Support](tasks/phase3-task2-smite-combat-integration.md)

## Phase 4: Multi-Damage Weapons + UI Breakdown

Оружие с несколькими типами урона (flaming longsword = 1d8 slashing + 1d6 fire). WeaponDef уже поддерживает `tuple[DamageComponent, ...]` — контент + вся цепочка (resolve_attack → perception → frontend) корректно рендерит 2-3 компонента. Frontend: damage breakdown card с иконкой/цветом типа, dice roll details. Каталог: 2-3 magic weapons.

**Верифицируем:** Unit tests — weapon с 2 damage components корректно резолвится. E2E — атака flaming sword показывает "1d8 slashing + 1d6 fire" в логе с визуальным разделением.

**Tasks:**

1. [Multi-Damage Weapon Catalog & Backend Tests](tasks/phase4-task1-multi-damage-backend.md)
2. [UI Damage Type Breakdown Polish](tasks/phase4-task2-ui-damage-breakdown.md)

## Phase 5: Smite + Magic Weapon Combo + Polish

Полный combo: Paladin с flaming longsword + smite → 1d8 slashing + 1d6 fire + 2d8 radiant. Три типа урона, все красиво отображаются. RuleBrain для Paladin: когда смайтить (crit → always, low HP → yes). Frontend: spell slot display на Character panel. Integration test: полный бой Paladin vs enemy.

**Верифицируем:** Integration test — Paladin атакует magic weapon + smite, лог содержит 3 damage components. E2E — spell slots видны, тратятся, бой работает end-to-end.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 4 tasks generated. Ready to start task 1.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
