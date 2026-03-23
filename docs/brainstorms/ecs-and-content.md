# Брейншторм: Граница кода и контента

## Проблема

Сейчас `Creature` — монолит: сам хранит статы как сырые числа, сам исполняет действия через if/elif, сам определяет что можно делать. При 6 типах действий и нулевом инвентаре это терпимо, но масштабироваться некуда:

- Нельзя наложить бафф/дебафф без мутации базового поля (а при снятии — откуда знать исходное значение?).
- Нельзя дать мечу действие "атака" — атаки зашиты в кортеж на существе.
- Нельзя сделать дверь с HP без наследования от Creature (а у двери нет мозга).
- Нельзя описать предмет или заклинание в YAML — всё требует кода.

Цель: **код не знает про "меч" или "сундук"**. Код — универсальный движок. Контент — YAML-файлы, которые движок умеет исполнять.

---

## Карта зависимостей

Системы строятся послойно. Каждый уровень опирается на предыдущий. Горизонтальные элементы можно параллелить.

```
Уровень 3:  Заклинания ──── Пропсы ──── Торговля
                │  │           │            │
Уровень 2:  Инвентарь ─── Диспатч действий ─── Ресурсы
                │                │
Уровень 1:  Conditions ──── Вычисляемые статы
                │                │
Уровень 0:  Активация ──── Fast-forward ──── Round в ядре
```

Каждый уровень описан ниже — что делает, от чего зависит, как внедрять.

---

## Уровень 0 — Фундамент (game loop)

Без этого уровня остальное строить бессмысленно: нет рабочего цикла игры.

### 0a. Активация / деактивация существ ✅

**Сейчас:** ~~`active` = жив/мёртв. Все живые NPC ходят каждый раунд, везде.~~ **Сделано.**

**Реализовано:** `active: bool` — proximity-based, не трёхстатусный enum.
- `active=True` — существо участвует в раундах (рядом с игроком или в бою).
- `active=False` — dormant (живо, но не ходит).
- Смерть = `is_alive` (hp <= 0), не `active=False`. Мёртвые не удаляются со слоя (видны как трупы), но не ходят (проверка `is_alive` в `run_round`). Убрана избыточная строка `target.active = False` при смерти в `combat_manager`.

**Отклонения от плана:**
- **Без enum.** Вместо трёх состояний (active/dormant/dead) — булев `active` + `is_alive`. Dead не нужен отдельным значением: воскрешение = создание нового существа, а не переключение флага.
- **Без ручного пробуждения (мастер/триггер).** Пока не реализовано — все dormant/active решается proximity. Можно добавить позже.

**Механика:**
- `EntitiesLayer.update_activation(time)` вызывается в начале каждого `Round.run_round()`.
- Находит все `PlayerCharacter`, собирает их `location_id`.
- Для каждого не-игрока: `active = (effective_location in player_locations) or in_combat`.
- NPC с расписанием: `effective_location = current_location(hour)` (расписание > `location_id`).
- Без игроков (тесты без PlayerCharacter) — no-op, ничего не меняет.
- `Round.run_loop()` получил параметр `max_rounds` для контролируемого завершения в тестах.

### 0b. Fast-forward времени ✅

**Сейчас:** ~~когда никто не active — время стоит.~~ **Сделано.**

**Реализовано:** wait + fast-forward как единая система.
- `wait(hours=N)` ставит `creature.wake_at_seconds = now + N*3600`, существо становится dormant.
- Работает для всех существ, не только для игрока.
- `Round.run_loop()`: после раунда, если нет active существ — `_fast_forward()` ищет ближайший `wake_at`, мотает `advance_time` до этой точки, вызывает `update_activation`.
- Если `wake_at` нет ни у кого — loop завершается (мир замер).
- Player с `wake_at` не является якорем — его proximity не активирует NPC рядом.
- При пробуждении (timer expired) player снова якорь → NPC рядом реактивируются.

**Пробуждение:**
- По таймеру: `wake_at_seconds` достигнут → `update_activation` обнуляет wake_at, существо снова eligible для активации.
- По proximity: если существо активировано proximity (якорь рядом), `wake_at` обнуляется (разбудили раньше).
- По атаке: пока не реализовано (отдельная механика).
- Мастером: пока не реализовано.

**Отклонения от плана:**
- Travel (`wait(travel_to=X)`) остался как legacy — мгновенный перенос + advance_time. Будет переделан.
- `wake_at_seconds` персистится в save/load.

**NPC и wait:**
- NPC с расписанием при dormancy "растворяются в расписании" — существуют как запись schedule, активируются когда якорь оказывается в их scheduled location.
- NPC brain может вернуть `wait` — NPC засыпает с таймером, просыпается по wake_at или по proximity.

### 0d. Explicit locations + NPC schedule placement ✅

**Сейчас:** ~~Location автогенерируется из Region (1 region = 1 location). NPC schedule ссылается на виртуальные `{settlement_id}_{label}` location_id которых нет в графе. Proximity activation не работает для миров с settlement NPC.~~ **Сделано.**

**Реализовано:**
- **Убрана `_generate_locations_from_regions`.** Каждый мир обязан определить locations явно — crash при отсутствии.
- **Settlement locations в village.yaml:** 8 locations (village_square, millbrook_smithy, millbrook_tavern, millbrook_market, millbrook_home, millbrook_fields, millbrook_barracks, millbrook_patrol) с описаниями и edges.
- **arena.yaml:** `arena_floor` как единственная location.
- **NPC/player используют `start_location`** вместо `region_id`. `start_region` остался как legacy alias в API.
- **Schedule validation:** `resolve_schedule` принимает `known_locations` — entries с несуществующими locations отбрасываются. `parse_npc` крашится если `start_location` не в known_locations. Spawn API тоже валидирует.
- **NPC перемещение по расписанию:** `update_activation` теперь перемещает NPC в `effective_location` при активации (`e.location_id = effective_location`). Кузнец днём в кузнице, вечером в таверне. Canned dialogue зависит от activity.

**Дизайн-решения:**
- Settlement ≠ Location. Settlement — экономическая абстракция (Politics/Settlements layer). Location — конкретное место в LocationGraph.
- Schedule labels (`smithy`, `tavern`) пока резолвятся как `{settlement_id}_{label}`. В будущем возможен маппинг через settlement role→location (Level 2+).
- Маленькие settlements могут быть одной location. Большие — десятками. Это решение мастера.

### 0c. Round как часть ядра ✅

**Сейчас:** ~~Round создаётся в WebSocket-адаптере. CLI и REST не могут гонять раунды.~~ **Сделано.**

**Реализовано:** Round lifecycle перенесён в `GameSession` (`service/session.py`):
- `GameSession` владеет Round, PlayerBrain, background thread.
- `SessionEventListener` protocol — транспорт реализует для получения событий.
- `routes_ws.py` стал тонким мостом: валидация → listener → forward actions.
- `add_listener` / `remove_listener` — потокобезопасное управление подписчиками.
- Replay `last_turn_msg` для reconnect (через `await` в WS handler, не через `run_coroutine_threadsafe`, чтобы избежать deadlock на event loop).
- Round останавливается когда все listeners отключились.

CLI и REST теперь могут запускать раунды через `GameSession.start_round()`.

---

## Уровень 1 — Механическая база

### 1a. Conditions (состояния D&D)

**Зачем:** Prone, Grappled, Poisoned, Frightened, Stunned — базовые условия D&D. Каждое condition = набор эффектов (disadvantage на атаки, speed = 0, и т.д.). Это **простейшая** форма модификаторов и proof-of-concept для всей системы.

**Как работает:**
- `Creature` получает поле `conditions: set[Condition]`.
- Condition — это enum или data-class с набором эффектов.
- Эффекты учитываются при вычислении статов (→ 1b) и при резолве действий.

**Почему первым:** не требует инвентаря, заклинаний, UI. Но заставляет решить как хранить и применять модификаторы. Валидирует архитектуру modifier pipeline на минимальном примере.

### 1b. Вычисляемые статы (derived stats)

**Зачем:** AC, speed, attack bonus — не просто числа, а `база + модификаторы`. Без этого невозможны баффы, экипировка, conditions.

**Как работает:**
Pipeline: `Базовое значение → [модификаторы] → Итог`.

Модификатор:
- `target`: что меняем (AC, speed, attack roll, saving throw...)
- `op`: как (ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE)
- `value`: числовое значение (для ADD/OVERRIDE)
- `source`: откуда пришёл (id предмета, заклинания, condition)
- `duration`: когда истекает (permanent, end_of_turn, timed, concentration)

Начать с двух статов: `effective_ac` и `effective_speed`. Они учитывают conditions из 1a. Потом — equipment из 2a.

**Нюансы D&D 5e, которые pipeline должен учитывать:**
- Stacking: одинаковые источники не стакаются (два Ring of Protection +1 = всё равно +1).
- Order of operations: OVERRIDE задаёт базу, затем ADD поверх (Mage Armor base 13+DEX, Shield +5 → 18+DEX).
- Advantage/disadvantage: не суммируются, любое количество = одно; adv + disadv = ни того ни другого.
- Concentration: ровно одно заклинание, новый каст снимает старый.

---

## Уровень 2 — Строительные блоки контента

### 2a. Инвентарь и экипировка

**Зачем:** отделить "лежит в рюкзаке" от "надето и даёт бонусы".

**Как работает:**
- `Inventory` = список предметов.
- `EquipmentSlots` = слоты (head, chest, main_hand, off_hand, ...). Набор слотов определяется контентом, не хардкодом.
- Предмет — YAML-объект: id, name, slot, base_value, modifiers[], granted_actions[].
- **Equip:** предмет регистрирует свои модификаторы на владельце (source = item_id).
- **Unequip:** удаляет все модификаторы с source = item_id. Чистка стейта — бесплатно.

```yaml
item_id: dwarven_plate
type: equipment
slot: chest
base_value: 1500
modifiers:
  - target: AC
    op: OVERRIDE
    value: 18
```

Движок читает YAML → предмет работает. Без кода.

### 2b. Диспатч действий (Action Dispatch)

**Зачем:** заменить if/elif в execute_action на реестр обработчиков. К этому моменту типов действий будет >10 (базовые + equip/unequip/use_item), и if/elif начнёт мешать.

**Как работает:**
1. **ActionProvider** — интерфейс: "я даю список доступных действий". Реализуют: экипированное оружие, фичи класса, заклинания.
2. `Creature.get_available_actions()` собирает: базовые (dodge, dash, flee) + от провайдеров.
3. **ActionDispatcher** — реестр: action_name → handler function. Handler — чистая функция в `rules/`.
4. `Creature.execute_action()` → `dispatcher.dispatch(action, creature, emit_fn)`.

### 2c. Ресурсы (Spell Slots, Ki, Rage, Charges)

**Зачем:** классы и магические предметы строятся на расходуемых ресурсах. Хардкод `self.ki_points` убивает расширяемость.

**Как работает:**
- `ResourceTracker` на существе, содержит набор `ResourcePool`.
- Pool: `{id, max, current, reset_on}`. Reset triggers: SHORT_REST, LONG_REST, DAWN.
- ActionProvider заклинания проверяет ресурс: нет слота → действие недоступно. При исполнении — ресурс тратится.
- Восстановление: событие отдыха/рассвета → ResourceTracker обнуляет подходящие пулы.

```yaml
resource_pools:
  - id: spell_slot_1
    max: 4
    reset_on: LONG_REST
  - id: rage
    max: 3
    reset_on: LONG_REST
```

---

## Уровень 3 — Gameplay-системы

### 3a. Заклинания

Заклинание = ActionProvider + потребитель ResourcePool + генератор Conditions/Modifiers. Зависит от всего из Уровней 1-2.

```yaml
spell_id: shield
level: 1
casting_time: reaction
slot_cost: 1
effects:
  - type: modifier
    target: AC
    op: ADD
    value: 5
    duration: end_of_next_turn
```

Движок читает YAML → заклинание работает (для типовых эффектов). Уникальная логика (Wish, Polymorph) — отдельные обработчики в коде.

### 3b. Интерактивные объекты (Props)

**Проблема:** дверь с HP, сундук с лутом, ловушка — не ложатся в иерархию Entity → Creature. У сундука нет мозга, у ловушки нет HP.

**Решение:** composition вместо наследования. Entity — контейнер с id и location. К нему прикрепляются типизированные компоненты через optional поля:
- Деревянная дверь: `Destructible(ac=15, hp=18)` + `Lockable(dc=12)`
- Сундук: `Destructible(ac=11, hp=10)` + `Inventory(items=[...])` + `Lockable(dc=15)`
- Ловушка: `TrapTrigger(save=DEX, dc=15, damage="3d6 fire")`

Не generic ECS с `has_component()` — типизированные optional поля с mypy-проверками.

### 3c. Торговля

Стык жёсткой механики (золото, предметы) и свободного текста (разговор с торговцем, торг). LLM не придумывает цены.

1. **Цена = формула:** `base_value × settlement_modifier × attitude_modifier`. Чистая функция. Осаждённый город — ×3 на еду. Враждебный торговец — +20%.
2. **LLM инициирует:** игрок торгуется текстом → LlmBrain вызывает тул `propose_trade(item_id, price)`.
3. **UI подтверждает:** поп-ап "Торговец предлагает Щит за 10 gp. [Принять] [Отказаться]".
4. **Код исполняет:** `execute_trade()` переносит предмет и списывает золото. LLM не трогает кошелёк напрямую.

`attitude_modifier` берётся из существующей NpcMemory (теги отношений), не из параллельной системы.

---

## Граница кода и контента

| Код (универсальный движок) | Контент (YAML, World Builder) |
|---|---|
| Modifier pipeline, StatBlock | Предметы с модификаторами |
| ActionDispatcher, handlers в rules/ | Заклинания с эффектами |
| ResourceTracker | Пулы ресурсов классов/предметов |
| Inventory, EquipmentSlots | Описания предметов, слотов |
| execute_trade() | Базовые цены, торговцы |
| Conditions, Destructible | Пропсы, ловушки, двери |

Мастер в World Builder создаёт предмет, заклинание или NPC — прописывая данные в YAML. Движок исполняет их без кода.

---

## Порядок внедрения

1. **Уровень 0** — закрыть фундамент: активация, fast-forward, Round в ядре. Без этого нет рабочего game loop.
2. **Уровень 1** — Conditions + derived stats. Proof-of-concept modifier pipeline на минимальном примере (AC, speed, conditions).
3. **Уровень 2** — Inventory/Equipment → Action Dispatch → Resources. Каждый шаг добавляет потребителей в modifier pipeline.
4. **Уровень 3** — Заклинания, пропсы, торговля. К этому моменту инфраструктура на месте.

Каждый уровень валидирует архитектурные решения предыдущего. Не строить следующий пока предыдущий не работает.
