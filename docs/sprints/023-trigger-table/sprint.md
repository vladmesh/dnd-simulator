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

## Phase 4: Ручка ГМ + failure containment

Минимальная мастерская ручка: активировать/погасить существо и взвести/снять триггер через master API + кнопки в панели (без полной `gm-actives-panel`). Плюс разгрузка бэклога: `action-error-kills-round-loop` (ожидаемые dispatch/handler-ошибки → неуспешный `ActionResult`, WS-regression что раунд живёт дальше) и `dash-actiondef-movement-conflation` (убрать мёртвые params, переписать описание). Проверка: E2E через мастер-панель, malformed action не убивает сессию.

Почему последней: контрольная поверхность над готовым механизмом; polish-айтемы не блокируют предыдущие фазы.

**Tasks:**

1. [Ручка ГМ для активности и триггеров](tasks/phase4-task1-gm-activation-api.md) — сохраняемый override, trigger state и master API под world gate
2. [Минимальная панель активности ГМ](tasks/phase4-task2-gm-activation-panel.md) — live controls в существующем списке существ
3. [Изоляция ошибок action от round loop](tasks/phase4-task3-action-error-containment.md) — failed `ActionResult` и WS-regression живой сессии
4. [Контракт Dash без мёртвого перемещения](tasks/phase4-task4-dash-action-contract.md) — metadata соответствует budget-only механике

---

## Status

**Current:** Phase 4 (Ручка ГМ + failure containment), task 3 done, task 4 pending.

## Decisions

- Граница Sprint 023: таксономия событий + lair write-back + trigger table + минимальная ручка ГМ. `inner-self`, `brain-gate-decide`, полная `detail-ladder`, квесты, реализм доставки информации и `gm-actives-panel` сверх минимума — за пределами спринта (2026-07-12).
- Разгрузка бэклога по просьбе оператора: `action-error-kills-round-loop`, `encounter-spawned-perceiver`, `dash-actiondef-movement-conflation` входят в scope как polish-айтемы фаз 1 и 4 (2026-07-12).
- `ENTITY_ATTACK_REQUESTED` — внутренняя команда resolution, `ENTITY_ATTACK` — завершённый мировой факт. Разделение принято вместо optional-полей в одном payload (2026-07-12).

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
