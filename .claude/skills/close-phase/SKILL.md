---
name: close-phase
description: >
  Close the current sprint phase: run integration tests (add new ones if needed), run E2E via Playwright
  with full debug, write a report, and mark the phase complete if no blockers. Use when user says
  "close phase", "finish phase", "phase done", "e2e", "run e2e", "test the phase", "verify phase",
  or when all tasks in a phase are marked done and it's time to validate before moving on.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Close Phase

Validate and close the current sprint phase. Integration tests → E2E via Playwright → report → close (or block).

## What this skill does NOT do

- Implement tasks (use `/implement`)
- Plan the next phase (use `/plan-phase`)
- Close the sprint (use `/close-sprint`)

## Protocol

### 1. Find the current phase

Read `docs/sprints/` — highest-numbered folder. Read `STATUS.md` and `sprint.md`.

**If no active sprint or current phase** — stop, nothing to close.

**If any tasks in the phase are still `pending` or `in_progress`** — stop, tell the user which tasks aren't done yet.

### 2. Integration tests

Run the existing integration tests:

```bash
make test-integration
```

If they fail — analyze and fix. Same contract logic as in `/implement`: understand why they fail before changing anything.

Then review what the phase added and determine if new integration tests are needed. If the phase introduced:

- New API endpoints → add REST tests
- Changed WebSocket protocol → add/update WS tests
- New game mechanics visible through API → add tests that exercise them

Write and add the new integration tests. Run again until green:

```bash
make test-integration
```

### 3. E2E via Playwright

This is manual-ish testing through the actual UI with Playwright MCP, with full debug logging.

#### 3a. Restart the stack with debug

Kill any running stack and start fresh with full debug:

```bash
# Kill existing
docker compose down 2>/dev/null; pkill -f uvicorn 2>/dev/null; pkill -f vite 2>/dev/null
sleep 2

# Start backend with debug + file logging
mkdir -p /tmp/dnd-e2e-logs
LOG_LEVEL=DEBUG LOG_DIR=/tmp/dnd-e2e-logs make serve &

# Start frontend
make frontend &

# Wait for both to be ready
sleep 5
```

#### 3b. Test the NEW functionality

Using Playwright MCP tools, navigate to the app and test what the phase delivered. This is the primary goal — verify the new feature works end-to-end through the real UI.

For each test scenario:
1. Describe what you're about to test and what you expect
2. Perform the actions via Playwright
3. Record what happened (screenshots, console output, logs)
4. Note any discrepancies between expected and actual

#### 3c. Basic regression

Run a minimal regression — the simplest existing flows to make sure nothing is broken:

- Load a world, verify it appears
- Basic combat: attack an NPC, verify damage appears in log
- Basic interaction: if village world, talk to an NPC (rule-based only unless the phase touched LLM)

**LLM usage:** Avoid LLM-brain NPCs unless the phase specifically modified LLM behavior. If it did — test with LLM, burning some tokens is acceptable for E2E validation.

#### 3d. Quick fixes

If something is broken and fixable in <5 minutes — fix it immediately, then restart and retest that scenario. Note the fix in the report.

If something is seriously broken (>5 minutes to fix, unclear cause, design issue) — note it as a blocker and continue testing other scenarios. Don't spend E2E time debugging.

### 4. Check logs

After E2E, review the debug logs:

```bash
ls /tmp/dnd-e2e-logs/
# Read relevant log files for errors, warnings, unexpected behavior
```

Note anything suspicious — even if the UI looked fine, logs might reveal silent errors, unhandled exceptions, or performance issues.

### 5. Write the E2E report

Create `docs/sprints/NNN-slug/e2e/phaseN-report.md`:

```markdown
# Phase N E2E Report

**Date:** <today>
**Sprint:** NNN-slug
**Phase:** N — <Phase Name>

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| <what you did> | <what should happen> | <what happened> | pass/fail/partial |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world | pass | |
| Basic combat | pass | |
| NPC interaction | pass | |

## Quick Fixes Applied

- <description of fix, if any>

## Log Analysis

- <notable findings from debug logs>

## Blockers

- <serious issues that prevent phase closure, if any>

## Minor Issues

- <things that work but are suboptimal — candidates for backlog>
```

### 6. Close or block

#### If no blockers:

Update the task statuses (should already be `done` from `/implement`).

Update `sprint.md` — mark the phase as complete:

```markdown
## Phase N: <Name> ✓

<description>

**Tasks:**
...
```

Update `STATUS.md`:

```markdown
**Phase:** N — <Phase Name> (COMPLETE)
**Updated:** <date>

## Current

Phase N complete. <brief summary of results>.
<If there's a next phase:> Ready for Phase N+1 task generation.
<If this was the last phase:> All phases complete. Ready for sprint closure.
```

Commit:

```bash
git add docs/sprints/NNN-slug/ tests/integration/
git commit -m "sprint NNN phase N: close — <summary>"
```

Do NOT push.

#### If there are blockers:

Do NOT mark the phase as complete.

Update `STATUS.md`:

```markdown
## Current

Phase N: E2E found blockers. Phase NOT closed.

## Blockers

- <blocker 1>
- <blocker 2>
```

Tell the user what the blockers are and what you recommend (fix in a new task, rethink approach, etc.).

### 7. Cleanup

```bash
# Kill the debug stack
pkill -f uvicorn 2>/dev/null
pkill -f vite 2>/dev/null
```

### 8. Report

```
Phase N: <Name>
  Integration tests: <N> total, <M> new
  E2E scenarios: <N> tested, <M> passed, <K> failed
  Quick fixes: <N>
  Blockers: <N>
  Status: CLOSED | BLOCKED
```
