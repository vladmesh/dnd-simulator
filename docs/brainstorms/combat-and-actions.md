# Боевая система и действия

Обсуждение 2026-03-20.

## Ключевое решение: единый пошаговый режим

Нет разделения на "свободный режим" и "бой". Игра **всегда** пошаговая.
Каждое существо по очереди выбирает действие (tool call). "Бой" — это просто
ситуация, когда существа начинают выбирать `attack()` вместо `say()`.

## Главный цикл

Вся игра — один цикл. Максимально тупой, без логики:

```python
while True:
    for creature in world.get_active_creatures():
        creature.take_turn(world)
```

Всё. Creature сам:
1. Строит awareness из world (погода, кто рядом, и т.д.)
2. Решает действие (LLM / input / if-else)
3. Выполняет через world (world.handle_event)
4. Обрабатывает ошибки (retry для LLM, сообщение для игрока)

Активные сущности — все в мире у кого `active=True`. Те что далеко от игрока
деактивированы и не попадают в список.

## Всё — tool call

NPC не "говорит текст". NPC выбирает действие через tool use:

```
say(text="Добро пожаловать, путник!")    — говорить
attack(target_id="goblin_1", weapon="longsword")  — атаковать
idle()                                    — ничего не делать
```

Текстовый ответ от LLM без tool call — ошибка. Единственный цикл обратной
связи — если LLM некорректно дёрнула инструмент (невалидные параметры, цель
не существует). Успешный tool call = ход окончен.

## take_turn(world) — полиморфная точка входа

Каждый тип существа знает как принимать решения. Источник решений — свойство
существа, как LLM у NPC:

```python
class Npc(Character):
    llm: LlmClient              # источник решений
    def take_turn(self, world):
        awareness = build_awareness(world, self.region_id)
        action = self.llm.generate_with_tools(awareness, tools)
        world.handle_event(Event(action))

class PlayerCharacter(Character):
    input_fn: Callable           # получить ввод
    output_fn: Callable          # показать вывод
    def take_turn(self, world):
        awareness = build_awareness(world, self.region_id)
        self.output_fn(format_awareness(awareness))
        raw = self.input_fn("> ")
        action = parse_action(raw)
        world.handle_event(Event(action))

class Wolf(Creature):            # статистические монстры
    def take_turn(self, world):
        if enemy_nearby: attack(nearest)
        else: idle()
```

Циклу вообще всё равно кто перед ним. I/O игрока — абстрактные callable,
можно подменить на REST/Telegram без переделки логики.

## Выполнение действий через World

World уже имеет `handle_event(event)` — рассылает по всем слоям.
Creature вызывает `world.handle_event(Event("attack", ...))`, EntitiesLayer
обрабатывает: валидирует, резолвит через rules/, применяет урон.

Если действие невалидно — слой возвращает ошибку. Creature обрабатывает:
- NPC/LLM → retry с другим tool call
- Player → output_fn("Невозможно") → input_fn снова
- Monster → fallback action

## Механики (rules/) — атомарный фундамент

Вся D&D сводится к трём типам бросков + урон:
- **Attack roll** — d20 + modifier vs AC (nat 20 = крит, nat 1 = промах)
- **Ability check** — d20 + modifier vs DC (нет критов по RAW)
- **Saving throw** — d20 + modifier vs DC
- **Damage roll** — dice expression → число, удвоение дайсов при крите

rules/ — набор утилит для слоёв. Чистые функции, без состояния.

## Боевые данные на Creature

```python
class DamageType(Enum):        # SLASHING, FIRE, RADIANT, ...
class ResolveType(Enum):       # ATTACK_ROLL, SAVING_THROW, AUTO_HIT
class DamageComponent:         # dice + type ("1d8" SLASHING)
class Attack:                  # name, ability, damage components, reach, resolve type
```

Attack покрывает и оружие, и single-target заклинания (fire bolt, magic missile).
Area-эффекты (fireball) — отдельная абстракция, потом.

Smite / Hex — дополнительные DamageComponent при резолюции, не меняют Attack.

## HP мутация

`take_damage()` / `heal()` / `is_alive` — методы на Creature.
rules/ не мутирует стейт. Слой вызывает resolve → применяет через Creature.

## Инициатива

Не нужна для базовой версии. Порядок опроса фиксированный.
В будущем: перебросить инициативу и перемешать очередь при начале боя.

## Лог региона и perceive_event

Каждый регион ведёт буфер событий. Когда creature делает `take_turn`, он
получает awareness (снимок мира сейчас) + лог событий с его прошлого хода.

Сырые Event → текст через шаблоны + `perceive()`:
- `ENTITY_ATTACK(player → smith)` → smith видит: "Полуэльф с мечом ударил тебя"
- `ENTITY_SAY(smith, "Стража!")` → guard видит: "Кузнец говорит: «Стража!»"

Форматирование — чистая функция `perceive_event(event, observer, entities)`.
Без LLM. Каждый тип события — шаблон с подстановкой через `perceive()`.

**Будущее:** фоллбек на LLM для произвольных действий (сальто, жесты и т.п.),
которые не укладываются в известные типы. Открывает пространство для свободного
отыгрыша. Пока — заглушка для неизвестных событий.

## Что реализовано

```
rules/dice.py         ✅  roll("2d6+3"), roll_d20(advantage/disadvantage)
rules/checks.py       ✅  attack_roll, ability_check, saving_throw, damage_roll
core/character.py     ✅  Entity → Creature → Character → Player/Npc
                      ✅  Attack, DamageComponent, DamageType, ResolveType
                      ✅  take_damage(), heal(), is_alive
llm/client.py         ✅  generate_with_tools() — tool use support
llm/tools.py          ✅  build_npc_tools() — say, attack, idle schemas
entities/models.py    ✅  Npc.take_turn() — LLM с tools + retry
core/player.py        ⬜  PlayerCharacter.take_turn() с input_fn/output_fn
world.py              ✅  handle_event() — рассылка по слоям
game loop             ⬜  главный цикл
```
