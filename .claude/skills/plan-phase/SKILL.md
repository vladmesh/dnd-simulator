---
name: plan-phase
description: >
  Generate tasks for the current sprint phase. Reads docs/STATUS.md, reviews code, breaks the phase into
  testable tasks with TDD approach (tests first, then implementation). Use when user says "plan phase",
  "generate tasks", "break down phase", "what are the tasks", "task generation", or when a new phase
  is ready to start after the previous one was completed. Also trigger when user asks "what's next"
  and there's an active sprint with an unplanned phase.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Plan Phase

Generate tasks for the current phase of the active sprint. Read the code, understand what needs to change, break it into testable increments, and discuss with the user.

## What this skill does NOT do

- Implement tasks (that happens after planning)
- Close tasks or update their status
- Run tests or audits
- Plan the next sprint or pick scope

## Protocol

### 1. Find the active sprint

Read `docs/STATUS.md` to determine which sprint is active and which phase is current.

**If there's no active sprint or all phases are marked COMPLETE** — tell the user there's nothing to plan and stop. Don't sugarcoat it.

Then read the sprint's `sprint.md` (from the path in `docs/sprints/NNN-slug/`) to understand the phase description — what it should deliver and why.

### 2. Review the code

This is the most important step. You need to understand the current state of the codebase to break the phase into sensible tasks.

Based on the phase description, identify:

- Which files/modules will be affected
- What already exists that you can build on
- What's missing that needs to be created
- What dependencies exist between pieces of work

Use the Explore agent or direct Grep/Glob/Read for this. Be thorough — bad code review leads to bad task breakdown.

### 3. Check for architectural issues

While reviewing, actively look for problems that could block or complicate the phase:

- **DRY violations** — copy-paste patterns that will get worse with new code
- **Hardcoded values** — game data in Python that belongs in YAML
- **Mixed responsibilities** — functions/classes doing too many things
- **Giant functions** — methods over ~200 lines that will grow further
- **Wrong abstraction level** — code in the wrong layer (rules with I/O, adapters with business logic)

If you find something that needs a refactor before the phase can proceed cleanly:

**Stop and report.** Don't try to work around it. Don't plan tasks that build on a shaky foundation. Tell the user:

- What the problem is
- Why it matters for this phase
- How big the fix is (quick fix vs. separate task vs. phase restructure)

The goal is a good product, not completed tasks. A delayed phase with clean code beats a "done" phase with technical debt. Don't be afraid to say "this needs fixing first."

### 4. Break into tasks

Each task should be:

- **Testable** — there's a clear way to verify it works (unit test, integration test, or manual check)
- **Stable** — after this task, the codebase should ideally still pass existing tests. Stubs and no-op implementations are fine. This is a preference, not a hard rule — sometimes you need to break things temporarily.
- **Scoped** — small enough to implement and review in one sitting

Aim for 2-4 tasks per phase. If you're getting more, the phase might be too big — discuss with the user.

### 5. TDD structure

Every task follows TDD: tests first, then implementation. The task file should reflect this.

**Important: write product-level tests, not implementation tests.** The tests should describe game behavior, not code structure.

Good tests (product logic, long chains):
- "A +1 dagger hits AC 15 on a roll of 14 with +2 DEX mod (14+2+1=17 ≥ 15) and deals 1d4+2+1 damage"
- "Buying a health potion for 50gp deducts 50gp from player inventory and adds the potion"
- "Weather changes every in-game hour according to the region's climate table"
- "A poisoned creature has disadvantage on attack rolls — roll twice, take the lower"

Bad tests (implementation details, trivial):
- "ActionType enum contains TRADE value"
- "WeatherModel has a temperature field"
- "parse_item() returns an Item instance"
- "inventory list starts empty"

The test should exercise as much of the real logic chain as possible. Mock external boundaries (I/O, LLM, random), but let the internal layers work together. 

### 6. Ask clarifying questions

If anything is unclear about the phase scope, implementation approach, or priorities — ask before writing task files. Better to discuss upfront than to rewrite tasks later.

Common things worth asking:
- "The phase says X, but the code already has Y — should we extend or replace?"
- "This touches module Z which is already messy — refactor first or work around?"
- "I see two ways to do this: A (simpler, less flexible) or B (more work, cleaner). Preference?"

### 7. Write task files

Create task files in `docs/sprints/NNN-slug/tasks/`:

```markdown
# Task: <Title>

**Date:** <today>
**Sprint:** NNN-slug
**Phase:** <N> — <Phase Name>

## Description

<What needs to happen, in concrete terms. Not a vague goal — specific changes.>

## Tests First

<What tests to write before implementation. Describe the scenarios, not the test function names. These should be product-level: describe game behavior that the code must satisfy.>

## Implementation

<After tests are red — what to build to make them green. Key files, approach, gotchas.>

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] <Domain-specific criteria>

## Status

`pending`
```

Task naming convention: `phaseN-taskM-slug.md` (e.g. `phase2-task1-inventory-model.md`).

### 8. Update sprint docs

Add task links to the phase section in `sprint.md`:

```markdown
## Phase N: <Name>

<existing description>

**Tasks:**

1. [Task Title](tasks/phaseN-task1-slug.md)
2. [Task Title](tasks/phaseN-task2-slug.md)
```

Update `docs/STATUS.md` — set the current phase and note task generation:

```markdown
**Phase:** N — <Phase Name> (tasks generated) — <date>

Ready to start task 1.
```

### 9. Commit

```bash
git add docs/sprints/NNN-slug/ docs/STATUS.md
git commit -m "sprint NNN phase N: task breakdown"
```

Do NOT push.

### 10. Report

Print the task list:

```
Phase N: <Name>
Tasks:
  1. <title> — <one-liner>
  2. <title> — <one-liner>
  ...
Ready to start task 1.
```
