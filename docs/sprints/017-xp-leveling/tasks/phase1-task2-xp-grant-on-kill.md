# Task: Wire XP to creatures and grant on kill

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 1 — XP & Leveling Core

## Description

Поля XP на модели и начисление при убийстве. `xp_value` хранится на каждом Creature (для монстров — из CR через `xp_for_cr`, для characters — 0 по умолчанию). `experience` и `level_up_available` на Character. При убийстве в `_handle_death` атакующий-Character получает XP и флаг `level_up_available` пересчитывается.

**Ключевые точки:**

1. **`Creature.xp_value: int = 0`** — добавить поле. `MonsterTemplate.spawn()` заполняет его через `xp_for_cr(self.cr)`. Characters остаются с 0.
2. **`Character.experience: int = 0`** и **`Character.level_up_available: bool = False`** — добавить поля.
3. **`_handle_death` в `combat_manager.py`** — после existing reputation drop блока:
   - Если `isinstance(attacker, Character)` и `target.xp_value > 0`: `attacker.experience += target.xp_value`, пересчитать `attacker.level_up_available = can_level_up(attacker.experience, attacker.level)`.
   - Эмитить `Event(EventType.XP_GAINED, ...)` с `entity_id`, `amount`, `new_total`, `source_entity_id`, `level_up_available`.
4. **`EventType.XP_GAINED`** — добавить в enum.
5. **Save/load** — `Character.to_save_data()` / `from_save_data()` (или аналог) включает новые поля.

## Tests First

`tests/integration/test_xp_grant.py`:

1. **Kill monster — XP gained**
   - Spawn Character L1 (experience=0), spawn monster CR 1/4 (50 XP) в бою. Character убивает. После `_handle_death`: `character.experience == 50`, `level_up_available == False`, событие `XP_GAINED` в логе локации с `amount=50`.
2. **Kill enough to level up**
   - Character L1 с experience=280, убивает CR 1/4 (50 XP). `experience == 330`, `level_up_available == True`. Level не меняется сам — только флаг.
3. **Kill character — no XP**
   - Character kills другого Character (у которого xp_value=0). `experience` не меняется, `XP_GAINED` не эмитится.
4. **Monster kills character — no XP**
   - Monster убивает Character. Monster не Character, XP не начисляется. (Защита от `isinstance` ветки.)
5. **XP persists через save/load**
   - Character с experience=450, level_up_available=True. Save → load → значения совпадают.
6. **MonsterTemplate.spawn ставит xp_value из CR**
   - Template с cr=2.0 → spawned creature с `xp_value == 450`.

Unit-тест `tests/unit/test_combat_manager_xp.py` можно добавить если хочется изолированно, но интеграционного достаточно — `_handle_death` нужен реальный combat context.

## Implementation

**Файлы:**

- `src/dnd_simulator/core/character.py`:
  - В `Creature`: `xp_value: int = 0` (frozen? Creature уже non-frozen — просто поле).
  - В `Character`: `experience: int = 0`, `level_up_available: bool = False`.
- `src/dnd_simulator/core/monster.py`:
  - `MonsterTemplate.spawn()` — установить `xp_value=xp_for_cr(self.cr)`. Импорт lazy или top-level: `rules/leveling` не тянет ничего из `core`, циклов нет → top-level ок.
- `src/dnd_simulator/core/models.py` (или где `EventType`):
  - `XP_GAINED = "xp_gained"`.
- `src/dnd_simulator/layers/entities/combat_manager.py` `_handle_death`:
  - После reputation drop блока (строка ~440): если attacker — Character и target.xp_value > 0 → начислить, выставить флаг, эмитить event.
  - Импорт `can_level_up` из `rules/leveling`.
- `src/dnd_simulator/core/player.py` `to_save_data` / соответствующий `from_save_data` — включить experience, level_up_available.
- `src/dnd_simulator/content_loader/creatures.py` — если при load задаётся experience/level_up_available из YAML (dungeon master может проставить) — поддержать, иначе дефолты.

**Gotchas:**

- `Character` это `Npc` и `PlayerCharacter` — оба наследники. Поля на базовом Character ок.
- Monster NPC (созданы через `Npc` класс напрямую из YAML, не MonsterTemplate) — у них xp_value=0 → XP не даётся. Это ок для Phase 1: все боевые противники спавнятся из MonsterTemplate через squad materialization. Если есть статичные враги-Npc в YAML (guards и т.п.) — они остаются с 0 XP. Помечаем в сomment.
- Perception для XP_GAINED в Phase 1 не нужен (нет UI). Handler добавим в Phase 3.

## Acceptance Criteria

- [ ] Integration тесты написаны и RED
- [ ] Поля добавлены: `Creature.xp_value`, `Character.experience`, `Character.level_up_available`
- [ ] `MonsterTemplate.spawn` заполняет `xp_value` из CR
- [ ] `_handle_death` начисляет XP и эмитит `XP_GAINED` event
- [ ] Save/load поддерживает новые поля
- [ ] Все тесты GREEN, `make check` проходит
- [ ] Никакого UI / API изменений в этой задаче (только модель + combat)

## Status

`done`

## Developer Notes

- Added `Creature.xp_value` (default 0) and `Character.experience` / `level_up_available` (defaults 0/False).
- `MonsterTemplate.spawn()` uses a lazy import for `rules/leveling.xp_for_cr` to match the existing core→rules pattern (`class_features.py` does the same for `fighting_style`).
- `_handle_death` grants XP only when attacker is Character and target.xp_value > 0. Uses `can_level_up()` to set flag. Emits `EventType.XP_GAINED` with `entity_id`, `amount`, `new_total`, `source_entity_id`, `level_up_available`.
- `PlayerCharacter.to_save_data` / `load_save_data` now roundtrip experience + level_up_available.
- Chose unit test in `tests/unit/test_xp_grant_on_kill.py` over integration (task allowed either) — drives `_handle_death` directly, matches pattern of `test_wire_sides_combat.py`. 7 tests, no integration-test runtime cost.
- `make check` green: 2093 backend + 220 frontend.
