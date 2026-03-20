# Боевая система и действия

Обсуждение 2026-03-20.

## Действие — базовая абстракция

В D&D "атака" — лишь одно из действий. Базовая единица — **Action**, не Attack.

Типы действий:
- **Attack** — удар оружием/безоружный (d20 + mod vs AC)
- **Cast a Spell** — заклинание (разные механики резолюции)
- **Dodge, Dash, Disengage, Hide** — тактические
- **Use an Object** — зелье, дверь, рычаг

## Модель Action

```python
@dataclass(frozen=True)
class Action:
    name: str
    resolution: AttackRoll | SavingThrow | Auto
    targeting: Single | Area | Self
    effects: list[Effect]  # Damage, Heal, ApplyCondition
    requirements: list[Requirement]  # HasSpellSlot, WeaponEquipped, InRange
```

Примеры:
- Меч: `Action("longsword", AttackRoll(STR), Single, [Damage("1d8", STR)])`
- Fireball: `Action("fireball", SavingThrow(DEX, dc=15), Area(20ft), [Damage("8d6")], requires=[HasSpellSlot(3)])`
- Magic Missile: `Action("magic missile", Auto(), Single, [Damage("1d4+1")] * 3, requires=[HasSpellSlot(1)])`
- Dodge: `Action("dodge", Auto(), Self, [ApplyCondition(DODGING)])`

## Creature хранит список действий

```python
class Creature(Entity):
    ability_scores, max_hp, current_hp, ac
    actions: list[Action]   # что вообще умеет
```

У волка — `[bite]`. У файтера — `[longsword, dodge, dash]`. У мага — `[staff, magic_missile, fireball]`.

Character наследует Creature и добавляет класс/расу/alignment. Экипировка/спеллы **генерируют** actions динамически.

## Валидация — постфактум, не предварительная

Предварительная фильтрация (available_actions с валидными целями) перегружает интерфейс и дорога по вычислениям. Вместо этого:

1. Creature знает свои действия: `creature.actions → [longsword, shortbow, magic_missile, dodge]`
2. Игрок/LLM выбирает действие + цель свободно
3. `resolve_action()` либо возвращает результат, либо ошибку валидации

```python
resolve_action(actor, action, target, context) → ActionResult | ActionError
```

Ошибки понятны и игроку, и LLM:
- "Слишком далеко для рукопашной атаки"
- "Нет spell slot 3 уровня"
- "Вы оглушены и не можете действовать"

LLM получает ошибку → пробует другое действие (паттерн уже в бэклоге).

Команда `actions` — просто dump списка без валидации. "Вот что вы умеете".

## Резолюция — чистая функция в rules/

```python
# rules/combat.py
def resolve_action(
    actor: Creature,
    action: Action,
    target: Entity | None,
    context: CombatContext | None,
) -> ActionResult | ActionError:
```

Без побочных эффектов. Применение результата к миру — отдельно, в service/combat manager.

## Действия вне боя

`resolve_action` работает и без `CombatContext`. Мистический снаряд в дверь — тот же Action, target это Entity (дверь). Результат: урон объекту.

## Кто рядом

Сейчас: все в одном `region_id` — "рядом". Для боя нужна хотя бы грубая дистанция. Варианты:
- Зоны: melee (5ft), close (30ft), far (120ft)
- Сетка с координатами (сложнее)

Решение отложено — начинаем с "все в регионе рядом".

## Интерфейс

**Игрок** — команды:
```
> actions                              — список доступных действий
> attack longsword goblin grunt        — действие + цель
> cast magic missile goblin shaman     — заклинание + цель
> dodge                                — тактическое действие
```

Или свободным текстом через мастера:
```
> бью мечом ближайшего гоблина
→ Master парсит → resolve_action()
```

**LLM (NPC в бою)** — tools:
```json
{"name": "attack", "params": {"weapon": "scimitar", "target": "player"}}
```

## Архитектура (где что живёт)

```
core/combat.py       — модели (Action, ActionResult, ActionError, CombatContext)
core/character.py    — Creature(Entity) с actions, Character(Creature)
rules/combat.py      — resolve_action(), roll_initiative()
service.py           — оркестрация, сборка nearby, применение результатов
```

## Открытые вопросы

- **Creature layer** — нужен ли отдельный слой для монстров, или они в NpcLayer?
- **CombatContext** — режим сессии (как talking_to) или отдельный объект на GameSession?
- **Дистанции** — зоны vs сетка vs "все рядом"
- **Spell slots / ресурсы** — когда добавлять
