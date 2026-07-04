# NPC Lifecycle — программа минимум

Три фазы оживления НПС. Каждая самодостаточна — после любой фазы игра уже играбельна.

> **Актуализация 2026-07-04:** фаза 3 (автономные тики, триггерные пробуждения) пересмотрена в [simulation-core.md](simulation-core.md) — периодические тики отброшены в пользу decision-точек (намерения + триггеры); память НПС расширена до «внутреннего я» (цели, отношения, живой alignment).

---

## Фаза 1 — Локации, расписание, перемещение (0 LLM) ✅ DONE

> Реализовано в коммитах `89de182`, `ebd2c5e`

### Мир как граф локаций ✅

`core/location.py`: `Location`, `LocationEdge`, `LocationGraph`. Плоский граф, живёт на `World.location_graph`. ~40 локаций для sword_vale: города разбиты на таверну/рынок/кузницу/ворота/казармы, дороги между городами с реальными расстояниями.

`Entity.region_id` убран, заменён на `Entity.location_id`. Регион — derived через `graph.region_of()` для погоды/политики.

### Перемещение ✅

`go <location_id>` — только соседний узел. Время = расстояние / скорость с модификаторами террейна и погоды. Минимум 1 минута.

### Расписание НПС (computed, не state) ✅

`scheduled_location(hour)`, `scheduled_activity(hour)` — чистые функции. `on_tick` убран. `location_override` для боя/разговора/ручного перемещения. `DEFAULT_SCHEDULE_TEMPLATES` + `resolve_schedule(role, settlement_id)` → `{settlement_id}_{label}`.

### `look` фильтрует по локации ✅

Запрос `entities_at_location` вычисляет кто где по расписанию. Рынок в 10 утра → торговец; в 22:00 → пусто.

### Флейвор-строки ✅

`activity_flavor(role, activity)` → "hammering at the anvil", "standing watch", "wiping down the bar". Показываются в `look` вместо сухих "working"/"idle".

### Backward compat ✅

Если `locations.yaml` отсутствует — автогенерация из регионов (1 location = 1 region). Старые миры работают.

### Не реализовано (будущее, не блокирует)

- Путешествие как процесс с прерываниями (случайные встречи, смена погоды, ночёвка на длинных дорогах)
- Навык картографии, купленные карты, fast travel
- Автоматический `location_override` при начале/конце разговора

---

## Фаза 2 — Память и осведомлённость (LLM при диалоге) ✅ DONE

> Реализовано, детали в `plans/npc-lifecycle.md` Phase 2 + Phase 2.5

### Event digest → delta log ✅

LlmBrain переключен с `perceived_log` (полная история) на `new_perceived_events` (дельта с последнего хода), лимит 15 строк. Память в JSON формате вставляется в system prompt.

### NpcMemory (замена conversation_summary) ✅

`NpcMemory` dataclass: `tags`, `recent`, `inner_state`, `current_conversation`. Заменяет `conversation_summary`. Сериализация в JSON, backward compat со старыми сейвами.

### Structured tags ✅

`NpcTag` — словарь тегов (emotions: angry/scared/..., relations: hates/loves/...:creature_id). `RuleBrain` читает теги: `hates:X` → приоритет цели, `scared` → раньше убегает.

### MemorySummarizer ✅

`llm/summarizer.py` — сжимает события в memory через дешёвый LLM-вызов. Триггеры: `conversation_ended`, `combat_ended`, `recent_overflow`. Защита тегов от изменения LLM.

### Не подключено (Phase 2.5) ⬜

- Триггеры сумарайзера не вызываются из `EntitiesLayer` (код есть, wiring нет)
- RuleBrain canned dialogue (таблица реплик по role+activity)

**Итог:** НПС помнят, что было. Structured tags работают в бою. Сумарайзер готов к подключению.

---

## Фаза 3 — Автономные тики ключевых НПС (L2) ⬜ TODO

### Тиры НПС ⬜

```python
class NpcTier(Enum):
    BACKGROUND = "background"   # L1: только расписание
    IMPORTANT  = "important"    # L2: реагирует на события
    KEY        = "key"          # L2+: периодические автономные тики
```

### Триггерный тик (IMPORTANT + KEY) ⬜

Мировое событие затрагивает НПС → один дешёвый LLM-вызов:

```
Ты кузнец Грунд. Характер: грубый, честный.
Произошло: объявлена война с орками.
Ответь JSON: {"schedule_change": "...", "mood": "...", "new_goal": "..."}
```

### Периодический тик (только KEY) ⬜

Раз в N игровых дней — тот же формат. Антагонист строит планы, компаньон развивается.

### Graceful degradation ⬜

Без LLM триггерные тики не срабатывают, НПС остаются на фазе 1. Игра работает, мир просто более статичный.

**Итог:** мир живёт без игрока. Вернулся через 3 месяца — кузнец ушёл в ополчение, торговец сбежал.
