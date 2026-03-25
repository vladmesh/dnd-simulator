# Живой мир: от захардкоженных энкаунтеров к автономной экологии

## Проблема

Сейчас мир завязан на игрока:

| Что есть | Как работает | В чём проблема |
|---|---|---|
| Random encounters (Sprint 004) | Бросок шанса при входе игрока в локацию | Монстры появляются из воздуха ради игрока |
| Lair monsters | Статичные Creature в YAML, сидят и ждут | Не двигаются, не взаимодействуют с миром |
| NPC расписание | Детерминированное: кузнец в кузнице 8-18 | Мир как часовой механизм, нет воли |
| Activation | Proximity-based: рядом с игроком = активен | Мир существует только вокруг игрока |
| NPC L2 ticks | Задуманы, не реализованы | Нет автономного поведения |

**Желаемое состояние (Kenshi-like):** мир живёт сам. Фракции сражаются, банды патрулируют дороги, караваны идут из города в город. Игрок — один из многих. Попал под горячую руку — получай.

---

## Ключевая идея: Группы как единица симуляции

Не отдельные NPC, а **группы** (squads / parties). Это естественно: бандиты ходят стаями, солдаты — патрулями, торговцы — караванами.

```
Group (id, faction_id, type, members: list[Creature], behavior, route)
  │
  ├── Patrol (route: [loc_A → loc_B → loc_A], faction: "kingdom")
  ├── Bandit Gang (base: cave_lair, roam: [forest_road, mountain_pass])  
  ├── Caravan (route: [town_A → town_B], cargo, guards)
  ├── Monster Pack (territory: [dark_forest_*], behavior: hunt)
  └── War Party (faction: "orcs", target: "village", siege)
```

### Почему группы, а не отдельные NPC?

1. **Масштабируемость.** 200 NPC индивидуально — дорого. 20 групп по 5-10 — управляемо.
2. **Естественность.** Реальный мир — группы. Патруль, банда, караван, стая волков.
3. **Простота AI.** Группа имеет одно поведение, не 10 отдельных.
4. **Kenshi делает так.** Squad — единица в Kenshi. Работает.

---

## Архитектура: два слоя симуляции

### Слой 1: Абстрактная симуляция (дёшево, всегда)

Группы как точки на графе локаций. Не тикают каждые 6 секунд — тикают по расписанию или при событиях.

```python
class WorldGroup:
    id: str
    faction_id: str
    group_type: GroupType  # PATROL, BANDIT, CARAVAN, MONSTER_PACK, WAR_PARTY
    
    # Абстрактное состояние
    current_location_id: str
    route: list[str]              # маршрут (для патрулей/караванов)
    territory: list[str]          # зона обитания (для бандитов/монстров)
    base_location_id: str | None  # логово / гарнизон
    
    # Состояние группы
    strength: int                 # абстрактная сила (не конкретные HP)
    max_strength: int
    behavior: GroupBehavior       # roam, patrol, raid, hunt, trade, flee
    
    # Шаблон для материализации
    member_templates: list[str]   # ссылки на MonsterTemplate / NPC template
    loot_table_id: str | None
    
    # Timing
    tick_interval: int            # секунды между тиками (patrol=3600, roam=1800)
    last_tick: int
```

**Абстрактная группа** не имеет конкретных Creature. Она — запись: "орочий патруль силой 5 в dark_forest_road". При столкновении (с игроком или другой группой) **материализуется** в конкретных существ.

### Слой 2: Материализация (дорого, по необходимости)

Когда группы встречаются в одной локации (друг с другом или с игроком):

```python
def materialize_group(group: WorldGroup, location_id: str) -> list[Creature]:
    """Превращает абстрактную группу в конкретных существ на EntitiesLayer."""
    creatures = []
    for template_id in group.member_templates:
        template = monster_templates[template_id]
        creature = template.spawn(location_id, unique_id())
        creature.brain = RuleBrain()
        creature.group_id = group.id
        creatures.append(creature)
    return creatures
```

После материализации — стандартный combat через существующую боевую систему. После боя — обновление абстрактного состояния группы (урон, лут, уничтожение).

---

## Взаимодействия групп (ядро живого мира)

### Матрица отношений: фракции

```yaml
factions:
  kingdom:
    relations:
      orcs: hostile
      bandits: hostile
      merchants_guild: friendly
  orcs:
    relations:
      kingdom: hostile
      bandits: neutral
      wildlife: neutral
  bandits:
    relations:
      kingdom: hostile
      merchants_guild: hostile  # грабят караваны
      wildlife: neutral
  wildlife:
    relations:
      _default: neutral        # волки никого не ненавидят, но атакуют слабых
```

### Что происходит при встрече двух групп?

```python
def resolve_group_encounter(group_a: WorldGroup, group_b: WorldGroup, 
                            factions: FactionRelations) -> EncounterResult:
    relation = factions.get_relation(group_a.faction_id, group_b.faction_id)
    
    if relation == "hostile":
        return resolve_abstract_combat(group_a, group_b)
    elif relation == "neutral":
        # Бандиты атакуют слабых даже при neutral
        if group_a.behavior == GroupBehavior.RAID and group_b.strength < group_a.strength:
            return resolve_abstract_combat(group_a, group_b)
        return EncounterResult.PASS  # разошлись
    else:  # friendly
        return EncounterResult.PASS
```

### Абстрактный бой (без игрока)

Когда две NPC-группы встречаются — **не нужна полная D&D симуляция**. Достаточно формулы:

```python
def resolve_abstract_combat(attacker: WorldGroup, defender: WorldGroup) -> AbstractCombatResult:
    """Быстрый резолв без материализации."""
    attack_power = attacker.strength * attacker.faction_modifier
    defense_power = defender.strength * defender.faction_modifier
    
    # Рандом для непредсказуемости (±30%)
    attack_roll = attack_power * random.uniform(0.7, 1.3)
    defense_roll = defense_power * random.uniform(0.7, 1.3)
    
    if attack_roll > defense_roll:
        winner, loser = attacker, defender
    else:
        winner, loser = defender, attacker
    
    # Победитель тоже теряет силу
    winner.strength -= max(1, loser.strength // 3)
    loser.strength = 0  # уничтожена или бежит
    
    return AbstractCombatResult(winner=winner.id, loser=loser.id)
```

Результат боя генерирует **Event** в мир — "Орочий патруль разгромил королевский караван на Лесной дороге". Это событие:
- Попадает в location_log → игрок, придя позже, увидит следы
- Триггерит NPC L2 ticks (когда реализуем)
- Влияет на Politics layer (усиление/ослабление фракции)

---

## Движение групп по миру

### Паттерны поведения

```python
class GroupBehavior(Enum):
    PATROL = "patrol"      # по маршруту туда-обратно
    ROAM = "roam"          # случайно по территории
    RAID = "raid"          # целенаправленно к цели
    TRADE = "trade"        # по маршруту с остановками
    HUNT = "hunt"          # случайно по территории, агрессивно
    GUARD = "guard"        # стоит на месте
    FLEE = "flee"          # к ближайшему безопасному месту
```

### Тик группы

```python
def tick_group(group: WorldGroup, graph: LocationGraph):
    if group.strength <= 0:
        return  # уничтожена
    
    if group.behavior == GroupBehavior.PATROL:
        # Следующая точка маршрута
        next_loc = group.route[group.route_index]
        group.current_location_id = next_loc
        group.route_index = (group.route_index + 1) % len(group.route)
    
    elif group.behavior == GroupBehavior.ROAM:
        # Случайная соседняя локация в пределах территории
        neighbors = graph.neighbors(group.current_location_id)
        valid = [n for n in neighbors if n in group.territory]
        if valid:
            group.current_location_id = random.choice(valid)
    
    elif group.behavior == GroupBehavior.RAID:
        # Кратчайший путь к цели
        path = graph.shortest_path(group.current_location_id, group.target_location_id)
        if path:
            group.current_location_id = path[1]  # следующий шаг
```

### Столкновения

После каждого тика — проверка: есть ли в этой локации другие группы?

```python
def check_collisions(location_id: str, groups: list[WorldGroup], factions):
    groups_here = [g for g in groups if g.current_location_id == location_id]
    
    for i, a in enumerate(groups_here):
        for b in groups_here[i+1:]:
            if should_fight(a, b, factions):
                resolve_encounter(a, b, factions, location_id)
```

---

## Как игрок вписывается

### Игрок = ещё одна "группа"

Концептуально, группа игрока — это `WorldGroup` с одним (или несколькими, в мультиплеере) участниками. Но с отличием: при столкновении всегда **материализуется** (полный D&D бой), а не абстрактный резолв.

```python
def encounter_with_player(npc_group: WorldGroup, player_location: str):
    """Группа NPC пришла туда, где стоит игрок."""
    # Материализуем NPC-группу
    creatures = materialize_group(npc_group, player_location)
    
    # Добавляем на EntitiesLayer
    for c in creatures:
        entities_layer.add_entity(c)
        c.active = True
    
    # Если hostile — враждебный AI инициирует бой (уже есть в Sprint 004)
    # Если neutral — становятся nearby entities, можно взаимодействовать
    # Если friendly — караван остановился, можно торговать
```

### Игрок не отличается от NPC

Критически: те же правила! Орочий рейд на деревню — это не скрипт "для игрока". Это группа орков идёт к деревне. Если игрок в деревне — попадёт в бой. Если нет — деревня сама отобьётся (или нет, через абстрактный бой с гарнизоном).

---

## Куда это ложится в текущую архитектуру

### Новый слой или часть существующего?

> [!IMPORTANT]
> **Предлагаю: новый sub-layer внутри EntitiesLayer, или отдельный слой "Ecology" между Politics и Entities.**

```
Layer 0: Geography    — terrain, weather
Layer 1: Politics     — factions, diplomacy, faction relations ← матрица отношений
Layer 1.5: Ecology    — groups, movement, abstract encounters  ← НОВОЕ
Layer 2: Settlements  — towns, economy
Layer 3: Entities     — creatures (материализованные)
```

Ecology зависит от:
- **Geography** (граф локаций, расстояния)
- **Politics** (отношения фракций)

Ecology влияет на:
- **Settlements** (караван пришёл — экономика буст; рейд — экономика минус)
- **Entities** (материализация при контакте с игроком)

### Что меняется в текущем коде

| Компонент | Сейчас | Будет |
|---|---|---|
| `_check_encounters` | Бросок шанса при входе игрока | Проверка: "есть ли группа в этой локации?" |
| `EncounterTable` | Статичные таблицы шансов | Не нужны — группы сами приходят |
| `MonsterTemplate` | Используется для спавна из encounter tables | Используется для материализации групп |
| `update_activation` | Рядом с игроком = active | + материализованные из групп = active |
| `PoliticsLayer` | Фракции без взаимодействия | Фракции определяют кто с кем дерётся |
| `World.advance_time` | Тикает слои | + тикает группы через EcologyLayer |

### Random encounters остаются как fallback

Можно сохранить `EncounterTable` как "дикие звери в этой зоне" — для ситуаций, когда нет конкретных групп. Но приоритет — группам.

---

## Инкрементальный путь от текущего состояния

### Шаг 0: Faction Relations (основа)
- Расширить PoliticsLayer: матрица отношений между фракциями
- `get_relation(faction_a, faction_b) -> hostile | neutral | friendly`
- У существ (и будущих групп) есть `faction_id`
- Отношения читаются из YAML (`nations.yaml` уже есть — расширить)

### Шаг 1: WorldGroup + абстрактное движение
- `WorldGroup` dataclass
- Определение групп в YAML (content)
- EcologyLayer с tick: движение групп по графу
- Логирование: "Орочий патруль прошёл через Лесную дорогу"

### Шаг 2: Материализация при контакте с игроком
- Игрок вошёл в локацию с группой → материализация
- Замена `_check_encounters` на проверку групп
- Hostile → бой (существующая система)
- Neutral/friendly → nearby entities

### Шаг 3: Абстрактные бои между группами
- Группы в одной локации с hostile отношениями → формула
- События боя в location_log
- "Следы битвы" в awareness: трупы, разрушения, брошенный лут

### Шаг 4: Влияние на мир
- Уничтожение группы → изменение territory control
- Караван дошёл → settlement economy boost
- Рейд успешен → settlement damage
- Ecology ↔ Politics ↔ Settlements feedback loop

### Шаг 5: Респавн и баланс
- Фракции восстанавливают группы (recruitment из settlements)
- Контроль территорий: фракция с войсками на территории = контроль
- Баланс: сильные фракции не должны монополизировать мир

---

## Открытые вопросы

1. **Где хранить группы?** Отдельный слой (EcologyLayer) или часть EntitiesLayer? Отдельный слой чище архитектурно, но добавляет cross-layer зависимость для материализации.

2. **Гранулярность тиков.** Как часто тикать группы? Каждый час? Каждые 10 минут? Чем чаще — тем живее, но тем дороже.

3. **Масштаб.** Сколько групп на мир? 10-20 для маленького мира типа Sword Vale? 50-100 для большого? Формулы абстрактного боя не дорогие, но проверка collisions — O(n²).

4. **Persistence.** Группы сохраняются в save? Да, обязательно. Мир должен быть persistent.

5. **Абстрактный бой vs полный бой.** Всегда абстрактный без игрока, или иногда (для ключевых событий) тоже полный? Полный дорогой и бессмысленный без наблюдателя.

6. **Визуализация.** Как показать игроку что мир живой? Следы боёв, слухи от NPC, изменения в поселениях. Нужна отдельная "rumors" система?

7. **Travel encounter.** Сейчас travel мгновенный. Если группы патрулируют дороги — нужно чтобы travel проходил через промежуточные локации (уже есть в LocationGraph). Пересечение маршрута → encounter.

8. **Sprint 004 compatibility.** Sprint 004 ещё не реализован (Planning complete). Стоит ли вообще делать его текущий дизайн, или сразу переделать на группы? Группы — значительно больший scope.

---

## Влияние на VISION.md

Вписывается в видение:
- **Classic mode (без LLM):** группы двигаются формулами, абстрактные бои формулами. Полностью работает.
- **LLM-enhanced:** L2 тики NPC обогащаются контекстом из ecology ("орки разгромили караван → кузнец берётся за оружие").
- **Масштаб ~200 NPC:** группы это 20-30 абстракций × 5-10 членов. Материализовано одновременно — 5-15 существ (как сейчас).
- **Одна петля раундов:** материализованные группы — обычные active creatures в Round.

---

## TL;DR

**Сдвиг парадигмы:** от "мир реагирует на игрока" к "мир живёт, а игрок — часть мира".

**Механизм:** абстрактные группы (squads) перемещаются по графу локаций, сталкиваются друг с другом и с игроком. Абстрактный бой между NPC-группами (формула), полный D&D бой при участии игрока (материализация).

**Инкрементально:** faction relations → world groups → материализация → abstract combat → world impact.
