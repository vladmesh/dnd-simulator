# Sprint 020 — Control Interfaces

**Goal:** Спроецировать единое control-ядро (content_loader + GameService + session) на три роли — worldbuilder / DM / админка — через минимальную модель идентичности и spectator-listener; попутно закрыть кластер session/save-багов и i18n-лога.

**Started:** 2026-06-29

## Context

Sprint 019 (control-plane-prep) отвердил ровно тот кластер, который этот спринт режет: `GameService` 1044 → 357 (миксины `WorldBuilderCommands`/`PlayerCommands`), тест-сетка на `session.py` (listener dispatch, round lifecycle), core/adapter развязаны. Взлётная полоса построена — теперь строим.

[control-interfaces.md](../../brainstorms/control-interfaces.md) формулирует три **человеческих** управляющих интерфейса как **три линзы над одним ядром**, не три приложения. Сейчас весь управляющий функционал свален под `/api/master/*` **без авторизации** — объединение всех трёх линз без перегородок. Физически он уже разрезан на три файла (`routes_content.py` = авторинг, `routes_world.py` = сборка/fork, `routes_session.py` = hot-controls + снапшот) — чистый seam для разреза по ролям.

Порядок по зависимостям из брейншторма: **identity (keystone) → spectator-listener → multiplayer → DM policy**. Этот спринт берёт первые две ступени на **минимальном весе** и сознательно откладывает две самые тяжёлые:

- **Identity — минимальный вес.** Роль + creator-тег на мирах + request-seam «кто звонит» (header/config-driven, без паролей/login/БД). Достаточно, чтобы выразить три линзы и разрезать `/api/master/*`. Открытый вопрос «file-namespace vs БД» из брейншторма не решаем — остаёмся на файлах с creator-тегом.
- **Spectator-listener** — read-only подписка на события сессии, развязанная от `PlayerBrain`/WS-игрока. Самый дешёвый разблокиратор: нужен DM (наблюдать стол), админке (наблюдать парк) и будущим зрителям-игрокам. Едет в `session.py` — ровно туда, где 019 положил тест-сетку.

Попутно закрываем кластер багов, тематически совпадающий с трогаемым кодом: **`session-disconnect-debounce`** (grace-period evict — та же listener-lifecycle поверхность, что и spectator), **`player-xp-not-persisted`** (save-путь теряет XP), **`master-panel-creature-inventory`** (DM/админка-наблюдению нужны предметы существ), **`combat-log-i18n-gaps`** (лог, который читают новые наблюдатели).

**Out of scope** (отдельные спринты или позже): мультиплеер (N PlayerBrain + приватность awareness — архитектурно самое тяжёлое, по брейншторму кандидат в свой спринт), полноценная auth/login/БД, DM policy-лимиты «нудж в пределах», «приключение как бандл». Большие type-свипы (`any-to-object-sweep`, `dict-str-object-overuse`) остаются в бэклоге.

**Ссылки:** [control-interfaces](../../brainstorms/control-interfaces.md), [game-loop-and-master](../../brainstorms/game-loop-and-master.md), [frontend-architecture](../../brainstorms/frontend-architecture.md), [BACKLOG](../../BACKLOG.md), [VISION](../../VISION.md)

## Phase 1: Identity & role keystone ✓

Минимальная модель идентичности — камень в основании, без которого три линзы не формулируются. `Role` (worldbuilder / DM / admin / player), owner-тег на мирах, request-seam, который резолвит «кто звонит» (header/config-driven, без паролей). Плюс минимальный фронт-селектор личности/роли, чтобы следующие фазы тестировались через UI.

**Что доставляет:** создание мира пишет owner; сервер резолвит identity → role; seam отклоняет невалидную роль (400). Линза-разрез фазы 2 опирается на это — потому первым.

**Tasks:**

1. [World creator field](tasks/phase1-task1-world-ownership.md) — `creator`-тег на манифесте (raw-dict, атрибуция без enforcement): плумбинг через `assembly`/`manifest`/`WorldBuilderCommands`/схемы; fork re-attributes, backward-compat `creator==""`, базовые миры `creator: system`
2. [Identity & role resolution seam](tasks/phase1-task2-identity-seam.md) — `service/identity.py` (`Role` StrEnum, `Identity`, `resolve_identity`) + `get_identity` FastAPI-dependency (header `X-User-Id`/`X-Role`, invalid role → 400) + стамп `creator` из вызывающего на world-create/fork + `meta.created_by` на session-create
3. [Frontend identity/role selector + header propagation](tasks/phase1-task3-frontend-identity-selector.md) — `identitySlice` (persist) + инъекция заголовков в `apiClient`/`wsClient` + селектор на `LandingPage`

## Phase 2: Three-lens projection of `/api/master/*`

Разрезать безавторизационный god-mode по ролям поверх уже физически разделённых route-файлов. Worldbuilder — авторинг, скопленный своими мирами. DM — авторинг + наблюдение живой сессии + hot-controls. Админка — read-only кросс-сессионный срез + техглубина. Фронт направляет каждую роль в свою линзу. Фолдит `master-panel-creature-inventory` (`CreatureResponse`/`all_entities` отдают inventory/equipped — данные DM/админка-наблюдения).

**Что доставляет:** worldbuilder не трогает чужой мир; DM наблюдает + нуджит; админка получает read-only park-view; предметы существ видны в мастер-панели.

Срез **projection-only** (по решениям спринта: creator = атрибуция, роль «not enforced yet»): линза меняет, что UI показывает/скейпит, бэкенд остаётся открытым god-mode (тонкие scoping-хелперы, без 403). `master-panel-creature-inventory` уже доставлен (бэк + edit-диалог со спринта 007) — фолдим только остаток: inline-показ предметов в read-only observation-списке.

**Tasks:**

1. [Backend lens-scoping primitives](tasks/phase2-task1-lens-scoping-backend.md) — `list_worlds(creator=)` фильтр + `?creator=` query-param; `list_sessions` обогащён `created_by`/`time`. Аддитивно, без enforcement.
2. [Frontend worldbuilder/DM lens](tasks/phase2-task2-frontend-worldbuilder-dm-lens.md) — роутинг по роли; worldbuilder = авторинг своих миров (без Sessions); DM = свои миры + свои сессии (`created_by`) + hot-controls; fallback на текущий экран
3. [Admin park lens + inline inventory](tasks/phase2-task3-admin-park-lens-inline-inventory.md) — admin read-only кросс-сессионный/кросс-мировой срез (атрибуция + время, write-контролы сняты, `SessionView` observe-only) + inline-предметы существ в observation-списке; закрывает остаток `master-panel-creature-inventory`

## Phase 3: Spectator-listener + disconnect-debounce

Read-only подписка на поток событий живой сессии, развязанная от `PlayerBrain`/WS-игрока — извлекается раз, используется трижды (DM-наблюдение, админка-парк, будущие зрители). Фолдит `session-disconnect-debounce` (grace-period evict): та же listener-lifecycle в `session.py`, чиним пока внутри.

**Что доставляет:** не-игровой WS подписывается и read-only получает события; быстрый disconnect+reconnect больше не выселяет сессию (grace-period отменяет evict при reconnect в окне).

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 4: Save robustness & i18n polish

Закрыть оставшийся кластер багов и почистить лог, который читают новые наблюдатели. `player-xp-not-persisted` — сериализовать `experience`/`level_up_available` через `to_full_save_data` + `PlayerContent`/`_to_player`. `combat-log-i18n-gaps` — английские item/faction-имена внутри RU-строк (i18n-свип). Сверка бэклога.

**Что доставляет:** XP/level_up переживают save/reload (и dev StrictMode evict→restore); RU боевой лог полностью локализован; `make check` зелёный.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 2 (Three-lens projection) tasks generated — 2026-06-29. Phase 1 COMPLETE. Phase 2 is a **projection-only** cut (3 tasks): backend scoping primitives → frontend worldbuilder/DM lens → admin park lens + inline inventory. `master-panel-creature-inventory` confirmed already delivered (sprint 007); only its inline-observation remnant folds into task 3. Ready to start task 1.

## Decisions (Phase 2)

- **Projection-only, no backend enforcement.** (2026-06-29, phase 2 planning) The lens cut changes what each role's UI scopes/offers; `/api/master/*` stays open god-mode with thin scoping helpers (`?creator=` filter, session-list `created_by`/`time`), no 403s. Consistent with phase-1 decisions (creator = attribution; role "not enforced yet"). Hard access enforcement waits for the M2M/DB sprint.
- **`master-panel-creature-inventory` was already fixed.** Backend `_entity_detail` has returned `inventory`/`equipped_weapon` since sprint 007 (`c5fe924`); `CreatureForm` has rendered them since sprint 007 (`7976363`). The backlog claim ("query doesn't include the fields") is stale. Only real remnant: items not shown inline in the read-only observation list — folded into task 3, backlog item marked resolved there.

## Decisions

- **`creator` (атрибуция), не `owner` (контроль доступа).** (2026-06-29, по ходу task 1) Поле на манифесте называется `creator` и означает «кто создал шаблон» — неизменяемая атрибуция, НЕ право доступа. Кто может смотреть/редактировать/играть — отдельное измерение, которое поедет «в другую сторону» как many-to-many (юзер ↔ ресурс), вероятно в БД. В файлы семантику доступа не зашиваем. Публичные миры = есть создатель, нет ограничения. Базовые миры: `creator: system`. Та же логика на сессиях: `meta.created_by` (атрибуция, без enforcement) — task 2.
- **Identity на минимальном весе, не full auth.** Роль + creator-тег + header/config seam, без login/паролей/БД. Достаточно выразить три линзы и разрезать `/api/master/*`; открытый вопрос брейншторма «file-namespace vs БД» не решаем — остаёмся на файлах. Видение «библиотека миров + приватные сессии» — главный аргумент в сторону БД, когда дойдём.
- **Мультиплеер и полная auth — отдельными спринтами.** По брейншторму мультиплеер «архитектурно самое тяжёлое, возможно в свой спринт». Этот спринт берёт identity (keystone) + spectator (дешёвый разблокиратор), две тяжёлые ступени откладывает.
- **Баги распределены по тематическим фазам, не в отдельный bug-dump.** Каждый баг садится в код, который его фаза и так трогает: disconnect-debounce → spectator/session-listener (фаза 3), master-panel-creature-inventory → DM/админка-наблюдение (фаза 2), player-xp-not-persisted + combat-log-i18n → save/лог-полировка (фаза 4).
- **Spectator-listener — приоритет №2 после identity.** Read-only подписка нужна сразу двум линзам (DM + админка); едет в `session.py`, отвердённый тест-сеткой 019.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
