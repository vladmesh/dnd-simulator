# Боевая система и действия

Обсуждение 2026-03-20.

## Уровни абстракции

### Механики (rules) — атомарный фундамент

Вся D&D сводится к трём типам бросков:
- **Attack roll** — d20 + modifier vs AC (nat 20 = крит, nat 1 = промах)
- **Ability check** — d20 + modifier vs DC (нет критов по RAW)
- **Saving throw** — d20 + modifier vs DC (механически = ability check)

Плюс бросок урона: dice expression → число, с удвоением дайсов при крите.

Это реализовано в `rules/dice.py` и `rules/checks.py`. Чистые функции, без состояния, детерминистичные через RNG injection.

### Боевые способности — данные на Creature

Что существо **умеет делать в бою**. Это не "действия" в широком смысле, а конкретный механический набор — атаки и спеллы:

```python
@dataclass(frozen=True)
class WeaponAttack:
    name: str           # "longsword", "bite", "claw"
    ability: Ability    # STR — к броску атаки и урону
    damage_dice: str    # "1d8", "2d6"
    reach: int = 5      # футы (5 = melee, 150 = longbow)
```

У волка — `[bite]`. У рыцаря — `[longsword, shield_bash]`. Это просто данные о том, какие параметры подставлять в чеки из rules/.

### "Действия" — два контекста

**Свободный режим** (narrative time) — нет action economy, нет порядка ходов:
- "Обыскиваю комнату" → Мастер (LLM) решает: ability_check(INT, dc=15)
- "Убеждаю стражника" → Мастер решает: ability_check(CHA, dc=12)
- "Бью по двери" → Мастер решает: attack_roll(STR_mod, door_ac), damage_roll("1d8+3")
- "Прячусь за бочку" → Мастер решает: ability_check(DEX, dc=10)

Мастер интерпретирует свободный текст и вызывает нужные механики. "Действие" тут — просто текст игрока.

**Бой** (structured time, раунды по 6 секунд) — action economy:
- 1 action, 1 bonus action, 1 reaction, movement за раунд
- Attack, Cast Spell, Dodge, Dash, Hide, Help — конкретный набор
- Резолюция автоматическая по правилам

Тактические действия (Dodge, Dash, Hide, Help) — не способности Creature, а правила боевой системы. Любое существо может Dodge.

## Валидация — постфактум

Creature знает свои атаки. Игрок/LLM выбирает атаку + цель свободно. Резолюция либо возвращает результат, либо ошибку:

- "Слишком далеко для рукопашной атаки"
- "Нет spell slot 3 уровня"
- "Вы оглушены и не можете действовать"

LLM получает ошибку → пробует другое действие. Игрок получает текст ошибки.

Без предварительной фильтрации — проще, дешевле, понятнее.

## Что уже реализовано

```
rules/dice.py       ✅  roll("2d6+3"), roll_d20(advantage/disadvantage)
rules/checks.py     ✅  attack_roll, ability_check, saving_throw, damage_roll
core/character.py   ✅  Entity → Creature (HP, AC, ability_scores) → Character → Player/Npc
```

## Следующий уровень: WeaponAttack + resolve

```
core/combat.py      — WeaponAttack (frozen dataclass), AttackResult, AttackError
rules/combat.py     — resolve_melee_attack(actor, weapon, target) → AttackResult | AttackError
                       resolve_ranged_attack(actor, weapon, target) → AttackResult | AttackError
```

resolve_melee_attack:
1. Валидация (цель существует, в досягаемости — пока все в регионе "рядом")
2. attack_roll(actor.ability_scores.modifier(weapon.ability), target.ac)
3. Если попал: damage_roll(weapon.damage_dice + modifier, critical=result.critical)
4. Возвращает AttackResult (hit/miss, damage, описание)

AttackResult — не привязан к "действиям" в целом, это конкретно результат атаки оружием. Чистый и узкий.

## Архитектура (где что живёт)

```
rules/
├── dice.py          ✅ дайсы
├── checks.py        ✅ три типа бросков + урон
└── combat.py        🔜 resolve_melee_attack, resolve_ranged_attack

core/
├── character.py     ✅ Entity → Creature → Character → Player/Npc
└── combat.py        🔜 WeaponAttack, AttackResult, AttackError
```

Позже:
- Боевой режим (CombatContext, инициатива, порядок ходов) — в service или отдельный модуль
- Заклинания — отдельная модель рядом с WeaponAttack
- Мастер вызывает ability_check/saving_throw напрямую для небоевых ситуаций

## Открытые вопросы

- **Creature layer** — нужен ли отдельный слой для монстров, или они в NpcLayer?
- **CombatContext** — режим сессии (как talking_to) или отдельный объект?
- **Дистанции** — зоны vs сетка vs "все в регионе рядом"
- **Spell slots / ресурсы** — когда добавлять
- **Инвентарь** — оружие как предмет генерирует WeaponAttack с нужными параметрами
