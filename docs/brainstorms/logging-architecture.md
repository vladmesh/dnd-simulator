# Logging Architecture Brainstorm

## Текущее состояние

14 файлов используют `import logging` со стандартным `logging.getLogger("dnd_simulator.xxx")`. Конфигурация — через `LOG_LEVEL` env var в `app.py` (default: WARNING). Формат простой: `%(levelname)s %(name)s: %(message)s`. Теги вручную в квадратных скобках: `[Round]`, `[LLM]`, `[NPC:Goblin]`, `[FastForward]`.

**Проблемы:**
- Нет структуры — плоский поток текста
- Нет session/entity/layer контекста в метаданных (только в тексте лога)
- Нет файлового вывода
- Нет навигации по логическим группам
- LLM-контексты (промпты, ответы) не логируются полностью

---

## Концепция: Structured Contextual Logging

### Ключевая идея — `structlog` + `contextvars`

Использовать **[structlog](https://www.structlog.org/)** вместо стандартного `logging`. Structlog нативно поддерживает:
- **Structured output** — каждый лог это dict/JSON, а не строка
- **Context binding** — attach session_id, entity_id, layer, phase при входе в scope
- **Processors pipeline** — фильтрация, обогащение, маршрутизация
- **stdlib integration** — работает поверх стандартного `logging`, не ломает сторонние библиотеки

### Альтернативы и почему structlog лучше

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| **stdlib logging + filters** | Уже в проекте, zero deps | Нет структуры, сложно делать context binding, нет JSON out of box |
| **structlog** | Structured JSON, context binding, processors, Grafana-ready | Новая зависимость, миграция |
| **loguru** | Красивый вывод в консоль, ротация файлов | Менее гибкий для structured logging, хуже для Grafana/Loki |
| **OpenTelemetry** | Стандарт индустрии, spans, metrics | Overkill для текущего масштаба, сложный setup |

**Рекомендация: `structlog`** — лучший баланс. Если позже понадобится OTel, structlog легко к нему подключается через processor.

---

## Архитектура

### Уровни конфигурации

```
--debug       → всё на DEBUG, structured JSON в файлы + pretty в консоль
--log-level X → стандартный уровень, только консоль
(default)     → WARNING, минимальный вывод
```

### Context Stack (через contextvars)

При входе в каждый scope привязывается контекст, который автоматически попадает в каждый лог:

```python
# Автоматически добавляется к каждому log entry
{
    "session_id": "abc-123",
    "entity_id": "goblin_01",
    "entity_name": "Грок",
    "layer": "entities",
    "phase": "combat_turn",      # combat_turn | peaceful_turn | tick | event_handling
    "location_id": "tavern",
    "round_number": 5,
    "turn_number": 3,
    "timestamp": "2026-03-24T11:52:53",
    "game_time": "Year 1, Month 3, Day 15, 14:30"
}
```

**Как это выглядит в коде:**

```python
import structlog

logger = structlog.get_logger()

# На уровне session — bind один раз
log = logger.bind(session_id=session.session_id)

# На уровне round
log = log.bind(round_number=round_num, phase="combat_turn")

# На уровне creature turn
log = log.bind(entity_id=creature.id, entity_name=creature.name)

# Потом просто:
log.info("action_executed", action="attack", target="orc_01", damage=12)
# → выведет ВСЕ привязанные поля + action/target/damage
```

### Теги и группы

Каждый лог имеет **domain** (логическая область) и **event** (что случилось):

| Domain | Events | Когда |
|--------|--------|-------|
| `llm` | `request`, `response`, `retry`, `token_usage` | Каждый LLM-вызов |
| `llm.context` | `system_prompt`, `user_prompt`, `messages` | Содержимое контекста LLM |
| `brain` | `choose_action`, `score_targets`, `fallback` | Решение мозга |
| `action` | `validate`, `dispatch`, `execute`, `budget_consume` | ActionDispatcher |
| `combat` | `initiative_roll`, `turn_start`, `turn_end`, `combat_start`, `combat_end` | Боевая система |
| `entity` | `field_change`, `hp_change`, `condition_add`, `condition_expire`, `activate`, `dormant` | Мутации entity |
| `world` | `advance_time`, `tick`, `event_propagate` | World/Layer тики |
| `layer.*` | `query`, `handle_event`, `tick` | Per-layer логирование |
| `round` | `start`, `end`, `fast_forward` | Round orchestrator |
| `transport` | `ws_connect`, `ws_disconnect`, `request`, `response` | API/WS |

---

## Режим консоли (для Grafana/Loki)

### Формат: JSON lines

```json
{"timestamp":"2026-03-24T11:52:53.123Z","level":"info","domain":"action","event":"execute","session_id":"abc-123","entity_id":"goblin_01","entity_name":"Грок","action":"attack","target":"orc_01","damage":12,"round":5}
```

**Почему JSON lines:**
- Grafana Loki/Promtail парсят из коробки
- `jq` для фильтрации в терминале: `cat log.jsonl | jq 'select(.domain=="llm")'`
- Подхватывается Docker logging driver → Loki/ELK без доп. настроек

### Dev-режим: Pretty console

Когда `--debug` без Docker — вывод через structlog `ConsoleRenderer`:

```
11:52:53 [info    ] action_executed  session=abc-123 entity=Грок action=attack target=orc_01 damage=12 round=5
11:52:53 [debug   ] llm_request      session=abc-123 entity=Грок tokens_in=450 model=gpt-4o
11:52:54 [info    ] llm_response     session=abc-123 entity=Грок tool=attack(target=orc_01) elapsed=823ms tokens=450→32
```

Цвета: level цветной, domain жирный, ключи серые, значения белые.

---

## Режим файлов (для навигации)

### Файловая структура

```
logs/
└── session_abc-123/
    ├── full.jsonl                    # всё, полный поток
    ├── llm/
    │   ├── all.jsonl                 # все LLM вызовы
    │   ├── goblin_01.jsonl           # LLM вызовы для конкретного entity
    │   └── contexts/
    │       ├── goblin_01_round5_turn3.json   # полный контекст (промпт + ответ)
    │       └── merchant_02_round5_turn1.json
    ├── entities/
    │   ├── goblin_01.jsonl           # все логи для этого entity
    │   ├── merchant_02.jsonl         # ...
    │   └── field_changes.jsonl       # все мутации полей
    ├── combat/
    │   ├── tavern_round5.jsonl       # бой в локации "таверна", раунд 5
    │   └── summary.jsonl             # старт/конец боёв
    ├── world/
    │   ├── ticks.jsonl               # все тики всех слоёв
    │   └── events.jsonl              # все events
    └── actions/
        ├── all.jsonl                 # все действия
        └── failed.jsonl              # только неудачные
```

**Денормализация**: один лог-entry может записаться в несколько файлов. Например, `[entity=goblin_01, domain=llm]` попадёт и в `llm/goblin_01.jsonl`, и в `entities/goblin_01.jsonl`, и в `full.jsonl`.

### Реализация: Custom Processor / Handler

```python
class FileDispatchHandler:
    """Маршрутизирует log entries в нужные файлы на основе domain и context."""
    
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._files: dict[str, IO] = {}
    
    def __call__(self, logger, method_name, event_dict):
        session_id = event_dict.get("session_id", "unknown")
        domain = event_dict.get("domain", "general")
        entity_id = event_dict.get("entity_id")
        
        targets = [f"session_{session_id}/full.jsonl"]
        
        # Domain-based routing
        if domain.startswith("llm"):
            targets.append(f"session_{session_id}/llm/all.jsonl")
            if entity_id:
                targets.append(f"session_{session_id}/llm/{entity_id}.jsonl")
        
        if entity_id:
            targets.append(f"session_{session_id}/entities/{entity_id}.jsonl")
        
        # ... write to all targets
```

### LLM-контексты — отдельные файлы

Полные промпты + ответы слишком большие для JSONL. Пишутся как отдельные JSON-файлы:

```json
// logs/session_abc-123/llm/contexts/goblin_01_round5_turn3.json
{
  "timestamp": "2026-03-24T11:52:53.123Z",
  "entity_id": "goblin_01",
  "entity_name": "Грок",
  "round": 5,
  "turn": 3,
  "mode": "combat",
  "messages": [
    {"role": "system", "content": "You are Грок, a goblin warrior..."},
    {"role": "user", "content": "What happened since your last turn..."}
  ],
  "tools": [...],
  "response": {
    "tool_call": {"name": "attack", "arguments": {"target": "orc_01"}},
    "elapsed_ms": 823,
    "tokens_in": 450,
    "tokens_out": 32
  }
}
```

---

## Entity Field Tracking

Для отслеживания мутаций полей entity — специальный трекер:

```python
class EntityFieldTracker:
    """Логирует изменения полей entity."""
    
    def track(self, entity_id: str, field: str, old_value, new_value):
        if old_value != new_value:
            logger.info(
                "field_changed",
                domain="entity",
                entity_id=entity_id,
                field=field,
                old=old_value,
                new=new_value,
            )
```

**Варианты реализации:**
1. **Явные вызовы** — в каждом месте где меняется поле, вызывать tracker. Просто, но много ручной работы.
2. **Property descriptors** — `@tracked_property` декоратор на полях Creature/Character. Автоматически логирует set. Элегантно, но добавляет overhead.
3. **Snapshot diff** — делать snapshot entity перед/после action, сравнивать diff. Самое полное, но дороже по CPU.

**Рекомендация:** (2)

---

## Миграция от текущего logging

### Подход: сразу нахуй сносим и делаем нормально. Мы в процессе активной разработки, нам нечего ломать.

### Конфигурация (один раз, в entry point)

```python
# dnd_simulator/logging_config.py
import structlog

def configure_logging(debug: bool = False, log_dir: Path | None = None):
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if debug:
        if log_dir:
            processors.append(FileDispatchProcessor(log_dir))
        # Console: pretty for tty, JSON for pipe/docker
        if sys.stderr.isatty():
            processors.append(structlog.dev.ConsoleRenderer())
        else:
            processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.WARNING
        ),
    )
```

---

## CLI флаги

```bash
# Production (default)
uvicorn dnd_simulator.adapters.api.app:app

# Debug — всё в консоль (pretty)
uvicorn dnd_simulator.adapters.api.app:app -- --debug

# Debug + файлы
uvicorn dnd_simulator.adapters.api.app:app -- --debug --log-dir ./logs

```

Или через env vars (более Docker-friendly):
```bash
DEBUG=1 LOG_DIR=/var/log/dnd LOG_DOMAINS=llm,combat uvicorn ...
```

---

## Grafana/Loki интеграция

Когда перейдёте на Docker:

```yaml
# docker-compose.yml
services:
  app:
    logging:
      driver: "json-file"  # или fluentd/loki
    environment:
      - DEBUG=1  # JSON lines в stdout
  
  loki:
    image: grafana/loki
  
  promtail:
    image: grafana/promtail
    # парсит JSON lines из Docker logs → Loki
  
  grafana:
    image: grafana/grafana
    # dashboards: по session_id, entity_id, domain
```

**Grafana queries (LogQL):**
```
{app="dnd-simulator"} | json | domain="llm"
{app="dnd-simulator"} | json | entity_id="goblin_01" | level="error"
{app="dnd-simulator"} | json | domain="action" | action="attack" | .damage > 10
```

Всё работает из коробки благодаря JSON-формату логов.

---

## Что это даёт

1. **`--debug` для сессии** → полный поток с контекстом, каждый лог знает к какой сессии, entity, слою, фазе он относится
2. **Навигация по файлам** → открыл `entities/goblin_01.jsonl` и видишь всё что происходило с гоблином
3. **LLM контексты** → полные промпты в отдельных JSON-файлах, можно воспроизвести вызов
4. **Grafana-ready** → JSON в stdout, Loki парсит, можно строить дашборды по domain/entity/session
5. **Денормализация** → один лог в нескольких файлах по разным классификациям
6. **Постепенная миграция** → не нужно менять всё сразу, structlog совместим с stdlib

## Открытые вопросы

1. **Хранение файлов** — по session_id или по дате? Ротация?
(По сессии, без ротации. Но для каждой строчки ещё дату добавить с точностью до секунды)
2. **Размер LLM-контекстов** — полные промпты могут быть большими. Хранить всегда или только в debug?
(Пока в режиме активной отладки - пишем всё)
3. **Performance** — запись в несколько файлов одновременно. Async IO или синхронный (в debug не критично)?
(Похуй)
4. **Filtering UI** — нужен ли простой TUI/web viewer для просмотра логов? Или `jq` + редактор достаточно?
(Похуй)
5. **Entity field tracking** — все поля или только "важные" (hp, conditions, inventory)?
(Пока в режиме активной отладки - пишем всё)
