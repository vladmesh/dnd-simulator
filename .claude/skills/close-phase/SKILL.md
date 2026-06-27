---
name: close-phase
description: >
  Close the current sprint phase: run integration tests (add new ones if needed), run E2E via the /e2e
  skill, and mark the phase complete if no blockers. Use when user says
  "close phase", "finish phase", "phase done", "e2e", "run e2e", "test the phase", "verify phase",
  or when all tasks in a phase are marked done and it's time to validate before moving on.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Close Phase

Validate and close the current sprint phase. Integration tests → E2E (via the `/e2e` skill) → close (or block).

## What this skill does NOT do

- Implement tasks (use `/implement`)
- Plan the next phase (use `/plan-phase`)
- Close the sprint (use `/close-sprint`)

## Protocol

### 1. Find the current phase

Read `docs/STATUS.md` to find the active sprint and current phase. Then read the sprint's `sprint.md` from `docs/sprints/NNN-slug/`.

**If no active sprint or current phase** — stop, nothing to close.

**If any tasks in the phase are still `pending` or `in_progress`** — stop, tell the user which tasks aren't done yet.

### 2. Integration tests

Run the existing integration tests:

```bash
make test-integration 2>&1 | tee /tmp/integration-test-output.txt
```

**ANY failure is a hard blocker — no exceptions.** This includes tests unrelated to the current phase, pre-existing failures, and flaky tests. A failing test means something is wrong, and we fix it before moving on.

#### If tests fail:

1. **Redirect output to file, read from file.** Never re-run just to see different output — read `/tmp/integration-test-output.txt`.
2. **Full investigation.** For each failing test:
   - Read the full traceback and understand what the test expects vs what happened.
   - Read the test code and the production code it exercises.
   - Determine root cause: is it a real bug, a race condition, a timing issue, a test that needs updating?
3. **Fix on the spot.** Whether the failure is from our changes or pre-existing — fix it. This includes:
   - Flaky tests: find the race condition and make the test deterministic (increase timeouts, add retries with backoff, fix the underlying race). "It passes sometimes" is not acceptable.
   - Pre-existing bugs: fix the bug or fix the test if the test is wrong.
   - Our regressions: fix the code.
4. **Re-run until all green.** After fixes, re-run the full suite. Repeat until 0 failures.
5. **If a fix is non-trivial (>15 min) or unclear** — stop, report to the user with full diagnosis, and block the phase. Do NOT skip the test or mark it as known-flaky.

Then review what the phase added and determine if new integration tests are needed. If the phase introduced:

- New API endpoints → add REST tests
- Changed WebSocket protocol → add/update WS tests
- New game mechanics visible through API → add tests that exercise them

Write and add the new integration tests. Run again until green:

```bash
make test-integration
```

### 3. E2E via `/e2e`

E2E is a single procedure owned by the `/e2e` skill: Playwright availability check, debug stack launch, playbook + auto-discovered scenarios, log review, and report. Do NOT duplicate it here.

Invoke it scoped to this phase, writing the report to the per-phase path:

```
/e2e --context sprintNNN-phaseN --report docs/sprints/NNN-slug/e2e/phaseN-report.md
```

- Test the phase's new functionality first, then a basic regression. Use `--section N[,N...]` to target the playbook sections the phase touched.
- Pass `--with-llm` only if the phase changed LLM behavior.
- **If `/e2e` reports Playwright MCP is unavailable, it blocks.** Do NOT close the phase without E2E. Tell the user to restart the session (`/exit` then re-launch) and re-run `/close-phase`.

When `/e2e` finishes, read the report it wrote at `docs/sprints/NNN-slug/e2e/phaseN-report.md` and use its blockers to decide close vs block below.

### 4. Close or block

#### If no blockers:

Update the task statuses (should already be `done` from `/implement`).

Update `sprint.md` — mark the phase as complete:

```markdown
## Phase N: <Name> ✓

<description>

**Tasks:**
...
```

Update `docs/STATUS.md`:

```markdown
**Phase:** N — <Phase Name> (COMPLETE) — <date>

<If there's a next phase:> Ready for Phase N+1 task generation.
<If this was the last phase:> All phases complete. Ready for audit.
```

Commit:

```bash
git add docs/sprints/NNN-slug/ docs/STATUS.md tests/integration/
# also stage any src/ or frontend/ files you fixed during integration/E2E debugging (steps 2-3)
git commit -m "sprint NNN phase N: close — <summary>"
```

Do NOT push.

#### If there are blockers:

Do NOT mark the phase as complete.

Update `docs/STATUS.md`:

```markdown
**Phase:** N — <Phase Name> (BLOCKED) — <date>

Blockers:
- <blocker 1>
- <blocker 2>
```

Tell the user what the blockers are and what you recommend (fix in a new task, rethink approach, etc.).

### 5. Cleanup

```bash
# Kill the debug stack
pkill -f uvicorn 2>/dev/null
pkill -f vite 2>/dev/null
```

### 6. Report

```
Phase N: <Name>
  Integration tests: <N> total, <M> new
  E2E scenarios: <N> tested, <M> passed, <K> failed
  Quick fixes: <N>
  Blockers: <N>
  Status: CLOSED | BLOCKED
```
