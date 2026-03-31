# Task: Frontend — Reaction Prompt + Disengage Indicator

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 3 — Frontend + Content

## Description

Wire the frontend to handle `reaction_prompt` WS messages and let the player respond.

1. **Reaction prompt overlay.** When server sends `reaction_prompt`, show a compact overlay/toast: "Enemy leaves your reach. Attack?" with two buttons (Attack / Skip). Compact — not a full modal, more like a banner or floating card at bottom. On click, send `{"type": "reaction", "name": "opportunity_attack", "params": {...}}` or `{"type": "reaction", "name": "skip"}` via WS. No timeout — Round blocks until player responds.

2. **Store handling.** Add `reactionPrompt: ReactionPrompt | null` to the turn slice. Set on `reaction_prompt` message, clear on submit. Add `submitReaction(name, params?)` that sends WS message and clears prompt state. Add `ReactionPrompt` type with trigger info and options.

3. **WS message routing.** Add `"reaction_prompt"` case to the message switch in `connectionSlice.ts`.

4. **Disengage indicator.** When the player has `is_disengaging` active (visible in awareness or budget), show a visual cue — a badge on BudgetDisplay or a status indicator — so the player knows movement won't provoke OA this turn. The `is_disengaging` flag should come from the awareness data; may need to add it to `_awareness_to_dict` on the backend if not already present.

## Tests First

**Component tests** (vitest + testing-library):
- ReactionPrompt component renders trigger description and option buttons
- Clicking "Attack" calls `submitReaction("opportunity_attack", {target_id: "x"})`
- Clicking "Skip" calls `submitReaction("skip")`
- Component not rendered when `reactionPrompt` is null
- Disengage indicator visible when `is_disengaging` is true in awareness

**Store tests** (vitest):
- `reaction_prompt` message sets `reactionPrompt` state
- `submitReaction` sends correct WS message and clears `reactionPrompt`

## Implementation

1. **Types** (`types/ws.ts`, `types/game.ts`) — add `ReactionPromptMessage` server→client type, `ReactionMessage` client→server type, `ReactionPrompt` data type with trigger + options.
2. **Store** (`store/slices/turnSlice.ts`) — add `reactionPrompt` state, `onReactionPrompt` handler, `submitReaction` action.
3. **Connection** (`store/slices/connectionSlice.ts`) — add `"reaction_prompt"` case to message router.
4. **ReactionPrompt component** (`components/game/ReactionPrompt.tsx`) — compact overlay with trigger description and option buttons. Positioned above ActionBar. Uses existing shadcn card/button patterns.
5. **GameScreen** — render `ReactionPrompt` when `reactionPrompt !== null`.
6. **BudgetDisplay** — show disengage indicator (e.g. shield icon with "Disengaged" tooltip) when active.
7. **Backend** (`service/session.py`) — add `is_disengaging` to awareness serialization if not present.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Player sees reaction prompt when OA is triggered
- [ ] Attack/Skip buttons send correct WS message
- [ ] Prompt disappears after choice
- [ ] Disengage status visible in UI when active
- [ ] No UI freeze — prompt blocks server, not client

## Status

`pending`
