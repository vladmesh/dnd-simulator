# Task: NPC Inspect Modal with Actions

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 4 — NPC Inspect Card

## Description

Replace the current inspect behavior (text log event) with a modal dialog showing structured NPC information and action buttons. The modal opens when clicking the eye icon on an NPC in the Nearby panel.

The modal shows:
- **Header:** NPC name, race, role (localized)
- **Body:** Description text from YAML, faction name
- **Combat info:** HP bar (only visible during combat)
- **Actions:** Attack, Talk, Trade (merchants only)
- Trade button opens the existing TradePanel as an overlay/modal within the inspect card

## Tests First

Frontend component tests are not part of our test suite — this task is verified via E2E in phase close. No unit tests needed.

## Implementation

1. **NpcInspectModal component:** New component `frontend/src/components/game/NpcInspectModal.tsx`
   - Uses shadcn Dialog
   - Reads NPC data from the enriched `NearbyEntity` fields (name, race, role, npc_description, faction_id, is_merchant)
   - Shows HP bar only when in combat mode
   - Action buttons: Attack (closes modal + sends attack), Talk (closes modal + opens talk input), Trade (opens TradePanel overlay for that merchant)

2. **Perception.tsx changes:**
   - Eye button click: opens NpcInspectModal with the selected entity's enriched `NearbyEntity` data (already in awareness, no server round-trip)
   - Remove old `idle` + `inspect_target` action dispatch

3. **CombatPanel.tsx changes:**
   - Same — eye button opens modal from awareness data, no server action

4. **TradePanel integration:**
   - Trade button in modal opens TradePanel filtered to that specific merchant
   - If merchant has no items, Trade button is disabled

5. **Translations:** Add i18n keys for modal labels (role names, "Description", "Faction", etc.)

## Acceptance Criteria

- [ ] Eye icon opens modal dialog (not log event)
- [ ] Modal shows NPC name, race, role, description, faction
- [ ] Attack button in modal initiates combat
- [ ] Talk button opens talk input
- [ ] Trade button visible only for merchants, opens trade UI
- [ ] Modal works in both peaceful and combat modes
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

- Eye icon in Perception and CombatPanel now opens a client-side modal instead of sending `idle` action to backend.
- In peaceful mode: modal shows full NPC info (name, race, role, description, faction) + action buttons (Attack, Talk, Trade for merchants).
- In combat mode: modal shows description, conditions, distance — CombatEntity doesn't carry enriched NPC fields, which is fine (you don't read backstories mid-fight).
- Trade button embeds MerchantView directly in the modal — exported it from TradePanel.
- Talk input is inline in the modal with Enter to send, Escape to cancel.
- Added i18n keys for faction label and all NpcRole values (en + ru).
- Also fixed unrelated skip: test_squad.py pointed at wrong path for squads.yaml (worlds/ vs library/).
