# Sprint 012 — Reactions & Opportunity Attacks

**Goal:** Система реакций D&D 5e — opportunity attacks при выходе из reach, Disengage предотвращает, все три мозга (Rule, LLM, Player) единообразно поддерживают choose_reaction.

**Started:** 2026-03-30

## Context

Sprint 011 завершил L1 классовых механик, но Disengage остался заглушкой — действие существует, бюджет тратится, эффекта нет. Причина: нет системы реакций и opportunity attacks. Рог может Disengage как bonus action через Cunning Action, но это бессмысленно без OA.

Reaction infrastructure — фундамент для будущих реакций (Counterspell, Shield, Ready action), но этот спринт реализует только OA как первый конкретный случай.

Ключевые архитектурные решения:
- **TurnBudget переезжает на Creature** (per-round вместо per-turn). D&D 5e: все ресурсы (action, bonus, movement, reaction) — от начала твоего хода до начала следующего. Reaction тратится между ходами, остальные — на своём ходу. Reset в начале хода существа.
- **Brain.choose_reaction** — новый метод на ABC, единообразный для всех мозгов. Default: SKIP. RuleBrain — детерминированная логика, LlmBrain — LLM-вызов с reaction tool schema, PlayerBrain — callback + queue (как choose_action).
- **ReactionTrigger** — typed data object описывающий что вызвало реакцию. Расширяемый на будущие типы (spell_cast, being_attacked).
- **check_reactions рекурсивный** — реакция может вызвать реакцию (counterspell chain). Глубина ограничена естественно: 1 reaction per creature per round.
- **Movement callback** — on_leave_reach в ActionContext, Round передаёт, handler вызывает при выходе из reach. Handler не импортирует Round.

**Ссылки:** [sprint 011](../011-class-mechanics-l1/sprint.md), [backlog](../../BACKLOG.md), [ecs-and-content](../../brainstorms/ecs-and-content.md)

---

## Phase 1: Reaction Infrastructure + OA Mechanics

Фундамент системы реакций и pure mechanics для opportunity attacks. Всё тестируемо unit-тестами без wiring.

- `Creature.turn_budget: TurnBudget | None` — бюджет живёт на существе, не как локальная переменная. `run_combat_turn` создаёт/сбрасывает в начале хода, между ходами budget доступен для реакций. Убрать создание TurnBudget как локальной переменной из Round.
- `ReactionTrigger(trigger_type: TriggerType, source_creature_id: str, data: dict)` — typed trigger. `TriggerType.LEAVING_REACH` для OA, расширяемый enum.
- `Brain.choose_reaction(creature, trigger, available_reactions) -> ActionType` — новый метод на ABC, default SKIP. RuleBrain: OA → всегда бить если можешь. LlmBrain: LLM-вызов с reaction tool schema. PlayerBrain: callback + queue (тот же паттерн что choose_action).
- `is_disengaging: bool` на Creature (как `is_dodging`), сброс в начале хода.
- `ActionType.OPPORTUNITY_ATTACK` + ActionDef (cost: reaction, targeted, combat_only).
- `rules/reactions.py` — pure functions: `can_opportunity_attack(reactor, mover, battle_map)`, `find_oa_triggers(path, combatants, battle_map) -> list[(step_index, list[Creature])]`.
- OA handler в `rules/handlers/` — одна melee атака, consume reaction из `creature.turn_budget`.
- LLM reaction tool schema в `llm/` — описание reaction options для LlmBrain.

**Верифицируем:** Unit tests: OA eligibility (reach, reaction budget, incapacitated, disengaging). TurnBudget на Creature сбрасывается корректно. Все три мозга возвращают осмысленный ответ на choose_reaction. find_oa_triggers находит правильные шаги пути.

**Tasks:**

1. [TurnBudget on Creature + is_disengaging](tasks/phase1-task1-budget-on-creature.md)
2. [Reaction Infrastructure — Triggers + Brain.choose_reaction](tasks/phase1-task2-reaction-infrastructure.md)
3. [OA Rules + Handler + Disengage Fix](tasks/phase1-task3-oa-rules-handler.md)

## Phase 2: Movement Integration + Round Wiring

Wiring реакций в game loop. OA реально срабатывает при движении.

- `on_leave_reach` callback в `ActionContext` — Round передаёт, movement handlers вызывают при каждом шаге где мувер покидает reach врага.
- `check_reactions` в Round — рекурсивный, с `exclude_ids` (предотвращает повторный запрос существу без реакции). Проверяет `creature.turn_budget.reaction > 0`, consume после успешной реакции.
- Movement handlers (`handle_move_to`, `handle_move` через CombatManager) — вызывают callback между шагами. Если мувер погиб от OA — движение прерывается.
- `handle_disengage` — ставит `is_disengaging = True` вместо no-op.
- `is_disengaging` сброс в начале хода (рядом с `is_dodging`).
- Integration тесты: OA срабатывает при выходе из reach, Disengage предотвращает, рог Disengage bonus + Attack в тот же ход, OA убивает мувера (движение прервано), два OA от разных врагов на одно движение.

**Верифицируем:** Full combat scenario: существо двигается мимо двух врагов, оба бьют OA (у обоих есть reaction). Существо с Disengage проходит без OA. Рог Disengage как bonus → Attack как action → движение без OA. Мувер убит OA — остановился на месте смерти.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 3: Frontend + Content

UI для реакций игрока и обновление контента.

- Reaction prompt в UI — когда PlayerBrain получает choose_reaction, клиент показывает компактный prompt ("Враг покидает вашу зону. Атаковать?") с кнопками (Attack / Skip).
- Combat log показывает OA как отдельное событие (кто, кого, урон).
- Disengage indicator в ActionBar — badge показывает что движение безопасно.
- WebSocket: новый тип сообщения для reaction prompt, ответ от клиента.
- Контент: существующие NPC в combat scenarios используют Disengage осмысленно (RuleBrain).

**Верифицируем:** Игрок видит reaction prompt, может выбрать. Лог показывает OA. NPC используют Disengage когда нужно отойти от врага.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

- **TurnBudget per-round на Creature, не per-turn локальная переменная.** D&D 5e: ресурсы от начала твоего хода до начала следующего. Reaction тратится между ходами из того же бюджета. Reset в начале хода.
- **Brain.choose_reaction — единообразный метод на ABC.** Все три мозга реализуют. Никакой транспортной специфики в мозгах. PlayerBrain — тот же callback + queue паттерн.
- **Movement callback on_leave_reach через ActionContext.** Handler не импортирует Round. Callback = None → работает как раньше (без OA). Чистое разделение.
- **check_reactions рекурсивный.** Реакция может породить trigger для другой реакции. Глубина ограничена естественно (1 reaction per creature per round). Готово к Counterspell chains.
- **Scope: только OA.** Инфраструктура поддержит Counterspell/Shield/Ready, но конкретные реакции кроме OA — вне скоупа.

## Deferred

- Counterspell, Shield, Ready action — инфраструктура готова, конкретные реакции в будущих спринтах
- Sentinel/Polearm Master feat interactions с OA (расширенный reach, OA при входе в reach)

## Results

_(заполняется в конце спринта)_
