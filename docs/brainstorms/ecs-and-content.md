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

### 1a. Conditions (состояния D&D) — частично ✅

**Реализовано (через action-dispatcher Phase 6):**
- `Creature.conditions: dict[Condition, int | None]` (ConditionsMap) — timed и permanent conditions.
- `Condition` enum: PRONE, GRAPPLED, INCAPACITATED, STUNNED, UNCONSCIOUS, BLESSED, DODGING.
- `tick_conditions()` в `rules/conditions.py` — декремент таймеров, удаление истёкших.
- `rules/conditions.py`: `is_incapacitated()`, `effective_speed()`, `attack_advantage()` — чистые функции, учитывают conditions при резолве.
- Интеграция: Round тикает conditions в начале хода, resolve_attack проверяет BLESSED (+d4), DODGING (disadvantage).

**Что осталось:**
- **Эффекты conditions не систематизированы.** Каждый condition проверяется ad-hoc в конкретных местах (resolve_attack, effective_speed). Нет единого маппинга condition → effects.
- **Не все D&D conditions реализованы.** Poisoned (disadvantage на атаки + ability checks), Frightened (disadvantage + не может приближаться к источнику), Restrained, Blinded, Deafened — отсутствуют.
- **Condition application через прямую мутацию dict.** Нет `add_condition()` / `remove_condition()` API — код напрямую пишет в dict.
- **Saving throws для снятия conditions** — не реализованы (dead code `auto_fail_str_dex_saves()` есть, но не подключен).

### 1b. Вычисляемые статы (derived stats) ✅

**Реализовано:**
- `core/modifiers.py` — data types: `Modifier`, `ModifierOp` (ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE), `StatType` (AC, SPEED, ATTACK_ROLL, INITIATIVE), `AttackModifiers`.
- `rules/modifiers.py` — pipeline: declarative condition→modifier mapping (16 conditions), `compute_stat()`, `resolve_advantage()`, `collect_dice_bonuses()`.
- Convenience API: `effective_ac(creature)`, `effective_speed(creature)`, `attack_modifiers(attacker, target, melee=)`.
- D&D 5e stacking: same `source` doesn't stack (take highest). OVERRIDE wins (most restrictive). Advantage + disadvantage cancel.
- `melee_only` / `ranged_only` on Modifier for context-dependent effects (Prone).
- `Condition.DODGING` added to enum, set in `resolve_dodge` alongside `is_dodging` bool.
- Combat manager replaced: 30+ lines of inline stat computation → single `attack_modifiers()` call.
- Old ad-hoc functions removed from `rules/conditions.py`: `effective_speed`, `attacker_has_disadvantage`, `attacks_against_have_advantage`, `attacks_against_have_disadvantage`, `is_auto_crit`.
- 71 unit tests in `test_modifiers.py`.

**Что осталось для расширения (не блокирует):**
- Duration на модификаторах не нужен — conditions владеют длительностью через ConditionsMap.
- `SET_BASE` operation (для Mage Armor: base 13+DEX) — добавить когда появится armor system.
- `MULTIPLY` operation (для Haste: double speed) — добавить когда появятся заклинания.
- Concentration tracking — отдельная система поверх conditions.
- Equipment modifiers через `grant_conditions` на WeaponDef — пока не применяются автоматически.

---

## Уровень 2 — Строительные блоки контента

### 2a. Инвентарь и экипировка ✅

**Реализовано (action-dispatcher Phases 5-6 + equip/unequip):**
- `Item` (frozen dataclass): id, name, item_type (POTION/WEAPON), params, weapon_def.
- `Creature.inventory: list[Item]` — предметы в рюкзаке. `USE_ITEM` расходует, `EQUIP` перемещает в weapon slot.
- `Creature.equipped_weapon: Item | None` — текущее оружие. `UNEQUIP` возвращает в inventory.
- `WeaponDef` — типизированное описание оружия (damage, reach, ability, finesse, magic bonus, grant_actions, grant_conditions).
- `EQUIP` / `UNEQUIP` — free actions (D&D 5e object interaction). Swap: старое оружие → inventory, новое → slot.
- `EquipmentActionProvider` — EQUIP доступен если в inventory есть weapons, UNEQUIP если weapon equipped.
- Content loader: `equipped: true` flag в YAML для pre-equipped weapons. Без флага — всё в inventory, NPC экипируют сами.
- RuleBrain: автоматически equip на первом ходу если unarmed.
- LLM brain: видит inventory + equip tool + situational hint ("you are UNARMED, use equip"). Экипирует сам.
- Frontend: equip dropdown (показывает weapons из inventory), unequip button.
- Perception: equip/unequip события видны в combat log.

**Что осталось:**
- **Нет EquipmentSlots.** Только `equipped_weapon` — один слот. Для брони, колец, щитов нужна система слотов.
- **Нет modifiers от экипировки.** `grant_conditions` парсится но не применяется автоматически при equip. Pipeline (1b) готов, нужен hook.
- **Нет base_value / gold cost** у предметов.

### 2b. Диспатч действий (Action Dispatch) ✅

**Полностью реализовано.** См. `docs/plans/action-dispatcher.md` (Phases 0-6).

- `ActionDispatcher` — реестр handler-ов + validate → execute pipeline.
- `ActionProvider` protocol — 4 провайдера: BaseActionProvider, InventoryActionProvider, EquipmentActionProvider, WeaponActionProvider.
- `Creature.execute_action()` удалён. Creature — чистые данные + brain.
- 11 action types: idle, say, attack, dodge, flee, move, dash, wait, bless, use_item, equip, unequip.
- Budget enforcement, target/reach validation — в цепочке `_CHECKS` валидатора.

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

1. **Уровень 0** ✅ — активация, fast-forward, Round в ядре.
2. **Уровень 1** ✅ — Conditions (1a) + derived stats / modifier pipeline (1b). **Следующий шаг: Level 2.**
3. **Уровень 2** — частично ✅. Action Dispatch (2b) ✅. Inventory/Equipment (2a) ✅ (equip/unequip, weapon swap, все мозги работают). Resources (2c) — не начато.
4. **Уровень 3** — Заклинания, пропсы, торговля. Не начато.

Каждый уровень валидирует архитектурные решения предыдущего. Не строить следующий пока предыдущий не работает.
