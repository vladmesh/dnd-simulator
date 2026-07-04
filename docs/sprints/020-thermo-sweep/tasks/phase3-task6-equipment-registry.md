# Task: Реестр экипировки — dict-модель + фабрика-хендлеры

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

> **Скоуп подтверждается координатором** (dispatch decision_gate «реестр экипировки»). По умолчанию — вариант A (бэкенд-internal дедуп, 12 ActionType сохранены, фронт не трогаем). Полный коллапс 12→2 ActionType ломает фронт (`InventoryPanel.tsx`/`actionCategories.ts` жёстко завязаны на per-slot экшн-типы) — это территория воркера фазы 4, отложено в бэклог. Если координатор выберет B/C — переписать эту задачу.

## Description

Экипировка размазана по 6 полям (`equipped_weapon`…`equipped_ring` на `Creature`, `core/character.py:226-231`), 12 ActionType (`EQUIP`/`UNEQUIP`/`EQUIP_ARMOR`/… `core/action_defs.py:301-413`), 12 рукописных обёрток-хендлеров (`rules/handlers/equipment.py:163-…`, каждая `return _handle_equip_slot(_X_CFG, ...)`) и 6-элементным `_EQUIPMENT_FIELDS` в сериализации (`core/player.py:56`). `SlotConfig`/`SLOT_CONFIGS` уже дают реестр слотов — но модель, хендлеры и action_defs его не используют.

Сделать (поведение и внешний контракт неизменны):

1. **Модель:** заменить 6 полей `equipped_*` на `equipped: dict[EquipmentSlot, Item]` на `Creature`. Сохранить `equipped_weapon`/`equipped_armor`/… как **compat-свойства** (`@property` read/write в `equipped[slot]`), чтобы `rules/weapons.py`, `rules/modifiers.py`, `service/commands_creatures.py:155`, сериализация и фронт-payload не менялись. Это ядро дедупа: один источник вместо шести.
2. **Хендлеры:** заменить 12 рукописных обёрток на фабрику. Либо `make_equip_handler(slot)`/`make_unequip_handler(slot)`, генерящие делегат к `_handle_equip_slot(SLOT_CONFIGS[slot], ...)`, либо единый диспетчер, читающий slot из `SLOT_CONFIGS` по ActionType. Реестр хендлеров (`handlers/__init__` или где регистрируются) строится циклом по `EquipmentSlot`.
3. **action_defs:** 12 `ActionDef` (`:301-413`) генерировать циклом по `SLOT_CONFIGS` вместо 12 копипаст-блоков. **12 ActionType остаются** (в `core/models.py`) — фронт-контракт.
4. **Сериализация:** `_EQUIPMENT_FIELDS`-цикл в `core/player.py`/`EntitiesLayer` переписать на итерацию по `equipped`-dict, ключ сериализации = slot-значение. Формат сейва неизменен (те же ключи `equipped_weapon` в JSON — пиновка round-trip из task 1).

Вне скоупа (вариант A): коллапс 12→2 ActionType, любые изменения `frontend/`, изменение shape player-status/awareness `EquippedInfo`. Если координатор одобрит B — отдельно менять `InventoryPanel.tsx`/`actionCategories.ts`/`types/api.ts` координируя с воркером фазы 4.

## Tests First

Поведение и формат неизменны — пиновка (GREEN до рефактора, есть в `test_equipment`/`test_handlers`):

- Экип оружия/брони/щита/head/feet/ring через соответствующий ActionType кладёт предмет в слот, снимает предыдущий в инвентарь, применяет модификаторы (AC от брони, `grant_modifiers` от аксессуара — эффективный AC меняется). Unequip возвращает в инвентарь и снимает модификаторы.
- `creature.equipped_weapon` (compat-свойство) читает/пишет то же, что `equipped[EquipmentSlot.WEAPON]`.
- Save→load: экипировка во всех 6 слотах переживает round-trip с идентичным JSON (те же ключи).
- Все 12 ActionType по-прежнему доступны в схеме действий (провайдер их отдаёт) — фронт-контракт цел.

## Implementation

1. Пиновка экип/анэкип по всем слотам + модификаторы + save-roundtrip (GREEN на текущей модели).
2. Модель: `equipped: dict` + compat-`@property` для 6 полей. Прогнать пиновку (всё зелёное — свойства прозрачны).
3. Хендлеры: фабрика вместо 12 обёрток; регистрация циклом.
4. action_defs: генерация 12 def циклом по `SLOT_CONFIGS`.
5. Сериализация: цикл по dict. Прогнать save-roundtrip (JSON байт-в-байт).

Gotcha: `equipped_*` compat-свойства должны поддерживать запись (`entity.equipped_weapon = weapon` в `commands_creatures.py:158`) — реализовать сеттер. Frozen dataclass? `Creature` — не frozen (мутабельные HP/conditions), но проверить, что `equipped`-dict инициализируется через `field(default_factory=dict)`. Порядок ключей в сериализации сохранить (пиновка round-trip). mypy: `dict[EquipmentSlot, Item]` — enum-ключи ок.

## Acceptance Criteria

- [ ] `Creature.equipped: dict[EquipmentSlot, Item]`; 6 `equipped_*` — compat-свойства (read+write)
- [ ] 12 рукописных обёрток-хендлеров заменены фабрикой/циклом
- [ ] 12 `ActionDef` генерируются циклом по `SLOT_CONFIGS`
- [ ] `_EQUIPMENT_FIELDS`-цикл сериализации переписан на `equipped`-dict; JSON неизменен
- [ ] 12 ActionType и фронт-контракт нетронуты (вариант A)
- [ ] Пиновка экип/модификаторы/save-roundtrip GREEN
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

Variant A, confirmed by coordinator via decision_gate. 12 ActionType + wire contract preserved; frontend untouched (phase 4 already merged, PR #26).

- **Model** (`core/character.py`): 6 `equipped_*` dataclass fields → `equipped: dict[EquipmentSlot, Item]` (single source) + six read/write compat properties (`equipped_weapon` etc.) over `_get_slot`/`_set_slot`. Setter with `None` pops the slot. All ~15 readers unchanged; `setattr(creature, "equipped_weapon", item)` in the equip handler and `entity.equipped_weapon = weapon` in commands go through the setter.
- **Construction migration**: `extract_all_equipped` now returns `dict[EquipmentSlot, Item]` (occupied slots only); `_to_player`/`_to_npc` pass `equipped=...`. ~10 test files migrated `Creature(equipped_weapon=x)` → `equipped={EquipmentSlot.WEAPON: x}` (the property can't be a dataclass init kwarg).
- **Handlers** (`rules/handlers/equipment.py`): 12 hand-written wrapper functions → `make_equip_handler(cfg)`/`make_unequip_handler(cfg)` factories + `EQUIPMENT_HANDLERS: dict[ActionType, handler]` built by looping `SLOT_CONFIGS`. `handle_equip`/`handle_unequip` (weapon) kept as named compat aliases for tests. Dispatcher registers via a loop over `EQUIPMENT_HANDLERS` (12 register lines → 2).
- **action_defs** (`core/action_defs.py`): 12 `_reg(ActionDef(...))` blocks → `_EQUIP_ACTION_SPECS` table (frozen `EquipActionSpec`) + a loop. Every N_() msgid and per-slot flag preserved verbatim (weapon slot keeps `ends_peaceful_turn=True` + `llm_hint`; others don't). i18n msgids unchanged (N_() literals still extractable from the table).
- **Serialization**: unchanged — `EQUIPMENT_FIELDS` iteration via the compat properties (getattr) produces byte-identical JSON keys (`equipped_weapon` etc.). No rewrite needed.
- **Deferral documented**: sprint.md Deferred + backlog `equip-action-collapse` (could, Tech Debt) + NB updated in `action-bar-unequip-i18n`.
- **Pins**: new `test_equipment_registry` (compat props read/write/clear; all 12 ActionDefs + factory registry present; weapon-slot special flags). `make check` green (backend 2369, mypy 160 files, frontend).
