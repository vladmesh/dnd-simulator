# E2E Playbook

Сценарии для регрессионного тестирования через Playwright. Каждый сценарий — что делаем, что ожидаем. Обновляется при добавлении новых фич.

**Последнее обновление:** 2026-03-26

---

## 1. Session Setup

### 1.1 Quick start — pick existing world
- Открыть `/`, выбрать мир (Sword Vale), создать персонажа (fighter, human, STR 16)
- **Ожидание:** редирект на `/play/:sessionId`, WebSocket подключён, первый turn в логе

### 1.2 World Builder wizard
- Открыть `/`, нажать "Build Custom World"
- Пройти 5 шагов: Geography → Politics → Settlements → Ecology → Entities (выбрать шаблон на каждом)
- На шаге Details ввести ID, название, описание → "Create World & Start"
- **Ожидание:** мир создан, сессия создана, переход на CharacterForm, после создания персонажа — в игру

### 1.3 World Builder — back navigation
- В wizard нажать Back на шаге 2+
- **Ожидание:** возврат к предыдущему шагу; Back на шаге 1 → возврат к списку миров

### 1.4 Assembled world in quick start
- После создания мира через wizard, вернуться на `/`
- **Ожидание:** новый мир виден в списке quick-start миров

### 1.5 Language toggle
- На SetupScreen переключить язык EN→RU
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

### 6.1 Create and manage session
- `/master` → выбрать мир → New Session
- **Ожидание:** сессия появляется в списке

### 6.2 Spawn creature
- В SessionView → Creatures → Spawn → заполнить форму (goblin, arena_floor)
- **Ожидание:** существо появляется в таблице

### 6.3 Edit creature HP
- Клик на существо → изменить HP → Save
- **Ожидание:** HP обновляется в таблице

### 6.4 Toggle brain type
- Нажать иконку Brain на существе
- **Ожидание:** тип переключается rule_based ↔ llm

### 6.5 Delete creature
- Нажать Delete → подтвердить
- **Ожидание:** существо исчезает из таблицы

### 6.6 Advance time
- Time tab → ввести 24 часа → Advance
- **Ожидание:** время сдвигается на сутки

### 6.7 Save and load
- Saves tab → Save (name: "test") → Load → подтвердить
- **Ожидание:** Save появляется в списке, после Load состояние восстанавливается

### 6.8 Give item — weapon
- Spawn creature → клик на имя → в edit форме секция Inventory видна → "Give Item" → выбрать Weapon → заполнить (name: "Test Sword", damage: 1d8, type: slashing) → Submit
- **Ожидание:** toast "Item given", оружие видно в inventory секции (equipped weapon badge), инвентарь обновляется без закрытия формы

### 6.9 Give item — potion
- В той же creature edit форме → "Give Item" → выбрать Potion → name: "Heal Potion", heal_dice: "2d4+2" → Submit
- **Ожидание:** toast "Item given", зелье видно в inventory секции

### 6.10 Layer Editor — fork, edit YAML, verify in session
- `/master` → выбрать мир (Sword Vale) → Fork entities layer → нажать Edit
- Выбрать npcs.yaml, изменить имя NPC (Edgar the Smith → Edgar the Modified)
- Нажать Save → создать новую сессию → в god-mode проверить имя NPC
- **Ожидание:** NPC имеет изменённое имя в сессии

### 6.11 Layer Editor — invalid YAML error
- Открыть editor на custom layer → ввести невалидный YAML (например `[[[`) → Save
- **Ожидание:** ошибка с деталями YAML-парсинга, после Reload контент не изменён

### 6.12 Layer Editor — library layer read-only
- `/master` → выбрать мир с library layers
- Library layers показывают кнопку "View" (не "Edit")
- Нажать View → editor открывается в read-only (нет кнопки Save или Save неактивна)
- **Ожидание:** нельзя сохранить изменения в library layer

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

## 10. LLM (only with --llm flag)

### 10.1 Talk to LLM NPC
- Переключить NPC на llm brain, поговорить
- **Ожидание:** осмысленный ответ в логе, не шаблонная реплика

### 10.2 LLM NPC combat decisions
- LLM NPC в бою принимает решения
- **Ожидание:** NPC действует осмысленно (атакует, лечится, убегает при низком HP)
