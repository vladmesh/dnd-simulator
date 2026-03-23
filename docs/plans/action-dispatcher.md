# Action Dispatcher — централизованное исполнение действий

## Контекст

Два брейншторма независимо пришли к одной проблеме:

- [`docs/brainstorms/world-state-machine.md`](../brainstorms/world-state-machine.md) — валидация рассыпана по Round, CombatManager, Creature. `execute_action` вызывается без проверок; мёртвые, dormant, вне-хода существа могут действовать.
- [`docs/brainstorms/ecs-and-content.md`](../brainstorms/ecs-and-content.md) — `execute_action` — if/elif монолит на 8 веток. Не масштабируется: equip/unequip/use_item/cast потребуют ещё больше веток. Action Dispatch (п. 2b) описан как реестр handler-ов.

Phase 1 из world-state-machine уже сделана: `validate_action()` + `ActionContext` + 3 проверки (alive, active, action_mode) живут в `rules/validation.py`, вызываются из Round.

## Проблема

Сейчас исполнение действия размазано по трём местам:

| Место | Что делает | Что не так |
|---|---|---|
| `Round` (round.py) | Валидация (validate_action), budget check/consume, dash special case, wait special case | Round знает про конкретные действия (dash, wait). Бюджет проверяется и списывается в разных точках |
| `Creature.execute_action()` (character.py) | if/elif маппинг action.name → Event emission | Монолит. Нет валидации. Вызывается напрямую — любой caller обходит проверки Round |
| `CombatManager` (combat_manager.py) | resolve_attack, resolve_move — фактическое исполнение | Дублирует проверки (alive, same location). Не проверяет бюджет и turn ownership |

Проблемы этой схемы:
1. **Нет единой точки входа.** `execute_action` можно вызвать без валидации.
2. **Round знает слишком много.** Dash, wait, budget — это не ответственность оркестратора.
3. **Creature — и данные, и исполнитель.** `execute_action` превращает Creature в god object.
4. **Нет расширяемости.** Новое действие = новая ветка в if/elif + правки в Round.

## Решение: ActionDispatcher

Единый объект, через который проходят ВСЕ действия. Validate → execute → return result.

### Принципы

- **Атомарность без роллбэков.** Валидация до мутации. Если ошибка — мир не менялся. Если ok — действие применилось полностью.
- **Round — тупой цикл.** Опрашивает brain-ы, передаёт Action в dispatcher, двигает время. Не знает что такое "атака" или "dash".
- **Creature — данные + brain.** Не исполнитель. `execute_action` удаляется.
- **Handler — чистая функция** в `rules/` или `service/`. Получает actor, action, world/entities, возвращает ActionResult.
- **Два уровня фильтрации.** Мягкий (awareness — скрыть невозможные действия от brain/UI) и жёсткий (dispatcher — не дать исполнить невалидное). Общая логика — одна функция `is_available()`, два потребителя.

### Текущий API (после Фаз 0–1)

```python
# core/action.py
class ActionType(StrEnum):
    IDLE = "idle"
    SAY = "say"
    ATTACK = "attack"
    DODGE = "dodge"
    FLEE = "flee"
    MOVE = "move"
    DASH = "dash"
    WAIT = "wait"
    END_TURN = "end_turn"
    SKIP = "skip"

@dataclass(frozen=True)
class Action:
    name: ActionType
    params: dict[str, object] = field(default_factory=dict)
```

```python
# service/action_dispatcher.py
ActionHandler = Callable[[Creature, Action, EmitFn, ActionContext, World], ActionResult]

class ActionDispatcher:
    def __init__(self, world: World) -> None: ...

    @property
    def world(self) -> World: ...

    def register(self, action_name: ActionType, handler: ActionHandler) -> None: ...
    def dispatch(self, actor, action, ctx, emit_fn) -> ActionResult: ...
    def has_handler(self, action_name: ActionType) -> bool: ...

def create_dispatcher(world: World) -> ActionDispatcher: ...
```

```python
# rules/action_handlers.py — все handler-ы
# Сигнатура: (actor, action, emit_fn, ctx, world) -> ActionResult
def handle_idle(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_say(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_attack(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_dodge(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_flee(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_move(actor, action, emit_fn, ctx, world) -> ActionResult: ...
def handle_dash(actor, action, emit_fn, ctx, world) -> ActionResult: ...
```

---

## Фазы внедрения

### Фаза 0: ActionDispatcher scaffold + миграция idle/say ✅

**Цель:** создать dispatcher, зарегистрировать простейшие handler-ы, проверить что архитектура работает.

**Что сделано:**
1. ✅ `service/action_dispatcher.py` — ActionDispatcher с `dispatch()`, `register()`, `has_handler()`.
2. ✅ `ActionContext.turn_budget: TurnBudget | None` добавлен.
3. ✅ Handler-ы для idle и say вынесены в `rules/action_handlers.py`.
4. ✅ Round: `_execute_action()` — роутит через dispatcher или fallback на `creature.execute_action()`.
5. ✅ 17 unit-тестов в `test_action_dispatcher.py`.

**Отклонения от плана:**
- `is_available()` не реализован (stub не нужен — отложен до Фазы 3).
- `emit_fn` передаётся в `dispatch()` per-call, а не хранится на dispatcher. Причина: emit_fn создаётся World-ом заново каждый раунд, хранить ссылку = stale reference.
- Открытый вопрос #3 (peaceful turn loop) — решён без изменений: Round по-прежнему использует `ends_peaceful_turn()` из `rules/actions.py`. Dispatcher не знает про turn structure.

### Фаза 1: Миграция боевых действий ✅

**Цель:** перенести attack, dodge, flee, move, dash в dispatcher.

**Что сделано:**
1. ✅ Handler-ы для attack, dodge, flee, move, dash в `rules/action_handlers.py`.
2. ✅ Dash handler мутирует `ctx.turn_budget.movement_remaining` напрямую (открытый вопрос #1 → вариант (a)).
3. ✅ Budget check/consume полностью в dispatcher. Round не вызывает `can_afford`/`consume`.
4. ✅ Round упрощён: убраны manual validation, dash special case, manual budget check/consume. Один вызов `_execute_action()` на каждое действие.
5. ✅ Round всегда создаёт dispatcher (default `create_dispatcher()`), не требует явной передачи.
6. ✅ 29 unit-тестов (было 17, добавлены тесты для combat handlers и budget).

**Отклонения от плана:**
- Handler signature: `(Creature, Action, EmitFn, ActionContext, World)` вместо `(Creature, Action, EmitFn, QueryFn)` из оригинального плана. QueryFn не нужен. Вместо него — ActionContext (для budget/dash) и World (для будущих handler-ов).
- Dispatcher stateful: `ActionDispatcher(world)` держит ссылку на World, передаёт handler-ам. В оригинальном плане предлагался `__init__(world, entities)` — вместо этого только World, т.к. из World доступны все слои.
- `action_cost("dash")` перенесён в `_STANDARD_ACTIONS` (был hardcoded `DASH_ACTION_COST`). Теперь `action_cost()` корректно возвращает стоимость dash без special case.
- `Creature.execute_action()` ещё НЕ удалён — используется как fallback для wait (Фаза 2). Plan говорил "Round вызывает только dispatcher", но wait остаётся legacy.
- Circular import (`round.py` ↔ `service/`) решён через `TYPE_CHECKING` guard + lazy import `create_dispatcher` в `Round.__init__`.

### Вне плана: ActionType enum ✅

**Не было в плане, сделано по ходу.**

`Action.name` был `str` — это приводило к уродливому коду вроде `action.name == "skip" or action == SKIP`. Введён `ActionType(StrEnum)` в `core/action.py`. Миграция затронула весь codebase (~15 src файлов, 6 test файлов). Строковый парсинг только на границах: `ActionType(tc.name)` в LLM brain, `ActionType(str(...))` в WS routes.

### Фаза 2: Миграция wait + удаление execute_action ✅

**Цель:** перенести последнее действие, убрать `execute_action` с Creature.

**Что сделано:**
1. ✅ `handle_wait` в `rules/action_handlers.py` — логика из `Round._handle_wait()` (travel + plain wait).
2. ✅ `_handle_wait` удалён из Round.
3. ✅ `Creature.execute_action()` удалён. Creature — чистые данные + brain.
4. ✅ WS routes / GameService не вызывали `execute_action` напрямую — проверено.
5. ✅ Fallback path в `Round._execute_action()` убран — всегда через dispatcher.
6. ✅ Тесты обновлены: `test_combat_awareness`, `test_npc_tools`, `test_double_turn_bug` переведены на dispatcher/handlers. 4 новых теста для `handle_wait`.
7. ✅ 33 unit-теста в `test_action_dispatcher.py` (было 29).

**Результат:** Creature — чистые данные + brain. Единственная точка исполнения — dispatcher. Все 8 action types (idle, say, attack, dodge, flee, move, dash, wait) зарегистрированы.

### Фаза 3: is_available + awareness фильтрация ✅

**Цель:** awareness показывает только доступные действия.

**Что сделано:**
1. ✅ `dispatcher.get_available_actions(actor, ctx)` — переиспользует `validate_action` + `action_cost` + `can_afford` + `has_handler`. Возвращает `list[ActionType]`.
2. ✅ `available_actions: list[ActionType]` добавлен в `PeacefulAwareness` и `CombatAwareness`.
3. ✅ Round заполняет `awareness.available_actions` перед вызовом brain (combat + peaceful turns).
4. ✅ LlmBrain фильтрует tools по `awareness.available_actions` — LLM не видит недоступных действий.
5. ✅ `_awareness_to_dict` в session.py сериализует `available_actions` в строки для WS/JSON.
6. ✅ 7 новых тестов в `test_action_dispatcher.py::TestGetAvailableActions`.

**Отклонения от плана:**
- Метод назван `get_available_actions` (возвращает список), а не `is_available` (проверяет один тип). Удобнее — один вызов вместо N.
- Заполняет Round, а не `build_awareness` в EntitiesLayer. Причина: EntitiesLayer не знает про dispatcher (и не должен — layers depend down, dispatcher в service/).
- PlayerBrain не изменён — `available_actions` уже попадает в WS через `_awareness_to_dict`, UI может использовать. Defense in depth: dispatcher всё равно валидирует.

**Результат:** LLM и UI не предлагают dodge вне боя, attack на мёртвого, move без бюджета. Dispatcher всё равно валидирует (defense in depth).

### Фаза 4: Budget enforcement в validator

**Цель:** перенести `check_budget` и `check_reach` из ad-hoc проверок в цепочку `_CHECKS` валидатора.

**Шаги:**
1. `check_budget` — добавить в `rules/validation.py`. Использует `ctx.turn_budget`.
2. `check_reach` — цель в досягаемости (через `ctx.combat_state` или BattleMap). Расширить ActionContext.
3. `check_target_valid` — цель существует и жива.
4. Убрать дублирующие проверки из CombatManager (alive, same location) — dispatcher уже проверил.

**Результат:** validator — полная цепочка предусловий. CombatManager — только исполнение механик (damage roll, move resolution).

### Фаза 5: ActionProvider (подготовка к инвентарю)

**Цель:** динамические источники действий — не только хардкод, но и экипировка, фичи класса.

**Шаги:**
1. Определить `ActionProvider` protocol — `get_actions(creature, ctx) -> list[ActionDef]`.
2. Базовые действия (dodge, dash, flee, idle, say, wait) — `BaseActionProvider`.
3. Weapon actions (attack с параметрами оружия) — `WeaponActionProvider` (будущее, когда появится инвентарь).
4. `dispatcher.get_available_actions(creature, ctx)` собирает из всех провайдеров + фильтрует через `is_available`.

**Результат:** система готова к инвентарю (п. 2a из ecs-and-content) и заклинаниям (п. 3a).

---

## Что не входит

- **ECS рефакторинг** — dispatcher работает с текущей иерархией Entity/Creature/Character. ECS — ортогональная задача.
- **Modifier pipeline / derived stats** — dispatcher не зависит от них. Когда появятся, handler-ы будут использовать `effective_ac()` вместо `creature.ac`.
- **Роллбэки / event sourcing** — validate-before-execute достаточно. Если понадобится undo, это отдельная система поверх dispatcher.
- **WorldInvariant** — пост-проверки из world-state-machine Phase 3. Ортогональны dispatcher-у, могут вызываться после dispatch в debug mode.

## Решённые вопросы

1. **✅ Dash: handler мутирует budget напрямую.** Вариант (a) — handler получает budget через `ctx.turn_budget` и мутирует `movement_remaining`. Проще, не требует нового поля в ActionResult.

2. **✅ Wait: handler нуждается в World.** Решено: `ActionDispatcher(world)` держит ссылку на World и передаёт его всем handler-ам как аргумент. Замыкания не нужны.

3. **✅ Peaceful turn loop.** Round по-прежнему использует `ends_peaceful_turn()`. Dispatcher не знает про turn structure — это ответственность Round.
