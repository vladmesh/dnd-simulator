# Task: combat_manager split + make_relation_fn helper

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

## Description

`combat_manager.py` (481) смешивает управление combat-state (start/end/remove, load/save) с резолвом действий (attack/move/dodge/flee) и хэндлингом смерти. Плюс адаптер `query_fn → FactionRelation` руками написан 4× в 6 сайтах и уже разошёлся (NEUTRAL-default против assert).

Сделать (поведение неизменно):

1. **`make_relation_fn(query_fn)` в `rules/reputation.py`.** Дедуп 6 сайтов: `combat_manager.py:101(start_combat),405(_handle_death)`, `awareness_builder.py:346,375`, `activation_manager.py:281(_maybe_start_combat)`. Функция возвращает `Callable[[str, str], FactionRelation]`, читающий `QueryType.FACTION_RELATION` через query_fn. Единое поведение при отсутствии ответа (сейчас часть сайтов ассертит, часть дефолтит в NEUTRAL — зафиксировать одно, задокументировать). `combat_manager` также строит relation по существам (`get_creature_relation`, `:105`) — оставить тонкую обёртку поверх `make_relation_fn`, читающую `faction_id`.
2. **Разделить initiative/turn-механику от combat-state.** Вынести резолверы действий (`resolve_dodge/resolve_flee/resolve_move/resolve_attack`, `:215-363`) и `_handle_death` (`:374-451`) в отдельный модуль (напр. `combat_resolution.py` в `layers/entities/`) как функции/тонкий класс над состоянием; `CombatManager` остаётся владельцем combat-state (start/end/remove/get/load/save, `:61-213,453-473`). Держать существующие точки входа `CombatManager.resolve_*` тонкими делегатами, чтобы вызывающие (query_handler/handlers) не менялись — либо перенести вызовы, если их немного.

Вне скоупа: смена контракта событий боя, логика инициативы как таковая, `combat_serialization.py` (уже отдельный).

## Tests First

Поведение неизменно — пиновка боевых цепочек (GREEN до рефактора, большинство уже есть в `test_combat_manager`/`test_round`):

- Атака: попадание/промах по AC, урон, смерть цели, начисление XP атакующему-Character, `xp_gained`-событие, drop репутации по killed. Auto-старт боя при атаке вне combat со сторонами через `forced_opponents`.
- Combat sides: два враждебных по фракции существа попадают на разные стороны; союзные — на одну.
- Новое (RED→GREEN): `make_relation_fn(query_fn)("faction_a","faction_b")` возвращает тот же `FactionRelation`, что читает `QueryType.FACTION_RELATION`; на неизвестной паре — задокументированный дефолт.
- Dodge/flee/move-резолверы дают тот же `ActionResult`, что до рефактора (пиновка через существующие тесты).

## Implementation

1. `make_relation_fn` в `rules/reputation.py` + unit-тест. Заменить 6 сайтов, убедиться что дивергенция (assert vs NEUTRAL) осознанно схлопнута в один вариант.
2. Вынести резолверы+death в `combat_resolution.py`; `CombatManager` делегирует. Прогнать `test_combat_manager`, `test_round`, боевые integration.

Gotcha: `make_relation_fn` живёт в `rules/` (чистая, без I/O — query_fn инъектируется аргументом, не импортируется). `activation_manager.py:281` и `awareness_builder.py` — потребители в разных модулях; менять их можно в этой же задаче (все читают один helper). Согласовать дефолт с фактическим поведением на проде, чтобы не сдвинуть авто-враждебность.

## Acceptance Criteria

- [ ] `make_relation_fn` в `rules/reputation.py`, 6 рукописных closures удалены
- [ ] Резолверы действий + death вынесены из `CombatManager`; combat-state остался владельцем
- [ ] Боевые пиновочные тесты (attack/xp/kill-rep/sides/dodge/flee/move) GREEN
- [ ] `combat_manager.py` заметно короче (дельта в Developer Notes)
- [ ] `make check` зелёный

## Status

`pending`
