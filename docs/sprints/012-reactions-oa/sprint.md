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

## Phase 1: Reaction Infrastructure + OA Mechanics ✓

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

## Phase 2: Movement Integration + Round Wiring ✓

Wiring реакций в game loop. OA реально срабатывает при движении.

- `on_leave_reach` callback в `ActionContext` — Round передаёт, movement handlers вызывают при каждом шаге где мувер покидает reach врага.
- `check_reactions` в Round — рекурсивный, с `exclude_ids` (предотвращает повторный запрос существу без реакции). Проверяет `creature.turn_budget.reaction > 0`, consume после успешной реакции.
- Movement handlers (`handle_move_to`, `handle_move` через CombatManager) — вызывают callback между шагами. Если мувер погиб от OA — движение прерывается.
- `handle_disengage` — ставит `is_disengaging = True` вместо no-op.
- `is_disengaging` сброс в начале хода (рядом с `is_dodging`).
- Integration тесты: OA срабатывает при выходе из reach, Disengage предотвращает, рог Disengage bonus + Attack в тот же ход, OA убивает мувера (движение прервано), два OA от разных врагов на одно движение.

**Верифицируем:** Full combat scenario: существо двигается мимо двух врагов, оба бьют OA (у обоих есть reaction). Существо с Disengage проходит без OA. Рог Disengage как bonus → Attack как action → движение без OA. Мувер убит OA — остановился на месте смерти.

**Tasks:**

1. [check_reactions rewrite + on_leave_reach callback](tasks/phase2-task1-check-reactions-callback.md)
2. [Wire movement handlers to trigger OA](tasks/phase2-task2-movement-wiring.md)
3. [Integration tests — OA fires during movement](tasks/phase2-task3-integration-tests.md)

## Phase 3: Frontend + Content ✓

UI для реакций игрока и обновление контента.

- **Perception handlers для OA и Disengage.** Сейчас `perceive_event` не имеет case-ветки для `EventType.OPPORTUNITY_ATTACK` и `EventType.ENTITY_DISENGAGE` — в логе показывается fallback "Что-то произошло (opportunity_attack)". Добавить handler-ы в `layers/entities/perception.py` по аналогии с `entity_attack`. OA: "X атакует Y (opportunity attack) [d20...]". Disengage: "X отступает".
- **WebSocket: reaction prompt.** Новый тип сообщения `type: "reaction_prompt"` с trigger info и available options. В `service/session.py` вызвать `brain.set_on_reaction(on_reaction)` по аналогии с `set_on_turn` — callback формирует message и отправляет через `_fire`. Новый тип входящего WS-сообщения `submit_reaction` вызывает `brain.submit_reaction(action)`. Убрать auto-SKIP fallback в `PlayerBrain.choose_reaction` (сейчас в `core/brain.py:381`) — после wiring он не нужен.
- **Reaction prompt в UI.** Когда приходит `reaction_prompt`, клиент показывает компактный overlay/toast ("Враг покидает вашу зону. Атаковать?") с кнопками (Attack / Skip). По клику отправляет `submit_reaction` через WS. Таймаут не нужен — Round блокируется на queue.get() до ответа.
- **Combat log показывает OA и Disengage** как отдельные читаемые события (зависит от perception handlers выше).
- **Disengage indicator в ActionBar** — badge или визуальная подсказка показывает что `is_disengaging` активен и движение безопасно.
- **Контент:** существующие NPC в combat scenarios используют Disengage осмысленно (RuleBrain). Проверить что RuleBrain._choose_combat_action выбирает Disengage перед отходом когда HP низкий.

**Верифицируем:** Игрок видит reaction prompt при OA, может выбрать Attack/Skip. Лог показывает OA и Disengage читаемым текстом. NPC используют Disengage когда нужно отойти от врага.

**Tasks:**

1. [Backend — Perception Handlers + WS Reaction Wiring](tasks/phase3-task1-backend-perception-ws.md)
2. [Frontend — Reaction Prompt + Disengage Indicator](tasks/phase3-task2-frontend-reaction-ui.md)
3. [RuleBrain Tactical Disengage](tasks/phase3-task3-rulebrain-disengage.md)

## Phase 4: Audit Refactor

Устранение audit findings в коде, затронутом спринтом 012. Чистка перед закрытием.

- **perception.py — 54 `.get()` → fail-fast.** Заменить `event.data.get("key", "")` на `event.data["key"]` во всех perception handlers. Маскировка пропущенных полей скрывает баги.
- **awareness_builder.py — убрать catch-all except.** 7 `except Exception` блоков заменяют реальные данные хардкоженными fallback-ами. Сузить до конкретных исключений или убрать.
- **perception.py — dispatch dict.** Заменить 55-строчный if/elif chain на `dict[EventType, Callable]` lookup.
- **session.py — extract closure duplication.** `start_round()` 116 строк, 4 closure (включая `on_reaction` добавленный в этом спринте) с одинаковой сериализацией. Вынести shared event builder.
- **round.py — extract helpers из run_combat_turn.** 137 строк, Sprint 012 добавил reaction integration. Вынести awareness rebuild и action execution.
- **Test gaps для sprint 012 files:** `rules/reactions.py`, `rules/handlers/reactions.py`, `rules/handlers/movement.py` — добавить выделенные unit тесты.

**Верифицируем:** `make check` проходит. Все новые тесты зелёные. Строки perception.py < 400, run_combat_turn < 80.

**Tasks:**

1. [Perception dispatch dict + fail-fast](tasks/phase4-task1-perception-refactor.md)
2. [Session closure dedup + awareness_builder exception narrowing](tasks/phase4-task2-session-awareness-cleanup.md)
3. [Round helpers + sprint 012 test gaps](tasks/phase4-task3-round-helpers-test-gaps.md)

---

## Status

**Current:** Phase 3 complete. Phase 4 (audit refactor) pending.

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
