# Task: Smite Choice UI in Attack Flow

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 7 — Smite UI + Level 1 Spell Slot

## Description

After selecting an attack target, if the player has spell slots with remaining uses, show an intermediate choice: "Attack" (normal) vs "Attack + Smite (slot N)" for each available slot level. If no spell slots or all depleted — skip straight to normal attack (current behavior).

The `smite_slot_level` param already exists on the attack ActionDef and flows through combat_manager → divine_smite rules. This task only adds the frontend UI to set it.

## Tests First

- Frontend unit test: when `self_resource_pools` includes a spell slot with `current_uses > 0`, clicking attack on a target shows smite options instead of immediately sending the action.
- Frontend unit test: when no spell slots exist, clicking attack target sends action immediately (no intermediate step).
- Frontend unit test: selecting "Attack + Smite (slot 1)" sends `sendAction("attack", { target_id, smite_slot_level: 1 })`.
- Frontend unit test: selecting "Attack" (no smite) sends `sendAction("attack", { target_id })` without `smite_slot_level`.
- Frontend unit test: depleted spell slots (current_uses === 0) are shown but disabled.

## Implementation

1. **Thread `self_resource_pools` to ActionButton**: `ActionBar` reads `awareness.self_resource_pools`, passes to `ActionButton` (only for attack action), which passes to `TargetDropdown`.

2. **SmiteChoiceDropdown component** (or inline in TargetDropdown): After target is selected, if spell slots exist, show a nested menu. Options: "Attack" + one "Attack + Smite (slot N)" per slot level with remaining uses. Depleted slots shown greyed out.

3. **TargetDropdown change**: Instead of calling `sendAction(name, { target_id })` directly on target click, check if smite options should be shown. If yes → enter "smite choice" state with the selected target_id stored. If no → send immediately as before.

4. **i18n**: Add translation keys for smite option labels.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Attack button with spell slots shows smite choice after target selection
- [ ] Attack button without spell slots works as before (no intermediate step)
- [ ] Smite choice sends correct `smite_slot_level` param
- [ ] Depleted slots are visually disabled

## Status

`done`

## Developer Notes

Implemented smite choice as a two-step flow in TargetDropdown:
1. Player clicks attack → selects target (single auto-select or multi dropdown)
2. If spell slots exist with `spell_slot_*` IDs → show intermediate smite choice panel (`data-testid="smite-choice"`) with "Attack" (normal) and "Attack + Smite (slot N)" per slot level
3. If no spell slots → send attack immediately (unchanged behavior)

Data flow: `awareness.self_resource_pools` → ActionBar reads it → passes as `spellSlots` prop → ActionButton → TargetDropdown. Only attack actions with `spell_slot_*` pools trigger the smite choice. Depleted slots (current_uses === 0) are shown greyed out and disabled.

No old tests modified — all 16 existing ActionButton tests pass unchanged. Added 5 new smite choice tests.
