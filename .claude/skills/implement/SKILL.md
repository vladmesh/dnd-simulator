---
name: implement
description: >
  Implement the next pending task in the current sprint phase. Follows TDD: write tests first (RED),
  then implement (GREEN), verify all tests pass, update docs, commit. Use when user says "implement",
  "next task", "work on task", "start task", "do the task", or when the user wants to pick up
  the next piece of work in an active sprint. Also trigger when user says "implement task N"
  to target a specific task.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Implement Task

Find and implement the next pending task in the current sprint phase. Follow TDD strictly. Stop and report if architecture is compromised.

## Protocol

### 1. Find the current task

Read `docs/STATUS.md` to find the active sprint and current phase.

**If there's no active sprint, or no current phase, or the phase has no task files** — tell the user there's nothing to implement and stop.

Read the sprint's `sprint.md` from `docs/sprints/NNN-slug/` and the phase's task files from `tasks/`. Find the first task with `status: pending`. That's what we're implementing.

**If all tasks are done** — tell the user the phase is complete and stop. Don't start the next phase — that requires `/plan-phase`.

### 2. Update status

Mark the task as in-progress:

In the task file, change:
```
`pending` → `in_progress`
```

Update `docs/STATUS.md` to reflect what we're working on:
```markdown
**Phase:** N — <Phase Name> (task M in progress) — <date>
```

### 3. Read the task and review relevant code

Read the full task file. Understand:

- What tests to write (from "Tests First" section)
- What to implement (from "Implementation" section)
- Acceptance criteria

Then read the code areas that will be affected. Understand the current state before changing anything.

### 4. Architectural check

Before writing any code, verify the foundation is solid. Look for:

- **DRY violations** in the area you're about to modify — will your changes make copy-paste worse?
- **Hardcoded game data** in Python that should be YAML — will you add more hardcoding on top?
- **Mixed responsibilities** — is the function/class you're extending already doing too much?
- **Giant functions** — will your changes push a 150-line method to 250?

If you find a problem that your task would make worse:

**Stop.** Report to the user:
- What the problem is
- Why proceeding would make it worse
- Proposed fix (quick refactor, separate task, or phase restructure)

Don't implement on a bad foundation just to close the task. A stopped task with a clear report is better than a "done" task that introduced technical debt.

### 5. TDD — RED phase

Write the tests described in the task's "Tests First" section.

**Product-level tests.** Test game behavior, not code structure. Long chains through real logic, mocking only external boundaries (I/O, LLM, random/dice).

Run the tests. They should be RED (failing). If they pass before implementation — either the feature already exists (re-evaluate the task) or the tests are too weak (rewrite them).

```bash
uv run pytest <test_file> -v
```

If the task's tests live under `tests/integration/`, they need the docker stack to run — `uv run pytest` against them won't work without a live backend. Write them now, but their RED/GREEN verification happens in step 7b via docker, not here.

### 6. TDD — GREEN phase

Implement the minimum code to make the tests pass. Follow the task's "Implementation" section as a guide, but use judgment — the task plan may not account for everything you discovered during code review.

Principles during implementation:
- **Minimum viable change.** Don't gold-plate. Don't add features the task didn't ask for.
- **Respect existing patterns.** Match the style and structure of surrounding code.
- **No hardcoded game data in Python.** If you need new game data — it goes in YAML under `content/` or in frozen dataclass definitions in `core/`.
- **Rules stay pure.** No I/O, no state, no side effects in `rules/`.
- **Layers depend down.** Don't import from layers above or from service/adapters in core/rules/layers.

### 7. Verification

Run the full test suite:

```bash
make check
```

This runs the full local gate: backend (lint + typecheck + tests) and frontend (eslint + typecheck + vitest) — the same checks CI runs, minus integration. Everything must pass. (Integration is not in `make check` — if this task touched it, see step 7b.)

#### If new tests fail

Debug and fix. This is normal TDD iteration.

#### If OLD tests fail

**Do not blindly fix old tests to make them pass.** Old tests existed for a reason. Analyze:

1. **What contract changed?** Identify the exact interface or behavior that shifted.
2. **Was the contract change intentional?** Does the task require this change, or did we accidentally break something?
3. **If intentional** — update the old tests to reflect the new contract. Document what changed and why in the task's developer notes.
4. **If accidental** — fix the implementation, not the tests. The old tests are telling you something is wrong.
5. **If unclear** — ask the user. "These 3 tests in test_combat.py fail because we changed the Attack dataclass. The task requires this change because X. Should I update them or rethink the approach?"

### 7b. Run integration tests if this task added or changed any

`make check` does NOT run integration tests — they need the docker stack. If this task added or modified anything under `tests/integration/`, run them **now**. Do not defer to `/close-phase`: a broken integration test committed here stays invisible (it never runs in `make check`) until close-phase, several tasks later, where it's far more expensive to diagnose.

Check whether integration tests changed:

```bash
git status --short tests/integration/
```

If nothing under `tests/integration/` is new or modified, skip this step — `/close-phase` runs the full integration suite anyway.

If anything changed, run the suite via docker — the clean, in-order environment CI uses, not a hand-started local backend. Always log to a file (per CLAUDE.md, never run it bare):

```bash
make test-integration 2>&1 | tee /tmp/integration.log
```

Read the log to inspect results. The **whole** suite must be green, not just your new test:

- Integration shares a process-global RNG and a single backend across all tests. A new test can break a *later* one through roll-ordering or a leaked session. If your test passes alone but the suite fails, that coupling is the bug — fix it, don't commit red.
- Treat any failure here exactly like a failing unit test: debug to root cause and fix before commit. Same rules as step 7 (don't blindly edit old tests; if a contract changed intentionally, update them and note why; if unclear, ask).

### 8. Update docs and commit

Update the task file:

```markdown
## Status

`done`

## Developer Notes

<What actually happened. Key decisions, surprises, problems encountered.
If old tests were modified — explain why. If you deviated from the plan — explain why.
Keep it brief but informative for future context recovery.>
```

Update `docs/STATUS.md` — note the completed task:

```markdown
**Phase:** N — <Phase Name> (task M done, M+1 pending) — <date>
```

Commit:

```bash
git add <changed files> docs/STATUS.md
git commit -m "sprint NNN phase N task M: <what was done>"
```

Stage specific files — don't `git add -A`. Do NOT push.

### 9. Report

```
Task M: <title> — done
  Tests: N new, M modified, K total passing
  Files changed: <list>
  Notes: <anything notable>
Next: Task M+1 — <title>
```
