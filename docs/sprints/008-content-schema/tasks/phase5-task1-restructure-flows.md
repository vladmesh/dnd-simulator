# Task: Restructure Player/Master World Flows

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 5 — DM World Management

## Description

Clean separation: players pick worlds, masters create/edit them.

**Player side (`SetupScreen`):**

- Remove "Build custom world" button and `WorldBuilder` step entirely. Player flow becomes: pick world → create session → create character.
- `SetupScreen` steps shrink from `"pick-world" | "build-world" | "create-character"` to `"pick-world" | "create-character"`.
- Keep `WorldPicker` — it lists available worlds and creates a session on pick.

**Master side (`WorldEditor`):**

- Remove fork-layer button from the stepper. All layers of a forked world are custom, so the stepper always shows editable `EntityListEditor` for every layer.
- Remove library/custom source badge distinction — if a layer happens to be library-sourced (base worlds), the editor shows read-only mode for the whole world (base worlds aren't editable). Forked worlds are always fully custom.
- Simplify: `WorldEditor` receives a `readOnly` prop. Base worlds open in read-only mode, forked worlds in edit mode. The per-layer fork button and source badges go away.

**Cleanup:**

- `WorldBuilder`, `LayerPicker`, `DetailsForm` components — delete if no longer referenced.
- Remove unused i18n keys from setup namespace if any.

## Tests First

- **SetupScreen:** render → no "Build custom world" button. Pick a world → goes straight to character creation (no build step).
- **WorldEditor read-only:** render with `readOnly=true` → no Add/Edit/Delete buttons in entity lists, no catalog picker.
- **WorldEditor editable:** render with `readOnly=false` → Add/Edit/Delete visible, catalog picker on ecology step.
- **No fork-layer button:** render WorldEditor → no "Fork" button anywhere in the stepper.

## Implementation

1. Simplify `SetupScreen.tsx` — remove `build-world` step and `WorldBuilder` import.
2. Add `readOnly` prop to `WorldEditor`. When true, pass `readOnly=true` to all `EntityListEditor` instances and hide catalog picker. Remove fork-layer logic from `WorldEditor`.
3. Update `MasterScreen` Worlds tab — pass `readOnly` based on whether the world is a base world (source detection TBD — could check if world dir has only library refs in manifest, or add an `editable` flag from backend).
4. Delete `WorldBuilder.tsx`, `LayerPicker.tsx`, `DetailsForm.tsx` if fully unused.
5. Clean up unused i18n keys.

## Acceptance Criteria

- [ ] Unit tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Player flow: pick world → create character (no builder)
- [ ] WorldEditor has no fork-layer button
- [ ] WorldEditor respects readOnly prop
- [ ] Unused components deleted
- [ ] `make check` passes

## Status

`pending`
