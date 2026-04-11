# Task: Frontend Target Scope Routing

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 6 — Action Target Scope

## Description

Update the frontend to use `target_mode` and `target_scope` from the backend instead of checking `hasParam("target_id")`. Filter the target list by scope and add "Self" option for ALLY/ANY scopes.

**TypeScript type changes (`types/game.ts`):**
- Add `target_mode?: string` and `target_scope?: string` to `ActionInfo`.

**ActionButton routing (`action-bar/ActionButton.tsx`):**
- Replace `hasParam(action, "target_id")` check with `action.target_mode === "single"`.
- Pass `target_scope` to `TargetDropdown`.

**TargetDropdown changes (`action-bar/TargetDropdown.tsx`):**
- Accept `scope` prop.
- Filter `enemies` (rename to `targets`/`nearby`) by scope:
  - `hostile` → only `is_hostile === true`
  - `ally` → only `is_hostile !== true` (includes self)
  - `any` → all nearby + self
- For `ally`/`any` scope: prepend a "Self" entry (use creature's own ID from awareness).
- Variable naming: `enemies` prop → `nearby` (matches the data source).

**ActionBar (`ActionBar.tsx`):**
- Pass full `nearby` list instead of only `enemies`. The filtering now happens inside TargetDropdown based on scope.

**Self ID:** The awareness already contains `self_id` (or equivalent). Pass it through to TargetDropdown so the "Self" entry can use the correct ID. Check what field name awareness uses.

## Tests First

1. **ActionButton renders TargetDropdown for `target_mode: "single"`:** ActionInfo with `target_mode: "single"` + nearby entries → renders TargetDropdown. ActionInfo with `target_mode: "none"` → renders simple button.
2. **HOSTILE scope filters to hostile targets only:** TargetDropdown with scope `hostile` and mixed nearby (some hostile, some not) → only hostile entries shown.
3. **ALLY scope shows allies + self, hides hostiles:** TargetDropdown with scope `ally` and mixed nearby → only non-hostile entries + "Self" entry shown.
4. **ANY scope shows everyone + self:** TargetDropdown with scope `any` → all nearby + "Self" shown.
5. **Self entry sends correct target_id:** Clicking "Self" sends `{ target_id: self_id }`.

## Implementation

1. Update `ActionInfo` type in `types/game.ts` — add `target_mode`, `target_scope`.
2. Update `ActionBar.tsx` — pass `nearby` instead of just enemies.
3. Update `ActionButton.tsx` — route by `target_mode === "single"` instead of `hasParam("target_id")`.
4. Update `TargetDropdown.tsx` — accept `scope` and `selfId` props, filter by scope, add Self entry.
5. Update existing frontend tests for the changed prop names and routing logic.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Lay on Hands shows "Self" + allies in target dropdown
- [ ] Attack shows only hostile targets
- [ ] No hardcoded `hasParam("target_id")` checks remain in target routing

## Status

`pending`
