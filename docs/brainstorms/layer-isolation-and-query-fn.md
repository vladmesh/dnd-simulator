# Layer Isolation: убираем World из слоёв и сущностей

## Проблема

Сейчас `World` протекает вниз по стеку как god-object:

- `Creature.take_turn(world: World)` — каждая сущность получает прямую ссылку на World
- `Brain.choose_action(creature, world)` — оба brain'а (Rule/LLM) вызывают `world.query_layer()`
- `build_awareness(world, location_id)` — утилита для сбора контекста принимает World
- `EntitiesLayer._world` — мы только что дали слою back-reference на World, чтобы NPC могли тикать

Формально архитектура говорит "слои зависят вниз, не вверх", но на практике каждый NPC ходит в World → Geography, World → Politics через query_layer. World одновременно контейнер (владеет слоями) и шина (передаёт запросы между ними).

`WorldState` — мёртвая абстракция. Должен был быть read-only snapshot для слоёв, но:
- Содержит нетипизированные `dict[str, object]` blob'ы
- Реально используется только geography (читает time) и settlements (читает geography/politics state)
- Все серьёзные запросы идут через `query_layer`, а не через WorldState

## Чего хотим

1. Ни один слой не знает о существовании `World`
2. Ни одна сущность / brain не знает о существовании `World`
3. Межслойное общение через явные, типизированные контракты
4. EntitiesLayer может тикать NPC без back-reference на World
5. Brain получает готовые данные, а не god-object из которого сам тянет

## Опции

### Опция A: Query callback (минимальный рефакторинг)

World передаёт `query_fn: Callable[[str, Query], Answer]` — это `self.query_layer`, обёрнутый в callable. Слои и сущности видят только сигнатуру.

```python
QueryFn = Callable[[str, Query], Answer]

class Layer(ABC):
    def tick(self, delta: TimeDelta, query_fn: QueryFn) -> list[Event]
    def handle_event(self, event: Event, query_fn: QueryFn) -> ActionResult

class Brain(ABC):
    def choose_action(self, creature: Creature, awareness: dict, events: list[str]) -> Action
```

**Как работает:**
- `World.advance_time()` передаёт `self.query_layer` как query_fn в каждый tick()
- EntitiesLayer.tick() собирает awareness через query_fn, передаёт brain'у готовый dict
- Brain не запрашивает ничего — получает awareness + events, возвращает Action
- EntitiesLayer транслирует Action → Event, возвращает из tick()
- World пропагирует events как обычно

**Плюсы:**
- Минимум новых абстракций — один тип callback'а
- Brain становится чисто data-driven
- WorldState выпиливается
- Layer ABC меняется минимально (новый параметр)

**Минусы:**
- query_fn всё ещё нетипизированный (str layer_name + Query)
- Слой может запросить что угодно у кого угодно — нет compile-time гарантий
- handle_event тоже нужен query_fn (например, при resolve_attack нужно знать локацию)

### Опция B: Typed context object

Вместо callback'а — объект `TickContext` / `LayerContext` с конкретными методами:

```python
class LayerContext(Protocol):
    def get_time(self) -> GameDateTime: ...
    def get_weather(self, region_id: str) -> WeatherInfo: ...
    def get_region_info(self, region_id: str) -> RegionInfo: ...
    def get_entities_at(self, location_id: str) -> list[EntityInfo]: ...
    def region_of(self, location_id: str) -> str: ...
    # ... конкретные методы для каждого нужного запроса
```

**Плюсы:**
- Полная типизация, IDE автодополнение
- Явно видно что каждый слой потребляет

**Минусы:**
- Много boilerplate — каждый новый query = новый метод в Protocol
- По сути god-interface вместо god-object
- World всё равно имплементирует этот Protocol, просто через прослойку

### Опция C: Event-only (radical)

Слои вообще не запрашивают данные. Всё через events:
- Geography emit'ит WeatherChanged, TemperatureUpdated каждый tick
- Settlements слушают эти events и обновляют своё состояние
- Entities слушают все events и строят awareness из потока

**Плюсы:**
- Полная декуплинг — слои общаются только через event bus
- Легко добавлять новые слои — просто подписываешься на events

**Минусы:**
- Огромный рефакторинг — вся текущая pull-модель (query) заменяется на push-модель (events)
- Сложнее отлаживать — данные растекаются по event потоку
- Нужны "request-response" events для синхронных запросов (awareness) — это callback с лишними шагами
- Не подходит для "дай мне погоду прямо сейчас" — нужно кешировать последний event

### Опция D: Оставить как есть (pragmatic)

Текущий компромисс: EntitiesLayer хранит `_world`, NPC вызывают `world.query_layer()`.

**Плюсы:**
- Уже работает
- Минимум кода
- `take_turn(world)` — существующий паттерн, проверенный game_loop'ом

**Минусы:**
- Циклическая зависимость World ↔ EntitiesLayer
- Brain получает god-object
- Тяжело тестировать brain'ы без мока всего World
- Если добавятся новые слои, проблема усугубится

## Рекомендация

**Опция A (query callback)** — лучший баланс чистоты и прагматизма.

Порядок рефакторинга:
1. Выпилить `WorldState` — заменить на `query_fn` в Layer.tick() и handle_event()
2. Изменить `Brain.choose_action` сигнатуру — `(creature, awareness, events)` вместо `(creature, world)`
3. Перенести `build_awareness` в EntitiesLayer — собирает через query_fn
4. Перенести `execute_action` из Creature в EntitiesLayer — транслирует Action → Event
5. Убрать `_world` из EntitiesLayer
6. Убрать `world` из `take_turn` / `Creature` — brain получает данные, не запрашивает

Затрагиваемые файлы:
- `core/layer.py` — Layer ABC
- `core/world.py` — World, убрать WorldState
- `core/character.py` — Creature.take_turn, build_awareness
- `core/brain.py` — RuleBrain
- `llm/brain.py` — LlmBrain
- `layers/entities/layer.py` — EntitiesLayer.tick, execute_action
- `layers/geography/layer.py` — tick signature
- `layers/politics/layer.py` — tick signature
- `layers/settlements/layer.py` — tick signature
- Тесты всех слоёв
