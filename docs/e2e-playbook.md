# E2E Playbook

Сценарии для регрессионного тестирования через Playwright. Каждый сценарий — что делаем, что ожидаем. Обновляется при добавлении новых фич.

**Последнее обновление:** 2026-03-27

---

## 1. Session Setup

### 1.1 Landing page — Player/DM split
- Открыть `/`
- **Ожидание:** две карточки: "Play" (→ /play) и "Dungeon Master" (→ /master)

### 1.2 Quick start — pick existing world
- Нажать "Play" → выбрать мир (Sword Vale) → "New Session" → создать персонажа (fighter, human, STR 16)
- **Ожидание:** редирект на `/play/:sessionId`, WebSocket подключён, первый turn в логе

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

### 10.6 Action bar budget display
- В бою проверить action bar
- **Ожидание:** строка бюджета: Actions/Bonus/Movement/Reaction с числами. После использования действия — соответствующие кнопки исчезают.

---

## 11. LLM (only with --llm flag)

### 11.1 Talk to LLM NPC
- Переключить NPC на llm brain, поговорить
- **Ожидание:** осмысленный ответ в логе, не шаблонная реплика

### 11.2 LLM NPC combat decisions
- LLM NPC в бою принимает решения
- **Ожидание:** NPC действует осмысленно (атакует, лечится, убегает при низком HP)
