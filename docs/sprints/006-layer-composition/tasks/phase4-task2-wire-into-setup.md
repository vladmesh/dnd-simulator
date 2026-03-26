# Task: Wire WorldBuilder into SetupScreen + E2E Verification

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 4 — World Assembly Frontend

## Description

Integrate the WorldBuilder wizard into the existing SetupScreen as an alternative to the quick-start WorldPicker. The setup screen gets a mode toggle: "Quick Start" (existing WorldPicker — pick a pre-built world) vs "Custom World" (WorldBuilder wizard). After the wizard assembles a world and creates a session, the flow continues to CharacterForm as before.

Also verify the full end-to-end flow works: user opens the frontend, uses the custom world builder, creates a character, and enters the game.

## Tests First

Integration test (added to `tests/integration/test_library_and_assembly.py`):

1. **Assembled world full lifecycle** — assemble a world from test templates, create a session, create a player character in it, verify player status shows correct location. Then verify the session appears in session listing with the correct world name. This tests the complete pipeline the UI relies on.

## Implementation

### SetupScreen changes (`frontend/src/components/setup/SetupScreen.tsx`)

Update the `Step` type to include a "build-world" step:
- `Step = "pick-world" | "build-world" | "create-character"`
- On the "pick-world" step, add a button/link: "Build Custom World" that sets step to "build-world"
- The "build-world" step renders `<WorldBuilder onWorldAssembled={...} onBack={...} />`
- `onWorldAssembled(sessionId)` transitions to "create-character" (same as WorldPicker flow)
- `onBack()` goes back to "pick-world"

### i18n additions

Add remaining i18n strings for the mode toggle and any missing wizard labels:
- `build_custom_world` — button label
- `back_to_worlds` — back link in wizard

### E2E manual verification checklist

Since there's no Playwright setup, E2E is manual but the integration tests cover the API chain:
- User lands on setup screen, sees both "Quick Start" worlds and "Build Custom World" option
- Clicking "Build Custom World" opens the wizard
- Wizard steps through all 5 layers with template cards
- Back button navigates to previous step
- Final step creates world + session, transitions to character creation
- Character creation and game entry work normally

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] SetupScreen has "Build Custom World" option alongside quick-start
- [ ] WorldBuilder integrates into the setup flow without breaking existing WorldPicker
- [ ] Session created from assembled world transitions to CharacterForm
- [ ] Full game flow works: build world -> create character -> play
- [ ] i18n strings present in both en and ru

## Status

`done`

## Developer Notes

All deliverables were completed in task 1 since the SetupScreen wiring, i18n strings, and full-lifecycle integration test naturally fell into the same unit of work. SetupScreen has the `build-world` step, WorldBuilder wired with `onWorldAssembled` and `onBack` callbacks, `build_custom_world` button on the pick-world screen. The `test_full_wizard_sequence` integration test covers the complete assembled-world lifecycle (assemble -> session -> player -> verify listing).
