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

## Phase 4: Multi-Damage Weapons + UI Breakdown ✓

Оружие с несколькими типами урона (flaming longsword = 1d8 slashing + 1d6 fire). WeaponDef уже поддерживает `tuple[DamageComponent, ...]` — контент + вся цепочка (resolve_attack → perception → frontend) корректно рендерит 2-3 компонента. Frontend: damage breakdown card с иконкой/цветом типа, dice roll details. Каталог: 2-3 magic weapons.

**Верифицируем:** Unit tests — weapon с 2 damage components корректно резолвится. E2E — атака flaming sword показывает "1d8 slashing + 1d6 fire" в логе с визуальным разделением.

**Tasks:**

1. [Multi-Damage Weapon Catalog & Backend Tests](tasks/phase4-task1-multi-damage-backend.md)
2. [UI Damage Type Breakdown Polish](tasks/phase4-task2-ui-damage-breakdown.md)

## Phase 5: Smite + Magic Weapon Combo + Polish ✓

Полный combo: Paladin с flaming longsword + smite → 1d8 slashing + 1d6 fire + 2d8 radiant. Три типа урона, все красиво отображаются. RuleBrain для Paladin: когда смайтить (crit → always, low HP → yes). Frontend: spell slot display на Character panel. Integration test: полный бой Paladin vs enemy.

**Верифицируем:** Integration test — Paladin атакует magic weapon + smite, лог содержит 3 damage components. E2E — spell slots видны, тратятся, бой работает end-to-end.

**Tasks:**

1. [Resource Pools in Awareness + Spell Slot UI](tasks/phase5-task1-spell-slot-ui.md)
2. [Paladin Combo Integration Test](tasks/phase5-task2-paladin-combo-integration.md)

## Phase 6: Action Target Scope ✓

Явная типизация целей для всех экшенов. Сейчас `ActionDef.targeted: bool` — бинарный флаг, фронтенд всех называет `enemies` и показывает один список `nearby` (без self). Это ломает Lay on Hands (нельзя выбрать себя) и не масштабируется на будущие заклинания.

Две ортогональные оси: **TargetMode** (как выбираем цель) × **TargetScope** (кого можно выбрать).

**TargetMode enum:**
- `NONE` — нет цели-существа (equip, say, wait, buy/sell, end_turn)
- `SELF` — цель = кастер, неявно (dodge, dash, disengage, second_wind, flee, rest, bless)
- `SINGLE` — выбрать 1 существо (attack, lay_on_hands)
- `MULTI` — выбрать N существ (future: scorching ray, magic missile)
- `POINT` — клик на карту x,y (future: fireball)
- `DIRECTION` — выбрать направление (future: burning hands, lightning bolt)

**TargetScope enum** (только для SINGLE/MULTI):
- `HOSTILE` — враги
- `ALLY` — союзники + self
- `ANY` — все + self

**ActionDef changes:** `target_mode: TargetMode`, `target_scope: TargetScope`, `max_targets: int`. Property `targeted` = `mode not in (NONE, SELF)`. Поле `targeted: bool` удаляется.

**Маппинг текущих экшенов:**

| Action | Mode | Scope |
|---|---|---|
| Attack, Opportunity Attack | SINGLE | HOSTILE |
| Lay on Hands | SINGLE | ALLY |
| Dodge, Dash, Disengage, Flee | SELF | — |
| Second Wind, Long/Short Rest, Bless | SELF | — |
| Equip/Unequip (все), Say, Wait, Buy/Sell, Idle, End Turn, Skip, Use Item | NONE | — |
| Move, Move To | NONE | — (свой UI) |

**Backend:** validation.py проверяет scope (hostile target must be is_hostile, ally must be !is_hostile or self). Awareness builder — без изменений, `nearby` остаётся как есть.

**Frontend:** ActionInfo получает `target_mode` + `target_scope`. Роутинг по mode вместо `hasParam("target_id")`. Для ALLY/ANY — фронт добавляет "Себя" в список. Переменная `enemies` → `nearby`.

**Верифицируем:** Unit tests — validation отклоняет hostile target для ALLY scope и наоборот. E2E — Lay on Hands показывает "Себя" + союзников, Attack показывает только врагов.

**Tasks:**

1. [TargetMode/TargetScope Enums + Validation](tasks/phase6-task1-target-enums-validation.md)
2. [Frontend Target Scope Routing](tasks/phase6-task2-frontend-target-scope.md)

## Phase 7: Smite UI + Level 1 Spell Slot

Паладин level 1 не имеет spell slots (по RAW они появляются на level 2). Пока нет системы левелинга — даём 1 spell slot на level 1 как временное решение, чтобы smite был тестируемым. Переделаем когда появится левелинг.

Фронтенд не имеет UI для smite — `smite_slot_level` есть как опциональный параметр ATTACK, но нет способа его задать. Добавляем выбор при атаке: после выбора цели, если есть spell slots, показываем варианты "Attack" / "Attack + Smite (slot 1)" / "Attack + Smite (slot 2)".

**Backend:**
- `build_class_resource_pools`: Paladin level 1 получает 1 spell slot (level 1). Временно, до системы левелинга.
- Остальной бэкенд (validate_smite, build_smite_damage, combat_manager, RuleBrain) уже полностью рабочий — менять не надо.

**Frontend:**
- При клике Attack на цель — если у игрока есть spell slots, показать вложенный выбор: "Attack" (без smite) и "Attack + Smite (slot N)" для каждого доступного уровня слотов. Если слотов нет — обычная атака без промежуточного шага.
- Отправка: `sendAction("attack", { target_id, smite_slot_level })` или без smite_slot_level.

**Верифицируем:** E2E — Paladin level 1 имеет spell slot, при атаке видит опцию Smite, атака со smite добавляет radiant damage и тратит слот. Без smite — обычная атака.

**Tasks:**

1. [Level 1 Paladin Spell Slot (Temporary)](tasks/phase7-task1-level1-spell-slot.md)
2. [Smite Choice UI in Attack Flow](tasks/phase7-task2-smite-choice-ui.md)

---

## Status

**Current:** Phase 7 PLANNED (2026-04-11). Phase 6 complete.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
