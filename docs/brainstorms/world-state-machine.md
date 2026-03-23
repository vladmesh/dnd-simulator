# Жёсткая стейт-машина мира: инварианты и валидация

## Проблема

Сейчас валидация рассыпана по трём уровням, ни один из которых не является полным:

| Где сейчас | Что проверяет | Чего не хватает |
|---|---|---|
| `Round.run_round()` | `is_alive`, `active`, `in_combat` перед вызовом turn | Не защищает от вызова `execute_action` напрямую |
| `CombatManager.resolve_attack()` | attacker/target существуют, живы, в одной локации | Не проверяет что сейчас ход этого существа |
| `CombatManager.resolve_move()` | существо на карте, нет стены | Не проверяет бюджет движения |
| `Creature.execute_action()` | Ничего. Просто эмитит Event | Может вызываться для мёртвого, вне хода, с любым действием |
| Brains/LLM tools | Фильтрация инвалидных tools | Не является защитой — brain может вернуть что угодно |
| WS routes | Базовая валидация payload | Транспортный уровень, не бизнес-логика |

### Конкретные баги которые можно воспроизвести

1. **Мёртвый NPC действует** — `execute_action` не проверяет `is_alive`
2. **Действие вне хода** — нет проверки "сейчас ход этого существа"
3. **Combat-only действие в мирное время** — dodge/flee/move вне боя не блокируется
4. **Peaceful-only действие в бою** — say в бою (через execute_action напрямую)
5. **HP ниже 0** — `take_damage` клэмпит, но прямое `creature.current_hp = -5` ничто не блокирует
6. **Золото из воздуха** — `creature.gold += 1000` никем не контролируется
7. **Движение без бюджета** — move эмитит Event → resolve_move двигает, но бюджет проверяет только Round
8. **Dormant существо действует** — `execute_action` не проверяет `active`

---

## Предлагаемое решение: WorldInvariant + ActionValidator

Идея: **два уровня защиты**, каждый с чёткой ответственностью.

### Уровень 1: `ActionValidator` — предусловия действий

Централизованная проверка ДО выполнения действия. Вызывается из `Creature.execute_action()` перед эмитом Event.

```python
# rules/validation.py

@dataclass(frozen=True)
class ValidationError:
    code: str        # машинный код ("DEAD_ACTOR", "NOT_YOUR_TURN", ...)
    message: str     # человекочитаемое сообщение

class ActionValidator:
    """Проверяет предусловия действия. Чистые функции, без мутаций."""
    
    @staticmethod
    def validate(actor: Creature, action: Action, context: ActionContext) -> ValidationError | None:
        """Возвращает ошибку или None если всё ок."""
        for check in _CHECKS:
            error = check(actor, action, context)
            if error:
                return error
        return None
```

**ActionContext** — минимальный контейнер с тем, что нужно для валидации:

```python
@dataclass(frozen=True)
class ActionContext:
    is_combat: bool
    current_turn_entity_id: str | None  # чей сейчас ход (None = вне раунда)
    turn_budget: TurnBudget | None       # текущий бюджет (None = мирный)
    combat_state: CombatState | None     # для reach/position проверок
```

**Цепочка проверок** (порядок важен — от дешёвых к дорогим):

```python
_CHECKS = [
    check_actor_alive,       # мёртвые не действуют
    check_actor_active,      # dormant не действуют
    check_turn_ownership,    # действие только в свой ход
    check_action_mode,       # combat-only / peaceful-only фильтр
    check_budget,            # хватает ли ресурсов (actions/bonus/movement)
    check_reach,             # цель в досягаемости (если атака)
    check_target_valid,      # цель существует и жива (если нужна)
]
```

Каждая проверка — отдельная чистая функция в `rules/validation.py`:

```python
def check_actor_alive(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    if not actor.is_alive:
        return ValidationError("DEAD_ACTOR", "Dead creatures cannot act")
    return None

def check_action_mode(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    if ctx.is_combat and action.name in _PEACEFUL_ONLY:
        return ValidationError("WRONG_MODE", f"'{action.name}' not available in combat")
    if not ctx.is_combat and action.name in _COMBAT_ONLY:
        return ValidationError("WRONG_MODE", f"'{action.name}' not available outside combat")
    return None

_COMBAT_ONLY = frozenset({"dodge", "flee", "move", "dash"})
_PEACEFUL_ONLY: frozenset[str] = frozenset()  # пока пусто

# say — ЗАБЛОКИРОВАН в бою. Речь/флейвор в бою идёт через поле `description`
# любого действия: "с криком ЗА ОРДУ бросаюсь на врага" = attack(description=...)
_COMBAT_BLOCKED = frozenset({"say"})  # подмножество, проверяется в check_action_mode
```

### Уровень 2: `WorldInvariant` — пост-проверки состояния мира

Инварианты которые должны быть ВСЕГДА истинны. Проверяются ПОСЛЕ мутации (в debug/test mode), а для критичных — ПЕРЕД мутацией через сеттеры.

```python
# core/invariants.py

class WorldInvariant:
    """Набор инвариантов которые мир проверяет после каждого события."""
    
    @staticmethod
    def check_all(world: World) -> list[InvariantViolation]:
        violations = []
        for check in _INVARIANTS:
            v = check(world)
            if v:
                violations.append(v)
        return violations

_INVARIANTS = [
    # HP
    inv_hp_non_negative,          # current_hp >= 0 для всех существ
    inv_hp_within_max,            # current_hp <= max_hp
    # Gold
    inv_gold_non_negative,        # gold >= 0 для всех персонажей
    # Consistency
    inv_dead_not_in_combat,       # мёртвые не in_combat
    inv_dead_not_active_turn,     # мёртвые не в turn_order
    inv_combat_has_fighters,      # каждый CombatState имеет >= 2 participants
    inv_entity_location_exists,   # location_id существует в LocationGraph
    # Budget (только если сейчас раунд)
    inv_budget_non_negative,      # все поля бюджета >= 0
]
```

### Где вызывать

```
┌──────────────────────────────────────────┐
│           Round.run_combat_turn          │
│  ┌────────────────────────────────────┐  │
│  │  brain.choose_action() → Action    │  │
│  │          ↓                         │  │
│  │  ActionValidator.validate()  ←── Уровень 1 (перед исполнением)
│  │          ↓ (ok)                    │  │
│  │  creature.execute_action()         │  │
│  │          ↓                         │  │
│  │  emit_fn → handle_event            │  │
│  │          ↓                         │  │
│  │  WorldInvariant.check_all()  ←── Уровень 2 (после мутации, debug)
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

---

## Точки интеграции

### 1. `execute_action` получает context и validate

Сейчас `execute_action` только эмитит. Предлагаемое изменение:

```python
def execute_action(self, action: Action, emit_fn: EmitFn, context: ActionContext | None = None) -> ActionResult:
    # Уровень 1: предусловия
    if context:
        error = ActionValidator.validate(self, action, context)
        if error:
            return ActionResult(success=False, error=error.message)
    # ... далее как раньше
```

`context=None` сохраняет обратную совместимость; Round всегда передаёт context.

### 2. Round строит ActionContext и передаёт

```python
# В run_combat_turn, перед execute_action:
context = ActionContext(
    is_combat=True,
    current_turn_entity_id=creature.id,
    turn_budget=budget,
    combat_state=self._entities.get_combat(creature.location_id),
)
result = creature.execute_action(action, emit_fn, context)
```

### 3. WorldInvariant — опциональная проверка

```python
# В Round.run_round(), после каждого хода или в конце раунда:
if __debug__:  # бесплатно в production (python -O)
    violations = WorldInvariant.check_all(self._world)
    for v in violations:
        logger.error("INVARIANT VIOLATION: %s", v)
```

Или через `STRICT_MODE` env variable для полной проверки в production (с raise).

### 4. Защитные сеттеры для критичных полей

Для полей которые НИКОГДА не должны быть невалидны — property с проверкой:

```python
class Creature:
    @property
    def current_hp(self) -> int:
        return self._current_hp
    
    @current_hp.setter
    def current_hp(self, value: int) -> None:
        self._current_hp = max(0, min(value, self.max_hp))
```

Это **не** ломает `take_damage`/`heal` — они уже клэмпят. Но защищает от `creature.current_hp = -5` в другом коде.

---

## Порядок внедрения (инкрементальный)

### Фаза 1: Фундамент (минимальный, тестируемый) ← **начать с этого**

1. **`rules/validation.py`** — `ActionValidator` + `ActionContext` + 3 базовые проверки:
   - `check_actor_alive`
   - `check_actor_active` 
   - `check_action_mode`
2. **Интеграция в `Creature.execute_action`** — добавить `context` parameter
3. **Интеграция в `Round`** — передавать context при вызове execute_action
4. **Тесты** — unit tests на каждую проверку + integration test "мёртвый не атакует"

### Фаза 2: Budget enforcement

5. `check_budget` — перенести проверку бюджета из Round в validator
6. `check_reach` — перенести проверку reach из CombatManager в validator (дубль, потом убрать из CM)

### Фаза 3: Инварианты мира

7. **`core/invariants.py`** — `WorldInvariant` + базовые проверки (HP bounds, dead-not-in-combat)
8. **Защитные сеттеры** на `current_hp`, `gold`
9. **Интеграция** — проверка в Round (debug mode)

### Фаза 4: Расширение правил

10. `check_turn_ownership` — требует трекинга "чей ход" в Round (добавить `current_turn_id`)
11. `inv_gold_conservation` — при торговле: total gold before == total gold after
12. `inv_entity_location_exists` — location_id валидна в графе

---

## Принципы

1. **Чистые функции** — `rules/validation.py` не мутирует стейт, не зависит от World
2. **Fail-safe default** — неизвестные действия **проходят** (не блокировать геймплей)
3. **Инкрементальность** — каждая фаза самодостаточна, можно остановиться после любой
4. **Обратная совместимость** — `context=None` пропускает валидацию, старый код работает
5. **Тестируемость** — каждая проверка тестируется отдельно, без создания целого мира
6. **Debug vs Production** — инварианты дорогие, работают только в debug; validator — всегда

---

## Что НЕ входит (и почему)

- **ECS рефактор** — отдельная задача (`ecs-and-content.md`), не мешать
- **Modifier pipeline** — будет после derived stats, validator не зависит от него
- **Action dispatch** — validator проверяет предусловия, dispatch — маршрутизацию. Ортогональны
- **Торговля/инвентарь** — будущие правила ДОБАВЯТСЯ в `_CHECKS` и `_INVARIANTS` когда появятся

---

## Открытые вопросы для обсуждения

1. ~~**say в бою**~~ **РЕШЕНО:** `say` как отдельное действие в бою заблокирован. Речь и флейвор идут через поле `description` на любом действии. Например: `attack(target_id=..., description="с криком ЗА ОРДУ бросаюсь на врага")` или `dodge(description="припадаю на колено, прикрываясь щитом")`. Это естественнее и не тратит отдельный тик цикла.

2. **Idle (look/inspect) в бою** — тоже бесплатное. Информационные действия не тратят бюджет, но NPC может залипнуть в цикле look→look→look.

3. **Strict mode в production** — делать ли `raise` при нарушении инварианта, или только логирование? `raise` безопаснее, но может crash-нуть сессию. Компромисс: `raise` в тестах, `log.error` + авто-коррекция в production?

4. **Сеттеры vs explicit methods** — `creature.current_hp = x` с клэмпом или только через `take_damage()`/`heal()`? Сеттер безопаснее, но explicit methods читаемее для бизнес-логики.
