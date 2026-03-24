# Sprint 001 — Class Mechanics: Fighter & Rogue L1

**Goal:** Fighter и Rogue первого уровня полностью играбельны — proficiency, equipment (armor/shield), Fighting Styles, Second Wind, Sneak Attack, Cunning Action.

**Started:** 2026-03-24

## Context

Классовые механики — фундамент играбельности. Без них все персонажи одинаковы: одинаковые атаки, одинаковый AC, одинаковые действия. Fighter и Rogue — два самых простых класса, покрывающих archetype "воин" и "ловкач". Реализация L1 разблокирует паттерны для остальных классов.

**Зависимости которые разблокирует:**
- Proficiency system → все будущие классы
- Armor/shield → AC разнообразие, loot, торговля
- ResourceTracker → spell slots, ki, rage (будущие классы)
- ClassFeatures (composition) → все классовые механики без наследования, мультикласс из коробки
- Equipment slots → расширение инвентаря

**Ссылки:** [ecs-and-content.md](../brainstorms/ecs-and-content.md) Level 2, [VISION.md](../VISION.md) "Classic mode"

## Plan

### Phase 1: Infrastructure

1. [x] **Proficiency bonus** — `proficiency_bonus(level) -> int` в `rules/`. +2 на L1. Добавить в `attack_modifiers()` если персонаж proficient с оружием. `engine`
2. [x] **Weapon/armor proficiency per class** — определить для Fighter (all armor, shields, simple+martial) и Rogue (light armor, simple + rapier/shortsword/hand crossbow/longsword). Данные, не код — frozen dict. `engine`
3. [x] **Equipment slots: armor + shield** — `equipped_armor: Item | None`, `equipped_shield: Item | None` на Creature. ItemType.ARMOR, ItemType.SHIELD. Equip/unequip handlers. `engine`
4. [x] **AC from equipment** — `effective_ac()` считает: armor base + DEX mod (capped по типу брони) + shield bonus + modifiers. `engine`
5. [x] **ResourceTracker** — `ResourcePool(id, max, current, reset_on)` на Creature. Reset triggers: SHORT_REST, LONG_REST. `engine`
6. [x] **ClassFeatures** — композиция вместо наследования. `core/class_features.py`: `FighterFeatures`, `RogueFeatures`. `list[ClassFeatures]` на Character (мультикласс из коробки). content_loader парсит из YAML. `engine`

### Phase 2: Fighter L1

7. [x] **Fighting Style** — Defense (+1 AC в броне), Dueling (+2 dmg одноручное). Через modifier pipeline + class_features. Great Weapon Fighting → бэклог (нужен is_two_handed + dice reroll). `class-feature`
8. [x] **Second Wind** — bonus action, heal 1d10 + fighter level, 1 use / short rest. Использует ResourceTracker. Новый ActionType SECOND_WIND. `class-feature`

### Phase 3: Rogue L1

9. [x] **Sneak Attack** — sneak_attack_dice на RogueFeatures. +Nd6 при advantage или союзник в 5ft. Только finesse/ranged. Раз в ход. Hook в resolve_attack(). `class-feature`
10. [x] **Cunning Action** — Dash, Disengage как bonus action. Проверка isinstance RogueFeatures. ActionProvider для Rogue. `class-feature`

### Phase 3.5: Generic Attack Perception

15. [x] **Component-based attack logging** — заменить ad-hoc плоские поля в event data на структурированные списки компонентов. Perception итерирует их обобщённо — ноль знаний о конкретных фичах. `engine` `refactor`
16. [x] **E2E Sneak Attack через Playwright** — тестовый мир `sneak_test.yaml`, рог + рапира + stunned враг. SA виден в UI-журнале боя. `e2e`

### Phase 4: Content + Quality

17. [ ] **Armor/weapon items в YAML** — leather armor, chain mail, shield, rapier, shortsword, longbow для village.yaml. Equip на существующих NPC. `content`
18. [ ] **Fighter и Rogue NPC** — хотя бы один Fighter и один Rogue в village с полной экипировкой и class features. `content`
19. [ ] **Tests** — unit tests для каждой новой механики. ClassFeatures, Fighting Styles, Second Wind, Sneak Attack, Cunning Action. `test`
20. [ ] **Audit + cleanup** — /audit после всех изменений, правки по результатам. `quality`

## Status

**Current:** Phase 3.5 complete. Phase 4 next.

Phase 1 (6/6) — done. E2E found and fixed 2 bugs:
- AC serialization: API returned raw `creature.ac` instead of `effective_ac()`
- Heavy armor negative DEX: `min(dex_mod, 0)` penalized AC, now ignored for heavy armor

Phase 2 (2/2) — done. E2E found and fixed 2 bugs:
- ClassFeatureActionProvider checked FighterFeatures instead of CharClass → Second Wind not offered to frontend-created Fighters
- Frontend missing `second_wind` action label and SIMPLE_ACTIONS entry

Phase 3 (2/2) — done. E2E passed, 0 bugs:
- Sneak Attack: elf rogue dealt 9 damage with rapier (1d8 max=8), proving 1d6 SA dice triggered via ally-adjacent condition
- Cunning Action: Dash consumed bonus action (not standard), player retained Attack action
- Disengage button appears in combat, disappears when bonus spent
- Unarmed attacks correctly do NOT trigger SA (no finesse weapon)

Phase 3.5 (2/2) — done. Рефакторинг attack perception + E2E проверка.

**#15 — Component-based attack logging.** Проблема: каждая новая боевая фича (Bless, SA, Dueling, будущий Smite/Hex) требовала ручных правок и в `combat_manager` log_data, и в `_perceive_attack`. Решение — обобщённый контракт данных:

Новые типы:
- `RollComponent(source, value, dice)` — подписанная компонента броска/урона (`core/modifiers.py`)
- `ExtraDamage(dice, type, source)` — именованный доп. урон, заменяет `tuple[str, DamageType]` (`rules/combat.py`)
- `DamageResult` расширен полями `source`, `dice` для трассировки

Изменения в pipeline:
- `AttackModifiers` получил `roll_components` и `damage_components` — breakdown бонусов атаки и урона
- `attack_modifiers()` строит компоненты: ability, proficiency, weapon_magic, blessed, dueling и т.д.
- `combat_manager.resolve_attack()` формирует `log_data` со структурированными `attack_roll.components[]` и `damage_components[]`

Perception стала полностью generic:
- `_format_roll(atk_roll, ac)` — итерирует components, строит `[adv d20(14)+6=20 vs AC 13]`
- `_format_damage(damage, components, critical)` — итерирует damage_components, строит `10 damage (1d8 piercing + 1d6 sneak_attack + +2 dueling)`
- Ни одна из функций не знает о конкретных фичах — всё определяется source/dice полями

Файлы: `core/modifiers.py`, `rules/combat.py`, `rules/modifiers.py`, `layers/entities/combat_manager.py`, `layers/entities/perception.py`, `tests/unit/test_combat.py`, `tests/unit/test_perception.py`. Все 816 тестов проходят.

**#16 — E2E Sneak Attack через Playwright.** Создан тестовый мир `content/worlds/sneak_test.yaml` (1 локация, 1 dummy NPC). Сценарий: рог (DEX 18) + рапира (finesse) + stunned враг → advantage → SA. Результат в UI-журнале:
```
You attack human, stunned (rapier strike) [adv d20(9)+6=15 vs AC 9], 10 damage (1d8 piercing + 1d6 sneak_attack)
```
Debug logs (`DEBUG=1`) подтвердили: `sneak_attack` event с `reason: "advantage"`, `dice: "1d6"`. Первая атака fists корректно НЕ дала SA (не finesse).

## Decisions

- **Proficiency bonus — не modifier pipeline**, а flat addition к base_mod в `attack_modifiers()`. Проще и корректно для D&D 5e.
- **AC backwards compat** — `max(creature.ac, 10 + dex_mod)` для unarmored Characters. NPC с хардкод ac сохраняют значения пока не получат броню.
- **Отдельные action types для armor/shield equip** — не обобщаем weapon equip, чтобы не ломать фронтенд.
- **ClassFeatures — композиция, не наследование.** `list[ClassFeatures]` на Character. Мультикласс из коробки. Избегаем diamond problem с PlayerCharacter/Npc.
- **Great Weapon Fighting → deferred** — нужен `is_two_handed` на WeaponDef + dice reroll в roller.

## Deferred

- **Great Weapon Fighting** — нужен `is_two_handed` флаг на WeaponDef + dice reroll механика в roller. Отдельная задача.
- **Expertise (Rogue)** — требует системы skill checks, которой нет. Отдельный спринт.
- **Thieves' Cant** — чистый флейвор, нет механического эффекта.
- **Saving throw proficiencies** — Fighter STR+CON, Rogue DEX+INT. Требует системы saving throws. Отдельный спринт.
- **Hide action** — часть Cunning Action, но реализация Hide требует Stealth vs Perception (skill checks). В первой версии Cunning Action = только Dash + Disengage.
- **SA ally-adjacency faction check** — сейчас любое живое существо в 5ft от цели считается "союзником" для SA. Нужна система фракций/hostility чтобы отличать реального союзника от враждебного NPC.

## Results

_(заполняется в конце спринта)_
