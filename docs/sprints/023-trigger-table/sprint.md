# Sprint 023 — Trigger Table

**Goal:** Декларативные парные триггеры `{on, until}` на типизированной таксономии событий активируют и гасят существ (YAML + ручка ГМ), а ecology получает событийный write-back смертей логова — первый прототип механизма detail-ladder.

**Started:** 2026-07-12

## Context

Третий эпик цепочки simulation-core после схемы сейва (Sprint 021) и якорей/намерений (Sprint 022). Сейчас активация опирается только на якоря и близость; разбудить существо по мировому событию нечем — «принц активируется, когда началась война» невозможен. Триггеры требуют контракта, на котором можно матчить: типизированной таксономии событий с фиксированными payload'ами (фундамент заложен Sprint 020 phase 2).

Спринт вводит таксономию, матчинг при эмиссии, активацию/гашение dormant↔active по парным `{on, until}` триггерам из YAML и ручки ГМ, самогашение «моя роль сыграна» как действие мозга. На той же событийной шине закрывается `lair-death-event`: ecology подписывается на смерти существ и обновляет состояние логова в реальном времени — бэклог помечает это как прототип write-back всей detail-ladder.

По просьбе оператора спринт докидывает разгрузку бэклога: containment ожидаемых action errors (`action-error-kills-round-loop`), перцептор встреч (`encounter-spawned-perceiver`) и чистку `dash-actiondef-movement-conflation`.

За границей спринта: `inner-self` (цели/отношения/alignment), `brain-gate-decide`, `detail-ladder` целиком, квесты, реализм доставки информации (триггеры всеведущие), `gm-actives-panel` сверх минимальной ручки.

**Ссылки:** [simulation-core](../../brainstorms/simulation-core.md), [BACKLOG](../../BACKLOG.md#simulation-core-брейншторм-2026-07-04), [Sprint 022](../022-intents-travel/sprint.md)

## Phase 1: Типизированная таксономия событий ✓

События получают фиксированные типы и payload'ы (контракт вместо свободных dict'ов); существующие эмиссии переводятся на таксономию. Сюда же `encounter-spawned-perceiver`: событие встречи получает перцептор вместо мусорного фолбэка. Проверка: unit-тесты контрактов payload'ов, существующие integration зелёные, в логе игрока осмысленная строка вместо `Something happened (encounter_spawned)`.

Почему первой: и триггеры, и write-back матчатся по типам событий — без контракта им не на чем стоять.

**Tasks:**

1. [Типизированное ядро событий](tasks/phase1-task1-event-contract-core.md) — payload-контракт и миграция системных/layer-событий
2. [Контракты lifecycle и боя существ](tasks/phase1-task2-entity-lifecycle-contracts.md) — encounter, combat, death, movement, XP/reputation
2.5. [Разделить запрос и результат атаки](tasks/phase1-task2.5-split-attack-event.md) — отдельные контракты command/fact
3. [Контракты событий действий](tasks/phase1-task3-action-event-contracts.md) — handlers, attack result, perception и полное покрытие EventType

`encounter-spawned-perceiver` при разведке оказался уже закрыт в Sprint 019: `_perceive_encounter_spawned`
зарегистрирован в dispatch и покрыт RU/EN тестами. Phase 1 сохраняет и пинует это поведение при миграции payload'а.

## Phase 2: Событийный write-back — смерти логова ✓

Ecology подписывается на события смерти существ и обновляет `LairState`/`core_alive` в реальном времени, а не при дематериализации. Закрывает `lair-death-event`. Проверка: убийство ядра → логово depleted сразу, состояние переживает save/load без дематериализации.

Почему второй: простейший потребитель шины обкатывает механизм подписки до trigger-table; заявленный прототип write-back detail-ladder.

**Tasks:**

1. [Принадлежность смерти логову](tasks/phase2-task1-lair-death-provenance.md) — строгая provenance ядра/миньона в `ENTITY_DIED` и сейве
2. [Немедленный write-back смерти в ecology](tasks/phase2-task2-ecology-death-writeback.md) — событийное обновление ростера/depletion и save/load
3. [Доставка каскадных событий в live session](tasks/phase2-task3-live-event-cascade.md) — E2E-блокер доставки `ENTITY_DIED` и WS-сериализации provenance

## Phase 3: Trigger table ✓

Парные `{on, until}` триггеры на существе из YAML: матчинг при эмиссии, пробуждение dormant→active по `on`, гашение по `until`, самогашение «моя роль сыграна» как штатное действие мозга, состояние триггеров в сейве. Проверка: контентный триггер будит NPC на событии, until гасит, всё переживает save/load.

Почему третьей: ядро эпика, стоит на фазах 1-2.

**Tasks:**

1. [Контракт и индекс trigger table](tasks/phase3-task1-trigger-contract-index.md) — строгий YAML/runtime-контракт и индексированный typed-payload matcher
2. [Событийный lifecycle активации](tasks/phase3-task2-event-activation-lifecycle.md) — `on`/`until` в живом event flow и независимые причины активности
3. [Сейв и самогашение триггера](tasks/phase3-task3-trigger-save-self-complete.md) — lossless save/load и действие мозга `complete_trigger`

## Phase 4: Ручка ГМ + failure containment ✓

Минимальная мастерская ручка: активировать/погасить существо и взвести/снять триггер через master API + кнопки в панели (без полной `gm-actives-panel`). Плюс разгрузка бэклога: `action-error-kills-round-loop` (ожидаемые dispatch/handler-ошибки → неуспешный `ActionResult`, WS-regression что раунд живёт дальше) и `dash-actiondef-movement-conflation` (убрать мёртвые params, переписать описание). Проверка: E2E через мастер-панель, malformed action не убивает сессию.

Почему последней: контрольная поверхность над готовым механизмом; polish-айтемы не блокируют предыдущие фазы.

**Tasks:**

1. [Ручка ГМ для активности и триггеров](tasks/phase4-task1-gm-activation-api.md) — сохраняемый override, trigger state и master API под world gate
2. [Минимальная панель активности ГМ](tasks/phase4-task2-gm-activation-panel.md) — live controls в существующем списке существ
3. [Изоляция ошибок action от round loop](tasks/phase4-task3-action-error-containment.md) — failed `ActionResult` и WS-regression живой сессии
4. [Контракт Dash без мёртвого перемещения](tasks/phase4-task4-dash-action-contract.md) — metadata соответствует budget-only механике

## Phase 5: Post-audit refactor ✓

Audit 2026-07-13 не нашёл блокеров, но показал, что типизированный event-контракт после Phase 1 всё ещё живёт рядом с legacy dict-представлением, а `EntitiesLayer`, `perception.py`, `session.py` и `apiClient.ts` снова растут на той же событийной и control-plane поверхности. Закрываем этот долг сейчас, пока контекст триггеров свежий.

Скоуп фазы:

- сделать typed payload единственным production/runtime-представлением события: убрать mapping-фасад и legacy-нормализацию из `Event`, разнести payload definitions/registry/codec по устойчивым границам;
- вынести trigger lifecycle, event location/logging и typed perception из растущего `EntitiesLayer`; заменить silent `.get()` там, где конкретный payload уже гарантирован типом;
- вынести transport payload builders из `session.py` и разделить `frontend/src/transport/apiClient.ts` по доменам без изменения wire-контракта;
- закрыть два небольших backlog-пункта: protocol error для non-object JSON по player/spectator WS и тест ошибки финального shutdown-autosave.

Проверка: legacy dict-конструкторы событий отсутствуют в production-коде; typed payload не притворяется mapping; размеры `entities/layer.py`, `session.py` и `apiClient.ts` уменьшаются; malformed WS JSON не рвёт соединение; shutdown всегда завершает lifespan с предсказуемым логированием ошибки; backend/frontend/integration зелёные.

**Tasks:**

1. [Единый typed event-контракт](tasks/phase5-task1-typed-event-runtime.md) — убрать legacy mapping/normalization и разделить definitions/registry/envelope
2. [Разгрузка entities event flow и perception](tasks/phase5-task2-entities-event-decomposition.md) — выделить trigger/logging и typed perception компоненты
3. [Разделение backend и frontend transport builders](tasks/phase5-task3-transport-decomposition.md) — уменьшить session.py/apiClient.ts без изменения wire API
4. [Protocol containment и финальный autosave](tasks/phase5-task4-transport-reliability-gaps.md) — закрыть два reliability test-gap

## Phase 6: Post-audit E2E fixes

Post-audit E2E 2026-07-13 остановился на двух пользовательских блокерах: frontend EN расходится с
server-rendered live event log на RU и `COMBAT_ENDED` уходит в generic fallback; Master Sessions
показывает stale disk saves, хотя их Manage URL не может открыть session. Закрываем только эти
регрессии, затем повторяем post-audit E2E.

**E2E:** [post-audit report](../../e2e-reports/2026-07-13-sprint023-post-audit.md)

**Tasks:**

1. [Единая locale и typed COMBAT_ENDED в live WS](tasks/phase6-task1-live-ws-locale-combat-ended.md) — синхронизировать язык session/WS и убрать fallback завершения боя.
2. [Не показывать stale saved sessions в Master](tasks/phase6-task2-stale-master-sessions.md) — оставить в Manage list только доступные live sessions.

## Phase 7: Follow-up post-audit E2E locale ✓

Повторный post-audit E2E после Phase 6 нашёл один blocker: `action_result.error` создаётся в round
thread до session-scoped locale context, поэтому failed action в EN session сохраняет process-default
RU перевод. Закрываем только эту propagation boundary, затем повторяем targeted locale scenario и
полный post-audit E2E.

Смешанный label расы соседнего существа не включён: content names сейчас следуют отдельному
`DND_LANGUAGE` contract, а не UI/session locale. Это non-blocking follow-up для отдельного решения.

**E2E:** [post-audit rerun report](../../e2e-reports/2026-07-14-sprint023-post-audit-rerun.md)

**Tasks:**

1. [Locale server-rendered action failure в live session](tasks/phase7-task1-live-action-failure-locale.md) — применить session locale до dispatch expected failure.

## Phase 8: Follow-up post-audit E2E Paladin ✓

Полный post-audit E2E 2026-07-14 остановился на §14.1, потому что playbook требовал у Paladin
L1 Fighting Style selector и spell slot. Это не регрессия UI: продукт следует SRD/PHB 2014, где
эти механики появляются на L2 через `LevelUpModal`. Сначала приводим playbook к уже реализованному
контракту, затем повторяем весь обязательный non-LLM прогон, включая L1 creation, L2 level-up,
Lay on Hands и Divine Smite.

**Tasks:**

1. [Контракт Paladin в E2E playbook](tasks/phase8-task1-paladin-e2e-contract.md) — выровнять §14.1 и зависимые Paladin сценарии с L2 contract.
2. [Повторный обязательный Paladin post-audit E2E](tasks/phase8-task2-paladin-post-audit-e2e.md) — выполнить полный прогон по исправленному playbook и записать report.
3. [Повторное открытие Level Up после defer](tasks/phase8-task3-level-up-modal-reentry.md) — восстановить ручной UI путь к pending L2 без изменения правил.
4. [Terminal lifecycle ядра логова](tasks/phase8-task4-lair-core-lifecycle.md) — исправить lifecycle после Master mutation `current_hp=0`, чтобы reconnect не материализовал второй roster поверх terminal depletion.

---

## Status

**Current:** Phase 8 закрыта. Интеграционный набор зелёный (163 passed); свежая landing-регрессия и
накопленные целевые границы Paladin/lair без блокеров. Все фазы завершены, нужен финальный audit.

## Decisions

- Граница Sprint 023: таксономия событий + lair write-back + trigger table + минимальная ручка ГМ. `inner-self`, `brain-gate-decide`, полная `detail-ladder`, квесты, реализм доставки информации и `gm-actives-panel` сверх минимума — за пределами спринта (2026-07-12).
- Разгрузка бэклога по просьбе оператора: `action-error-kills-round-loop`, `encounter-spawned-perceiver`, `dash-actiondef-movement-conflation` входят в scope как polish-айтемы фаз 1 и 4 (2026-07-12).
- `ENTITY_ATTACK_REQUESTED` — внутренняя команда resolution, `ENTITY_ATTACK` — завершённый мировой факт. Разделение принято вместо optional-полей в одном payload (2026-07-12).
- Audit 2026-07-13: quick-fix нет. В Phase 5 взяты `typed-event-compat-bridge`, `entities-layer-regrowth` + `perception-fail-fast`, transport decomposition (`session.py` + `api-client-growing`) и два малых test-gap. Security, eslint suppressions, общий `Any` sweep и принятые mutable runtime dataclasses остаются в backlog (2026-07-13).
- Post-audit E2E 2026-07-13: Phase 6 ограничена единой locale live WS + typed `COMBAT_ENDED` perception и исключением stale saved sessions из Master list. Остальной playbook повторяется после этих двух fixes (2026-07-13).
- Post-audit E2E 2026-07-14: §14.1 ошибочно требовал Fighting Style и spell slot у Paladin L1. Подтверждённый SRD/PHB 2014 контракт проекта оставляет их на L2; Phase 8 исправляет E2E expectations, не product code (2026-07-14).

## Deferred

- Security (`cors-wildcard`, optional WS origin, item bounds, frontend-error schema) требует отдельного продуктового решения про deployment/auth и не смешивается с refactor-фазой.
- `event-log-eslint-suppress`, `schema-form-eslint-suppress`, общий `any-to-object-sweep` и mutable runtime dataclasses не ухудшают trigger-table contract; остаются в каноническом backlog.

## Results

Финальный audit triage 2026-07-13: quick-fix 0, sprint-relevant 0, новый `core/events.py` typed-event codec `Any` добавлен подпунктом к `any-to-object-sweep`; остальные 10 findings уже отслеживаются в BACKLOG.
