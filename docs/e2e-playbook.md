# E2E Playbook

Сценарии для регрессионного тестирования через Playwright. Каждый сценарий — что делаем, что ожидаем. Обновляется при добавлении новых фич.

**Последнее обновление:** 2026-04-10

---

## 1. Session Setup

### 1.1 Landing page — Player/DM split
- Открыть `/`
- **Ожидание:** две карточки: "Play" (→ /play) и "Dungeon Master" (→ /master)

### 1.2 Quick start — pick existing world
- Нажать "Play" → выбрать мир (Sword Vale) → "New Session" → создать персонажа (fighter, human, point buy STR 15 CON 14, Defense style)
- **Ожидание:** редирект на `/play/:sessionId`, WebSocket подключён, первый turn в логе

### 1.4 Character creation — point buy
- На экране создания: проверить что есть +/- кнопки для ability scores, счётчик оставшихся очков (27), preview HP/AC/Gold, текст Starting Equipment
- **Ожидание:** point buy корректный (15→9pts, остаток обновляется), + disabled при 15, - disabled при 8. Preview: Fighter L1 CON 14 → HP 12, Chain Mail + Shield + Defense → AC 19, Gold > 0 (значение из starting_equipment)

### 1.5 Character creation — class-specific UI
- Выбрать Fighter → появляется Fighting Style selector (Defense/Dueling/GWF). Выбрать Rogue → selector исчезает. Starting equipment меняется.
- **Ожидание:** Fighter: Chain Mail, Longsword, Shield (или Greatsword для GWF). Rogue: Leather Armor, Rapier, Shortbow, Dagger

### 1.3 Language toggle
- На любом экране переключить язык EN→RU
- **Ожидание:** лейблы меняются на русские

---

## 2. Peaceful Mode

### 2.1 Perception — nearby entities
- В мирном режиме (Sword Vale) увидеть список NPC в Perception Panel
- **Ожидание:** имена NPC видны, кнопки Talk/Attack/Inspect

### 2.2 Talk to NPC (rule-based)
- Нажать Talk на rule-based NPC, ввести текст, отправить
- **Ожидание:** в логе появляется реплика NPC (entity_say)

### 2.3 Wait and time advance
- Нажать Wait → время сдвигается на 1 час
- **Ожидание:** время обновилось в Location Panel, возможно weather_changed в логе

### 2.4 Move between locations
- Нажать Move toward соседнюю локацию (если есть paths)
- **Ожидание:** location_id меняется, Location Panel обновляется

---

## 3. Combat

### 3.1 Initiate combat
- Атаковать NPC → бой начинается
- **Ожидание:** combat_started в логе, sidebar переключается на CombatPanel, round number виден

### 3.2 Attack and damage
- В бою нажать Attack на врага
- **Ожидание:** entity_attack в логе с броском [d20+X=Y vs AC Z], damage, HP врага обновляется

### 3.3 End turn and NPC response
- Нажать End Turn
- **Ожидание:** NPC ходит, round_result в логе, новый turn приходит

### 3.4 Combat ends
- Убить врага (или несколько раундов)
- **Ожидание:** entity_died в логе, combat_ended, sidebar возвращается в peaceful

### 3.5 Level-up full cycle (Paladin L1 → L2)
- Мир `level_up_test`, создать Paladin L1 (например STR 15 / CON 14 / CHA 14), `start_location: arena_floor`, `combat_position: [5,5]`
- Атаковать `xp_dummy` (xp_value=500, hp=3) — один удар через L2 порог
- **Ожидание:** XP ≥ 300, `level_up_available=true`, авто-открывается level-up модалка с заголовком «Level up to L2», dropdown Fighting Style (Defense / Dueling / Great Weapon Fighting), Confirm disabled до выбора
- Нажать Cancel
- **Ожидание:** модалка закрывается, `level_up_available` остаётся true, в sidebar виден ручной «Level Up» button, на последующих `turn`/`round_result` событиях модалка сама НЕ переоткрывается
- Нажать ручной «Level Up» button
- **Ожидание:** модалка снова открывается с теми же опциями
- Выбрать Dueling, нажать Confirm
- **Ожидание:** level=2, max_hp 12 → 20, появился пул `spell_slot_1` (2/2), `lay_on_hands` max 5 → 10
- Завершить ход, на следующем раунде атаковать `practice_thug` опцией `getByRole('menuitem', { name: /Attack practice_thug \+ Smite \(slot 1\)/ })`
- **Ожидание:** в damage breakdown: `1d8 + 2d8 divine_smite + +2 str + +2 дуэлянт`, `spell_slot_1` уменьшается до 1/2, бой завершается

---

## 4. Class Features

### 4.1 Fighter — Second Wind
- Создать fighter, получить урон, нажать Second Wind
- **Ожидание:** HP восстановлены (1d10+level), кнопка исчезает (1 use/short rest)

### 4.2 Fighter — Fighting Style (Defense)
- Создать fighter с Defense style и бронёй
- **Ожидание:** AC = base armor + DEX + 1 (Defense bonus) в статах

### 4.3 Fighter — Fighting Style (Dueling)
- Создать fighter с Dueling style, одноручное оружие, атаковать
- **Ожидание:** damage включает +2 dueling в логе

### 4.4 Rogue — Sneak Attack
- Создать rogue с finesse оружием, атаковать stunned врага (advantage)
- **Ожидание:** sneak_attack damage компонент в логе (+Nd6)

### 4.5 Rogue — Cunning Action
- Создать rogue L1+, в бою увидеть Dash/Disengage как bonus action
- **Ожидание:** Dash потребляет bonus action (не action), Attack остаётся доступным

---

## 5. Equipment

### 5.1 Equip weapon
- Экипировать оружие из инвентаря
- **Ожидание:** weapon_damage в статах обновляется, атака использует новое оружие

### 5.2 Equip armor and shield
- Экипировать броню и щит
- **Ожидание:** AC пересчитывается (armor base + DEX cap + shield bonus)

### 5.3 Use healing potion
- Использовать зелье лечения (use_item)
- **Ожидание:** HP восстановлены, зелье исчезает из инвентаря

---

## 6. Master Panel

### 6.1 Master — Worlds tab
- `/master` → вкладка Worlds
- **Ожидание:** список миров: editable (Fork + Delete) и library (Fork only)

### 6.2 Fork world
- Нажать Fork на library world → ввести ID → Submit
- **Ожидание:** новый мир появляется с Fork + Delete кнопками, toast "World forked"

### 6.3 Delete world
- Нажать Delete на forked world → подтвердить
- **Ожидание:** мир удалён из списка

### 6.4 World editor stepper
- Клик на editable world → stepper открывается
- **Ожидание:** 5 вкладок (Geography, Politics, Settlements, Ecology, Entities), таблицы сущностей с Add/Edit/Delete, Back/Next/Close навигация

### 6.5 Create and manage session
- Вкладка Sessions → выбрать мир → New Session
- **Ожидание:** сессия появляется в списке

### 6.6 Spawn creature
- В SessionView → Creatures → Spawn → заполнить форму (goblin, silverport_city_market)
- **Ожидание:** существо появляется в таблице

### 6.7 Edit creature HP
- Клик на существо → изменить HP → Save
- **Ожидание:** HP обновляется в таблице

### 6.8 Toggle brain type
- Нажать иконку Brain на существе
- **Ожидание:** тип переключается rule_based ↔ llm

### 6.9 Delete creature
- Нажать Delete → подтвердить
- **Ожидание:** существо исчезает из таблицы

### 6.10 Advance time
- Time tab → ввести 24 часа → Advance
- **Ожидание:** время сдвигается на сутки

### 6.11 Save and load
- Saves tab → Save (name: "test") → Load → подтвердить
- **Ожидание:** Save появляется в списке, после Load состояние восстанавливается

### 6.12 Give item — weapon
- Spawn creature → клик на имя → в edit форме секция Inventory видна → "Give Item" → выбрать Weapon → заполнить (name: "Test Sword", damage: 1d8, type: slashing) → Submit
- **Ожидание:** toast "Item given", оружие видно в inventory секции (equipped weapon badge), инвентарь обновляется без закрытия формы

### 6.13 Give item — potion
- В той же creature edit форме → "Give Item" → выбрать Potion → name: "Heal Potion", heal_dice: "2d4+2" → Submit
- **Ожидание:** toast "Item given", зелье видно в inventory секции

---

## 7. Conditions

### 7.1 Apply condition via master
- Master → Edit creature → toggle Prone
- **Ожидание:** condition badge виден в CombatPanel, speed снижена

### 7.2 Condition affects combat
- Stunned враг → атака с advantage
- **Ожидание:** [adv d20(...)] в логе атаки

---

## 8. Inventory & Accessories

### 8.1 View inventory panel
- Создать персонажа, войти в игру
- **Ожидание:** панель Inventory видна: 6 слотов (Weapon, Armor, Shield, Head, Feet, Ring) + сумка + золото

### 8.2 Equip accessory
- Экипировать кольцо или ботинки из инвентаря
- **Ожидание:** аксессуар отображается в слоте, модификатор применяется (AC или speed)

### 8.3 Unequip accessory
- Снять экипированный аксессуар
- **Ожидание:** слот пустой, модификатор снят, предмет в сумке

---

## 9. Trading

### 9.1 Open trade with merchant
- Перейти к торговцу, нажать Trade
- **Ожидание:** TradePanel открывается, видны товары торговца с ценами

### 9.2 Buy item
- Купить предмет у торговца
- **Ожидание:** золото уменьшается, предмет появляется в инвентаре, предмет исчезает у торговца

### 9.3 Sell item
- Продать предмет торговцу
- **Ожидание:** золото увеличивается, предмет исчезает из инвентаря

### 9.4 Insufficient gold
- Попытаться купить предмет без достаточного количества золота
- **Ожидание:** ошибка "Not enough gold", покупка не проходит

---

## 10. Dashboard Layout (Sprint 009)

### 10.1 Three-column dashboard
- Войти в игру (любой мир)
- **Ожидание:** три колонки видны: Nearby (левая), Character+Inventory (центр), Location (правая). Все панели на экране одновременно, без табов.

### 10.2 Compact log + expand overlay
- В игре кликнуть кнопку expand лога (стрелка вниз)
- **Ожидание:** overlay с полным логом событий, кнопка закрытия. Compact лог показывает последние 1-2 события.

### 10.3 NPC inspect modal
- Нажать кнопку inspect (лупа) на NPC в Nearby панели
- **Ожидание:** модалка с именем, расой, ролью, описанием из YAML, фракцией, кнопками Attack/Talk

### 10.4 Click-to-move on BattleMap
- Начать бой, в бою кликнуть по подсвеченной клетке на карте
- **Ожидание:** персонаж перемещается, movement budget уменьшается, подсветка доступных клеток обновляется

### 10.5 Combat layout switch
- Начать бой
- **Ожидание:** правая колонка заменяется на интерактивную BattleMap (CSS Grid), левая колонка = CombatPanel (вся высота). После боя LocationPanel возвращается.

### 10.7 Click occupied cell → creature inspect
- В бою кликнуть на клетку, занятую существом (NPC или враг)
- **Ожидание:** открывается карточка существа (NPC inspect modal) с именем, расой, HP, фракцией (display name, не raw ID)

### 10.6 Action bar budget display
- В бою проверить action bar
- **Ожидание:** строка бюджета: Actions/Bonus/Movement/Reaction с числами. После использования действия — соответствующие кнопки исчезают.

---

## 11. Reactions & Opportunity Attacks (Sprint 012)

### 11.1 OA triggers on leaving reach
- В бою рядом с врагом, нажать move_to на клетку далеко от врага
- **Ожидание:** "Reaction!" popup с кнопками "Melee attack against X" и "Skip". Если враг реагирует — OA event в логе.

### 11.2 Disengage prevents OA
- В бою рядом с врагом, нажать Disengage, затем move_to подальше
- **Ожидание:** перемещение без OA popup, никакого opportunity_attack в логе

### 11.3 Rogue Cunning Action Disengage
- Создать rogue, в бою нажать Disengage (bonus action), затем Attack (action), затем move_to
- **Ожидание:** Disengage потребляет bonus (не action), Attack остаётся, move_to без OA

### 11.4 NPC OA on player movement
- В бою End Turn, подождать ход NPC. Если NPC подошёл и стоит рядом — reaction prompt
- **Ожидание:** NPC двигается, если покидает reach игрока — "Reaction!" popup для игрока

### 11.5 Reaction budget in action bar
- В бою проверить budget display
- **Ожидание:** "Reaction: 1" видно. После OA — "Reaction: 0"

---

## 12. LLM (only with --llm flag)

### 12.1 Talk to LLM NPC
- Переключить NPC на llm brain, поговорить
- **Ожидание:** осмысленный ответ в логе, не шаблонная реплика

### 12.2 LLM NPC combat decisions
- LLM NPC в бою принимает решения
- **Ожидание:** NPC действует осмысленно (атакует, лечится, убегает при низком HP)

---

## 13. Faction Relations & Reputation

### 13.1 Combat sides — allies don't attack each other
- Начать бой с NPC враждебной фракции (гоблин-патрульный)
- **Ожидание:** NPC той же фракции воюют на одной стороне, союзники не атакуют друг друга OA

### 13.2 Kill reputation drop
- Убить NPC в бою, проверить лог событий
- **Ожидание:** в логе событие `reputation_changed` с указанием фракции и дельты

### 13.3 Auto-hostility
- Атаковать мирного NPC вне боя
- **Ожидание:** автоматически начинается бой, NPC и его союзники (по effective_relation) на противоположной стороне. HOSTILE scope валидация не должна блокировать attack до старта боя.

---

## 14. Paladin & Spell Slots

### 14.1 Paladin character creation
- Создать Paladin, выбрать Fighting Style
- **Ожидание:** starting equipment содержит Chain Mail + Shield + Longsword (или греатмечь для GWF); preview HP использует d10 hit die; Lay on Hands pool = 5 × level; level 1 spell slot присутствует в ресурсах

### 14.2 Lay on Hands
- В бою/вне боя использовать Lay on Hands на союзника или на себя, выбрать количество HP
- **Ожидание:** HP цели увеличилось (clamp до max HP), пул Lay on Hands уменьшился на использованное количество; лог событие `entity_lay_on_hands`

### 14.3 Divine Smite
- Paladin атакует melee, попадает, в UI появляется выбор Smite
- **Ожидание:** при согласии тратится spell slot, урон в логе показывает radiant component (+2d8 базово, +1d8 на уровень слота); breakdown по damage types виден

### 14.4 Target scope validation
- Попытаться использовать Lay on Hands на враждебного NPC (ally scope), attack на союзника (hostile scope)
- **Ожидание:** действие отклонено с понятным сообщением; UI не показывает target, запрещённый scope-ом
