# Roadmap

Этапы разработки, текущий статус, ссылки на детальные планы.

## Done

### Phase 1 — Локации, расписание, перемещение
Граф локаций (~40 для Sword Vale). NPC-расписание через чистые функции. Перемещение между локациями с расчётом времени. `look` фильтрует по локации и расписанию.

### Phase 2 — Память NPC и awareness
NpcMemory (теги, recent, inner_state, current_conversation). Структурированные теги для эмоций/отношений. Дельта-лог для LlmBrain (~15 строк). MemorySummarizer сжимает память через LLM.

### Phase 2.5a — Wiring суммаризатора
Триггеры суммаризации: конец боя, конец разговора, переполнение recent. Суммаризация с точки зрения каждого NPC.

### Phase 2.5b — Canned dialogue для RuleBrain
Таблицы реплик по (role, activity, mood). RuleBrain отвечает на события осмысленными фразами без LLM.

### Round system — Раунд-оркестратор
Multi-action turn loop с TurnBudget. Единый раунд для боя и мирного режима. Бюджет действий (action, bonus_action, movement, reaction). PlayerBrain через queue + callback.

### Unified entity model
Все существа на EntitiesLayer. Убран session.player, заменён единой моделью. Brain как strategy pattern (RuleBrain / LlmBrain / PlayerBrain).

### Combat system
BattleMap (2D grid), инициатива, auto-exit после 2 idle раундов. D&D 5e diagonal distance, стены, коллизии.

## In Progress

### Frontend — веб-интерфейс
Мастер-панель и интерфейс игрока. Vanilla HTML/CSS/JS, dark theme.
→ [план](plans/frontend-debug-ui.md)

## Planned

### Phase 3 — Автономные тики и эволюция NPC
Триггерные пробуждения NPC по событиям мира. Периодические тики для ключевых NPC. Batch LLM-вызовы для групповых реакций. Graceful degradation без LLM.
→ [брейншторм](brainstorms/npc-lifecycle.md), [брейншторм](brainstorms/game-loop-and-master.md)

### Система триггеров пробуждения
Предзаданные триггеры в контенте + ручное пробуждение мастером. Механика — отдельный брейншторм.

### Магия мысли
Заклинания как CRUD над памятью NPC. Работает на всех NPC независимо от мозга.
→ [брейншторм](brainstorms/magic-as-prompt-api.md)

### World Builder
UI-визард для создания миров (7 шагов). Часть продукта для конечных пользователей.
→ [план](plans/world-builder.md)

### WebSocket транспорт
Замена REST на WebSocket для real-time взаимодействия. Основа для мультиплеера.

### Мультиплеер
Несколько игроков в одном мире. Механика активности уже поддерживает это — игре всё равно, PlayerBrain или LlmBrain.

### Расширение правил D&D 5e
Классы, расы, экипировка, заклинания — постепенное добавление.

## Known Issues

См. [backlog.md](backlog.md) — баги и мелкие фичи.
