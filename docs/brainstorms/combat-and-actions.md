# Боевая система и действия

Обсуждение 2026-03-20.

## Ключевое разделение: два режима игры

**Свободный режим** (narrative time) — нет action economy, нет порядка ходов.
Игрок описывает намерение свободным текстом. Мастер (LLM) интерпретирует и вызывает
нужные механики из rules/:
- "Обыскиваю комнату" → `ability_check(INT, dc=15)`
- "Убеждаю стражника" → `ability_check(CHA, dc=12)`
- "Бью по двери" → `attack_roll(STR_mod, door_ac)` + `damage_roll("1d8+3")`

**Бой** (structured time) — раунды по 6 секунд, action economy:
- 1 action, 1 bonus action, 1 reaction, movement за раунд
- Attack, Cast Spell, Dodge, Dash, Hide, Help — конкретный набор
- Резолюция автоматическая по правилам

## Механики (rules/) — атомарный фундамент

Вся D&D сводится к трём типам бросков + урон:
- **Attack roll** — d20 + modifier vs AC (nat 20 = крит, nat 1 = промах)
- **Ability check** — d20 + modifier vs DC (нет критов по RAW)
- **Saving throw** — d20 + modifier vs DC
- **Damage roll** — dice expression → число, удвоение дайсов при крите

Реализовано: `rules/dice.py`, `rules/checks.py`.

## Боевые способности — данные на Creature

Что существо **умеет в бою** — не "действия" в широком смысле, а конкретные атаки:

```python
@dataclass(frozen=True)
class WeaponAttack:
    name: str           # "longsword", "bite"
    ability: Ability    # STR — к броску атаки и урону
    damage_dice: str    # "1d8", "2d6"
    reach: int = 5      # футы (5 = melee, 150 = longbow)
```

Это просто данные — какие параметры подставлять в чеки из rules/.

Тактические действия (Dodge, Dash, Hide) — не способности Creature, а правила боевой
системы. Любое существо может Dodge.

## Валидация — постфактум

Creature знает свои атаки. Игрок/LLM выбирает атаку + цель свободно. Резолюция либо
возвращает результат, либо ошибку ("слишком далеко", "оглушены"). Без предварительной
фильтрации — проще, дешевле, понятнее.

## HP мутация

rules/ — чистые функции, не мутируют стейт. `take_damage()` / `heal()` / `is_alive` —
методы на Creature. Оркестратор (service) вызывает resolve → применяет результат через
методы на Creature → генерирует события (ENTITY_DIED).

## Что реализовано

```
rules/dice.py       ✅  roll("2d6+3"), roll_d20(advantage/disadvantage)
rules/checks.py     ✅  attack_roll, ability_check, saving_throw, damage_roll
core/character.py   ✅  Entity → Creature (HP, AC, ability_scores) → Character → Player/Npc
```
