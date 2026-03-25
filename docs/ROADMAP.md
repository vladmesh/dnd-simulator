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

### Frontend — React веб-интерфейс
React + TypeScript + shadcn/ui, dark theme. Игровой экран (EventLog, BattleMap, ActionBar, Nearby/Location/Character панели) + мастер-панель (World/Creatures/Time/Saves). WebSocket для real-time взаимодействия.

### Level 0 — Фундамент game loop
Proximity-based активация существ: NPC рядом с игроком active, остальные dormant. Wait + fast-forward: `wake_at_seconds` на существе, Round.run_loop() мотает время до ближайшего пробуждения. Explicit locations — каждый мир обязан определить locations явно, убрана автогенерация из регионов. NPC перемещаются по расписанию при активации. Round lifecycle в GameSession.
→ [брейншторм](brainstorms/ecs-and-content.md)

### Level 1 — Conditions, BrainFactory, валидация
D&D 5e conditions (Prone, Poisoned, Stunned и др.) с `ConditionsMap` (rounds-based или permanent). Pure mechanics: `is_incapacitated()`, `effective_speed()`, `attack_advantage()`, `tick_conditions()`. BrainFactory — единая точка создания Brain из ai_type. ActionValidator — pipeline проверок (alive, active, action mode).
→ [брейншторм](brainstorms/ecs-and-content.md)

### Level 1.5 — ActionDispatcher, оружие, предметы
ActionDispatcher (`service/action_dispatcher.py`) — единый entry point: validate → handler → budget consume. ActionProvider определяет доступные действия по состоянию, инвентарю и оружию. Система предметов: `Item`/`WeaponDef` (`core/items.py`), `get_weapon_attack()` строит `Attack` из экипированного оружия. Healing potion как USE_ITEM. Dynamic ActionBar во фронте.
→ [план](plans/action-dispatcher.md)

### Level 1.5a — Modifier pipeline, equip/unequip, logging
Централизованный pipeline модификаторов (`core/modifiers.py` + `rules/modifiers.py`) — заменил разрозненную логику в combat_manager и conditions. Новые действия equip/unequip для смены оружия. Structlog логирование с file dispatch. Фикс awareness: LLM теперь видит регион/поселение текущей локации.
→ [брейншторм](brainstorms/logging-architecture.md)

### Audit quick wins
Фиксы по результатам аудита: безопасность, конвенции, fail-fast. Тестовая инфраструктура: Docker integration tests, git hooks (pre-commit, pre-push).

### Sprint 001 — Class Mechanics: Fighter & Rogue L1 (фазы 1-3.5)
Инфраструктура классовых механик: proficiency system, armor/shield экипировка, ResourcePool (расходуемые ресурсы), ClassFeatures (композиция вместо наследования), ActionDef (централизованный реестр действий). Fighter L1: Fighting Style (Defense/Dueling) через modifier pipeline, Second Wind (bonus action heal). Rogue L1: Sneak Attack (+Nd6 finesse/ranged при advantage/ally adjacent), Cunning Action (Dash/Disengage как bonus action через CostOverride). Generic attack perception — компонентный лог атак вместо ad-hoc полей.
→ [план спринта](sprints/001-class-mechanics/sprint.md)

### Sprint 003 — Inventory & Trading (фазы 1-4)
Полноценная система инвентаря и торговли. Phase 1: generic equip/unequip + accessory slots (head, feet, ring) с модификаторами через modifier pipeline. Phase 2: awareness для инвентаря/экипировки + фронтенд панель (6 слотов + сумка + золото). Phase 3: Merchant-флаг на NPC, buy/sell экшены, Trade UI. Phase 4 (audit refactor): NpcRole enum, вынос контента NPC в YAML, фикс rules→layers зависимости.
→ [план спринта](sprints/003-inventory-trading/sprint.md)

## In Progress

### Sprint 004 — Monster Encounters
Рандомные энкаунтеры с монстрами в опасных локациях, логова с persistent существами, автолут. MonsterTemplate из YAML, таблицы встреч на локациях, hostile AI, автодроп лута.
→ [план спринта](sprints/004-monster-encounters/sprint.md)

## Planned

### Level 2 — Расходуемые ресурсы
Spell slots, ki, rage. Дополнительные типы брони и оружия.
→ [брейншторм](brainstorms/ecs-and-content.md)

### Level 3 — Заклинания, пропсы
Заклинания как YAML, интерактивные объекты (двери, сундуки).
→ [брейншторм](brainstorms/ecs-and-content.md)

### Phase 3 — Автономные тики и эволюция NPC
Триггерные пробуждения NPC по событиям мира. Периодические тики для ключевых NPC. Batch LLM-вызовы для групповых реакций. Graceful degradation без LLM.
→ [брейншторм](brainstorms/npc-lifecycle.md), [брейншторм](brainstorms/game-loop-and-master.md)

### World Builder
UI-визард для создания миров (7 шагов). Часть продукта для конечных пользователей.
→ [план](plans/world-builder.md)

### Мультиплеер
Несколько игроков в одном мире. Механика активности уже поддерживает это — игре всё равно, PlayerBrain или LlmBrain.

## Known Issues

См. [e2e-report.md](e2e-report.md) — результаты E2E-тестирования фронтенда.
