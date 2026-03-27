# Phase 2 E2E Report

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 2 — Log Formatting

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Compact log strip shows last 5 events | Events visible in strip below header | Events render with icons, colors, proper formatting | pass |
| Attack events colored red with sword icon | Red text + swords icon | Correct | pass |
| Say events colored blue with message icon | Blue text + message-circle icon | Correct | pass |
| Death events bold red with skull icon | Bold red + skull icon | Correct | pass |
| Use item events purple with flask icon | Purple text + flask-round icon | Correct | pass |
| Second wind events green with heart icon | Green text + heart-pulse icon | Correct | pass |
| Combat started/ended events with icons | Orange flame / green flag | Correct | pass |
| Aggregated moves collapse consecutive moves | Single line with total distance | "player_1 moved (45 ft)" for 3 moves (10+15+20) | pass |
| Aggregated moves expand on click | Show individual sub-entries | 3 sub-entries with footprint icons shown | pass |
| Move + dash aggregate together | Combined into single entry | "player_1 moved (35 ft)" for move(5) + dash(30) | pass |
| Turn headers separate actors in combat | Horizontal divider with actor ID | "PLAYER_1", "GOBLIN_1" headers rendered | pass |
| Full log overlay with virtualization | All entries visible, scrollable | 13 entries rendered correctly | pass |
| Empty log shows nothing (no crash) | Empty strip, no errors | Correct — strip area present but empty | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world | pass | Both Sword Vale and Test Valley load correctly |
| Create character | pass | Character creation with custom stats works |
| Dashboard layout | pass | All 3 panels visible, header + action bar work |
| Move between locations | pass | Navigation via location buttons works |
| End turn | pass | Turn advances, new turn received |
| Log overlay expand/close | pass | Expand button opens overlay, close dismisses it |

## Quick Fixes Applied

- Fixed `getDistanceFt()` in `logProcessing.ts`: backend sends move distance as `data.ft`, not `data.distance_ft`. Added fallback: `event.data?.distance_ft ?? event.data?.ft`
- Fixed flaky test `test_flee_removes_from_turn_order`: characters had low HP (15), longsword crit (16 dmg) could kill them, causing combat to end unexpectedly. Bumped HP to 50.

## Log Analysis

- No console errors in frontend
- No backend errors beyond pre-existing `KeyError: 'target_id'` in attack handler (attack action sent without target params — pre-existing bug, not phase 2 related)
- Peaceful mode rounds produce 0 events (`tick_events: 0`), so the log strip is empty until combat or other actions generate events. This is expected behavior.

## Blockers

None.

## Minor Issues

- Turn headers and aggregated move summaries display `actor_id` (e.g. "player_1") instead of human-readable names. Backend `PerceivedEvent` doesn't include `actor_name`. Low priority — backlog candidate.
- Virtualized full log has minor overlap when aggregated move is expanded (height estimate slightly off). Cosmetic only.
- Attack action bar button sends action without `target_id` param → backend `KeyError`. Pre-existing bug, not phase 2.
