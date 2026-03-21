# Layer Isolation: убираем World из слоёв и сущностей

> **СТАТУС: ПОГЛОЩЕНО / РЕАЛИЗОВАНО** (Архитектура внедрена согласно `plans/layer-isolation.md`)

## Проблема

Сейчас `World` протекает вниз по стеку как god-object:

- `Creature.take_turn(world: World)` — каждая сущность получает прямую ссылку на World
- `Brain.choose_action(creature, world)` — оба brain'а (Rule/LLM) вызывают `world.query_layer()`
- `build_awareness(world, location_id)` — утилита для сбора контекста принимает World
- `EntitiesLayer._world` — слой хранит back-reference на World, чтобы NPC могли тикать

Формально архитектура говорит "слои зависят вниз, не вверх", но на практике каждый NPC ходит в World → Geography, World → Politics через query_layer. World одновременно контейнер (владеет слоями) и шина (передаёт запросы между ними).

`WorldState` — мёртвая абстракция:
- Содержит нетипизированные `dict[str, object]` blob'ы
- Реально используется только geography (читает time) и settlements (читает geography/politics state)
- Все серьёзные запросы идут через `query_layer`, а не через WorldState

## Решение: два callback'а + push events

### Принципы

1. **Ни один слой и ни одна сущность не знают о существовании `World`**
2. **Query только вниз по стеку** — слой может запрашивать данные только у слоёв ниже себя (geography ← politics ← settlements ← entities)
3. **Влияние вверх — через push events** — если нижнему слою нужно передать данные верхнему, он emit'ит event в своём tick, World пропагирует, верхний слой ловит в handle_event и кеширует
4. **Brain — чистая стратегия** — получает готовые данные (awareness + events), возвращает Action, без side effects
5. **EntitiesLayer оркестрирует** цикл "собрать контекст → brain решает → транслировать Action в Event"

### Два callback'а

World при вызове tick/handle_event создаёт для каждого слоя пару callback'ов:

```python
QueryFn = Callable[[str, Query], Answer]   # запросить данные у другого слоя
EmitFn  = Callable[[Event], ActionResult]  # отправить событие в мир
```

#### query_fn — запрос данных вниз

```python
def _make_query_fn(self, caller_layer: str) -> QueryFn:
    def query_fn(target_layer: str, query: Query) -> Answer:
        if target_layer == caller_layer:
            raise LayerError(f"{caller_layer} cannot query itself through World")
        if self._layer_index(target_layer) >= self._layer_index(caller_layer):
            raise LayerError(f"{caller_layer} cannot query {target_layer} (same level or above)")
        return self.query_layer(target_layer, query)
    return query_fn
```

Валидация в одном месте:
- Нельзя запрашивать себя
- Нельзя запрашивать слой на том же уровне или выше
- Слой, который не существует — ошибка
- Можно добавить логирование для дебага

#### emit_fn — отправка событий в мир

```python
def _make_emit_fn(self, caller_layer: str) -> EmitFn:
    def emit_fn(event: Event) -> ActionResult:
        if event.source_layer != caller_layer:
            raise LayerError(f"{caller_layer} emits event as {event.source_layer}")
        return self.handle_event(event)
    return emit_fn
```

Валидация:
- source_layer в событии должен совпадать с вызывающим слоем

### Push events для данных вверх по стеку

Когда верхнему слою нужны данные от нижнего (пример: Politics нужна сила нации из Settlements для войны):

1. Settlements в своём tick() emit'ит event:
   ```python
   Event(SETTLEMENT_CENSUS, data={"nation_id": "X", "population": 5000, "military": 200})
   ```
2. World пропагирует event во все слои (механизм `_propagate_events` уже есть)
3. Politics ловит в handle_event и кеширует данные
4. Когда Politics тикает — данные уже на месте

Это работает потому что слои тикают снизу вверх: Geography → Politics → Settlements → Entities. Settlements тикает раньше, чем Politics успеет воевать в следующий раз.

### Изменения в Layer ABC

```python
class Layer(ABC):
    def tick(self, delta: TimeDelta, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]
    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult
    def query(self, query: Query) -> Answer          # без изменений
    def get_state(self) -> dict[str, object]          # без изменений
    def load_state(self, state: dict[str, object])    # без изменений
```

### Изменения в сущностях и brain'ах

```python
class Brain(ABC):
    def choose_action(self, creature: Creature, awareness: dict, events: list[str]) -> Action

class Creature:
    # take_turn и execute_action уходят из Creature
    # EntitiesLayer берёт на себя оркестрацию
```

#### PlayerBrain — игрок как обычный brain

Игрок ничем не отличается от NPC на уровне архитектуры. Единственная разница — способ принятия решений:
- RuleBrain — дерево правил
- LlmBrain — LLM через tool use
- **PlayerBrain** — ввод из консоли (CLI) или API-запрос (REST)

`PlayerBrain.choose_action()` блокируется (CLI) или ждёт команду из очереди (API) и возвращает Action. Дальше EntitiesLayer обрабатывает его ровно так же, как NPC action.

`wait` = `idle` — никакой специальной логики.

Это открывает:
- **Мультиплеер** — несколько существ с PlayerBrain
- **Персонажи мастера** — DM переключается между brain'ами в рантайме

### EntitiesLayer — оркестрация

EntitiesLayer.tick():
1. Собирает awareness через query_fn (погода, регион, поселения, политика)
2. Собирает events из location_log
3. Вызывает brain.choose_action(creature, awareness, events) — brain возвращает Action
4. Транслирует Action → Event через emit_fn
5. Возвращает список событий

### location_graph

Сейчас живёт на World, используется для `region_of(location_id)` и `get(location_id).name`.

Логически это данные Geography слоя. Варианты:
- Переносим в Geography, доступ через query: `query_fn("geography", Query("region_of", {location_id}))`
- Или EntitiesLayer хранит ссылку на LocationGraph напрямую (передаётся при создании)

Решить при реализации — зависит от того, насколько часто дёргается.

### game_loop

Сейчас game_loop сам итерирует creature и вызывает take_turn(world). После рефакторинга:
- Combat turn order (инициатива) уходит внутрь EntitiesLayer
- game_loop только вызывает `world.advance_time()` в цикле
- EntitiesLayer.tick() внутри сам гоняет всех creatures в правильном порядке (initiative для боя, default для мирных)

### WorldState

Выпиливается полностью. Всё что слоям нужно — доступно через query_fn.

## Порядок рефакторинга

1. Добавить `QueryFn`, `EmitFn` типы в core/models.py
2. Изменить Layer ABC — tick() и handle_event() принимают query_fn + emit_fn
3. World создаёт callback'и с валидацией, передаёт в tick/handle_event
4. Обновить Geography, Politics, Settlements — новая сигнатура tick/handle_event
5. Settlements: добавить push events (census) для Politics
6. Brain ABC — новая сигнатура: `(creature, awareness, events) -> Action`
7. Перенести build_awareness в EntitiesLayer, переписать на query_fn
8. Перенести execute_action из Creature в EntitiesLayer, переписать на emit_fn
9. Убрать take_turn из Entity/Creature
10. Убрать `_world` / `set_world` из EntitiesLayer
11. Выпилить WorldState
12. Добавить PlayerBrain (CLI + API варианты)
13. Упростить game_loop — только advance_time
14. Перенести combat turn order в EntitiesLayer.tick()
15. Обновить тесты

## Затрагиваемые файлы

- `core/models.py` — QueryFn, EmitFn типы
- `core/layer.py` — Layer ABC
- `core/world.py` — World: callback'и с валидацией, убрать WorldState
- `core/character.py` — убрать take_turn, execute_action, build_awareness, perceive_by_id(world)
- `core/brain.py` — RuleBrain: новая сигнатура, добавить PlayerBrain
- `llm/brain.py` — LlmBrain: новая сигнатура
- `layers/entities/layer.py` — оркестрация: awareness + brain + emit + combat turn order
- `layers/geography/layer.py` — tick/handle_event сигнатура, возможно location_graph
- `layers/politics/layer.py` — tick/handle_event сигнатура, handle census events
- `layers/settlements/layer.py` — tick/handle_event сигнатура, emit census
- `game_loop.py` — упростить до advance_time loop
- `service.py` — player commands через PlayerBrain queue вместо прямого execute_action
- `core/player.py` — PlayerCharacter: убрать специальную логику, добавить PlayerBrain
- Все тесты слоёв
