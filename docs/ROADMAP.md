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

### Sprint 004 — Living World: Squads & Encounters (фазы 1-4)
Живой мир: абстрактные группы (squads) перемещаются по графу локаций, сталкиваются друг с другом и с active characters. EcologyLayer — tick-based движение сквадов. Faction relations: faction_id на Creature/Squad, матрица отношений на PoliticsLayer. Encounter tables как свойство зоны для любого active character. Hostile AI: faction-aware, враг по faction relations → атака. Abstract combat formula (squad vs squad). Materialization: squad при контакте с active character → конкретные Creature. YAML контент: фракции, 4 сквада, 8 monster templates для Sword Vale.
→ [план спринта](sprints/004-monster-encounters/sprint.md)

### Sprint 005 — Tech Sweep (фазы 1-5)
God-класс EntitiesLayer расщеплён на AwarenessBuilder/ActivationManager/QueryHandler/CombatManager/Perception. action_handlers.py → rules/handlers/ package, content_loader.py → content_loader/ package. Убран legacy single-file content format. Service mixins получили Protocol base. Round больше не обращается к приватным методам EntitiesLayer. Answer.value Any → object. Unit-тесты для критических путей: AwarenessBuilder, World layer isolation, ActionProvider/BrainFactory. 81 файлов, +5751/−2964 строк.
→ [план спринта](sprints/005-tech-sweep/sprint.md)

### Sprint 006 — Layer Composition (фазы 1-4)
Мир собирается из переиспользуемых шаблонов слоёв. Library (`content/library/`) хранит 5 шаблонов на слой (geography, politics, settlements, ecology, entities) с metadata.yaml. Мир — manifest.yaml со ссылками на library или custom. Content loader резолвит манифест. API: каталог шаблонов с фильтрацией совместимости, сборка мира из шаблонов, fork слоя в custom. Frontend: WorldBuilder wizard (6 шагов), альтернатива quick-start. Старый формат (без манифеста) убран, content_saver удалён.
→ [план спринта](sprints/006-layer-composition/sprint.md)

### Sprint 007 — World Builder + Session Robustness (фазы 1-5)
Save/load completeness (resource pools, combat state, spawned creatures, brain reassignment). Give Item UI. Fork UI + World Inspector на /master. Layer editor (YAML read/write API + textarea). Partial worlds: incomplete manifests, scaffold endpoint, fork world with layer truncation, delete world. Фазы 6-7 (structured forms, DM restructure) deferred — superseded by sprint 008.
→ [план спринта](sprints/007-world-session/sprint.md)

### Sprint 008 — Content Schema & Catalogs (фазы 1-5)
Pydantic content models как единый source of truth для структуры контента. Phase 1: Pydantic-модели + перепись парсеров на model_validate. Phase 2: каталоги monsters + items — вынос из слоёв, ref-resolution между мирами и каталогами. Phase 3: entity CRUD API + JSON Schema endpoints + cross-layer refs. Phase 4: frontend schema-driven forms (SchemaForm, EntityListEditor, CatalogBrowser), DM restructure (Worlds/Sessions tabs, landing page Player/DM). Phase 5: DM world management (fork world, delete world, player flow simplified — no world builder).
→ [план спринта](sprints/008-content-schema/sprint.md)

### Sprint 009 — UI Layout: Dashboard + Combat Map (фазы 1-5)
Переработка игрового экрана в dashboard: три колонки панелей (Nearby, Character+Inventory, Location) всегда видны. Компактный лог (1-2 строки + expand overlay). Action bar с budget display, drawers для зелий/классовых умений/инвентаря. NPC inspect modal (описание, фракция, действия). Боевой layout: CombatPanel в левой колонке, интерактивная CSS Grid BattleMap в правой (заменяет LocationPanel в бою). Click-to-move: BFS pathfinding + подсветка доступных клеток + `move_to(x, y)` action на бэкенде.
→ [план спринта](sprints/009-ui-layout/sprint.md)

### Sprint 010 — E2E Polish + ActionBar Decomposition (фазы 1-2)
Закрытие UX-багов из e2e-отчёта sprint 009: combat log i18n, click-to-inspect на BattleMap (клик по фигурке → карточка существа, combatants list убран), NPC inspect faction display, HP edit current/max, brain toggle warning toast, consumable drawer tooltip, log overlay backfill. ActionBar.tsx (532 строк) декомпозирован на 8 субкомпонентов (action-bar/), оркестратор < 150 строк.
→ [план спринта](sprints/010-e2e-polish/sprint.md)

### Sprint 011 — Class Mechanics L1 Completion (фазы 0-4)
Structured dice pipeline (DiceResult, D20Result, reroll_below для GWF). BattleMap reachability на бэкенде (Dijkstra, единый BFS, фронт = рендерер). Типизированное оружие/броня с D&D 5e свойствами (`is_two_handed`, `light`, `heavy`), Great Weapon Fighting style, Cunning Action с выбором cost_mode (bonus/action), SA faction check (ally detection через faction relations). SRD каталог оружия (12 видов) и брони (12 видов + shield). Fighter/Rogue NPC с полной экипировкой, 106 integration tests. Кликабельный лог бросков (RollBreakdown, AttackCardModal). Fix: equipment persistence в save/load, potion crash.
→ [план спринта](sprints/011-class-mechanics-l1/sprint.md)

### Sprint 012 — Reactions & Opportunity Attacks (фазы 1-4)
Система реакций D&D 5e. Brain.choose_reaction() — единый метод на ABC для RuleBrain/LlmBrain/PlayerBrain. Opportunity attacks при выходе из reach врага, Disengage предотвращает OA. TurnBudget на Creature (персистирует между ходами для реакций). Movement handlers вызывают on_leave_reach callback. check_reactions рекурсивный (reaction → reaction). Frontend: reaction prompt UI, disengage indicator, perception handlers для OA/Disengage. Creature.combat_position для детерминированной расстановки на карте. BattleMap.set_position raises ValueError на out-of-bounds. Phase 4 (audit refactor): perception dispatch dict, session closure dedup, awareness exception narrowing, round helpers extraction, unit tests для reactions/handlers/movement.
→ [план спринта](sprints/012-reactions-oa/sprint.md)

### Sprint 013 — Character Creation Overhaul (фазы 1-3)
Экран создания персонажа из "впиши любые цифры" → D&D-подобный flow. Phase 1: HP формула (max hit die + CON mod), point buy валидация (27 очков, 8-15), starting equipment по классу. Phase 2: backend derive stats + API, frontend CharacterForm с point buy UI (+/− кнопками, preview HP/AC/gold), Fighting Style selector для Fighter. Phase 3: Guard monster template для Kingdom Patrol, integration tests squad materialization. GWF fighter получает greatsword вместо longsword+shield. Crit dice отделены от base dice для корректного GWF reroll.
→ [план спринта](sprints/013-char-creation/sprint.md)

### Sprint 014 — Faction Relations & Reputation (фазы 0-4)
Бои с правильными сторонами из faction relations. CombatSides — граф отношений при старте боя: FRIENDLY → одна сторона, HOSTILE → разные, forced_opponents для атак. Personal reputation: числовой `reputation: dict[str, int]` на Creature (sparse, fallback на faction defaults). `effective_relation(A, B)` — единая функция: personal rep → thresholds (75+ FRIENDLY, 25-74 NEUTRAL, <25 HOSTILE) → faction fallback. Kill reputation drop (omniscient, масштабируется по репутации жертвы). Auto-hostility: атака NPC вне боя → бой с правильными сторонами. Phase 0 refactor: PoliticsLayer split (diplomacy/warfare/economy), CombatManager split, Brain decompose. Phase 4 bugfixes: starting equipment → реальные Item + equip, skip dead creatures в round loop, RuleBrain movement budget check.
→ [план спринта](sprints/014-faction-reputation/sprint.md)

### Sprint 015 — Paladin Class & Spell Slots (фазы 1-7)
Paladin L1-L2 как первый caster-класс. Phase 1: spell slots как `ResourcePool` (reset on LONG_REST). Phase 2: `PaladinFeatures` (fighting style + cost overrides), Lay on Hands (pool = 5 × level), стартовая экипировка. Phase 3: Divine Smite (`rules/divine_smite.py`) — тратим spell slot после melee hit, +2d8 radiant базово, +1d8 на уровень слота. Phase 4: multi-damage weapons (attack carries `tuple[DamageComponent, ...]`), UI breakdown по типам урона. Phase 5: Smite + Magic Weapon combo, spell slot UI, integration tests. Phase 6: `TargetMode`/`TargetScope` enums (NONE/SELF/SINGLE × HOSTILE/ALLY/ANY), валидация scope в `rules/validation.py`, frontend routing. Phase 7: Smite choice UI во время атаки, level 1 spell slot на персонаже.
→ [план спринта](sprints/015-paladin-spell-slots/sprint.md)

### Sprint 017 — XP & Leveling (фазы 1-5)
Система опыта и уровней + исправление уровней классовых фич по PHB. Phase 1: `rules/leveling.py` — XP-by-CR (D&D 5e MM), PHB thresholds, `can_level_up`. XP начисляется при kill (omniscient, как reputation drop), эмитится `xp_gained`, флаг `level_up_available` на Character. Phase 2: `perform_level_up` + `POST /level-up`, level-aware class features (`collect_*_modifiers` гейтят по `creature.level`) — Paladin L1 теперь без FS/Smite/slots (исправлен PHB-баг sprint 015), L2 Paladin получает Fighting Style + Divine Smite + spell slot, Fighter L2 — Action Surge (extra action / short rest), Rogue L2 — только HP. Phase 3: `LevelUpModal` с класс-условной формой (Paladin выбирает Fighting Style, остальные — confirm-only), dedicated `level_up_arena` world для E2E. Phase 4: bug sweep из phase-3 E2E — per-location battle_map override, fail-fast coord validator (x = width, y = height), единый canonical player для combat sidebar HP/AC, Cancel в LevelUpModal = defer (не delete). Phase 5: post-audit cleanup — перенос level-up+status логики в `GameService.level_up_player` / `player_status` (DTO layer), unit tests для `rules/leveling` и `perform_level_up`, schemas `Any → object`, fix non-determinism в `roll_initiative` / `BattleMap.place_randomly` (используют `get_global_rng()`, больше не обходят `DND_DICE_SEED`).
→ [план спринта](sprints/017-xp-leveling/sprint.md)

### Sprint 016 — Tech Sweep (фазы 1-4)
Техспринт после 10 продуктовых спринтов. Phase 1: bug sweep — class_features save/load (AC Defense bug), 26 pre-existing frontend test failures, action bar display (raw snake_case имена, cost labels, drawer tooltips), Second Wind perception formatter, battle map configs из regions.yaml. Phase 2: split `routes_master.py` на `routes_session.py` + `routes_world.py`; extract `get_session_state()` из adapter в service. Phase 3: core boundaries — `CreatureHost` protocol в `core/creature_host.py` развязывает `round.py` от `EntitiesLayer`, `RuleBrain` переехал в `rules/rule_brain.py` (core не импортирует rules), `llm/` использует `ScheduledNpc` Protocol вместо импорта `Npc`, `NpcMemory` в `core/`, `ClassFeatures.collect_self_modifiers/collect_attack_modifiers` — каждый класс декларирует свои модификаторы. Phase 4: `EntityKind(StrEnum)` runtime дискриминатор, `BrainType(StrEnum)` для ai_type, fail-fast cleanup (attack target_id на входе dispatcher, autosave log+continue, HTTPStatus в тестах). Post-audit: fix auto-hostility — HOSTILE scope без combat_state пропускает faction check, чтобы attack handler мог запустить бой через forced_opponents.
→ [план спринта](sprints/016-tech-sweep/sprint.md)

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

### World Builder (advanced)
Расширенный world builder: редактор слоёв (YAML editor в UI), превью мира перед стартом, маркетплейс шаблонов. Базовый wizard (выбор из библиотеки) реализован в Sprint 006.
→ [план](plans/world-builder.md)

### Мультиплеер
Несколько игроков в одном мире. Механика активности уже поддерживает это — игре всё равно, PlayerBrain или LlmBrain.

## Known Issues

См. [e2e-reports/](e2e-reports/) — результаты E2E-тестирования, [BACKLOG.md](BACKLOG.md) — баги и tech debt.
