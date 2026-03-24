---
name: new-sprint
description: >
  Plan a new sprint: choose scope from backlog/roadmap, break into vertical phases, create sprint docs.
  Use when user says "new sprint", "next sprint", "plan sprint", "start sprint", "sprint planning",
  or after a sprint is completed and it's time to pick up the next chunk of work. Also trigger when
  user asks "what should we work on next" or "what's the priority now" in the context of this project.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# New Sprint

Plan a new sprint through a structured dialogue with the user. This skill covers scope selection and phase breakdown only — no task planning, no implementation details.

## What this skill does NOT do

- Generate tasks (that's a separate step after this skill finishes)
- Discuss implementation details (how code should look, what functions to write)
- Start any coding work
- Run tests or audits

## Protocol

### 1. Gather context

Read these files to understand the current state of the project:

```
docs/VISION.md          — product vision and architectural direction
docs/ROADMAP.md         — what's done, what's planned, dependency graph
docs/BACKLOG.md         — prioritized work items with tags
CLAUDE.md               — architecture, key design principles
```

Then find the previous sprint. Look at `docs/sprints/` for the highest-numbered folder. Read its `sprint.md` to understand what was just completed and what was deferred. Deferred items from the previous sprint are strong candidates for the next one.

### 2. Determine sprint number and create scaffold

The next sprint number is the previous sprint's number + 1, zero-padded to 3 digits. The sprint name (slug) will be filled in after scope is decided.

Create `docs/sprints/NNN-TBD/sprint.md` with only:

```markdown
# Sprint NNN

**Started:** <today's date>
```

Update `docs/sprints/NNN-TBD/STATUS.md`:

```markdown
# Sprint NNN Status

**Sprint:** NNN
**Phase:** Planning
**Updated:** <today's date>

## Current

Scope selection in progress.
```

Do NOT commit yet — the folder will be renamed once the scope is decided.

### 3. Propose scope options

Based on what you read, propose 3-5 scope options to the user. Each option should include:

- **What:** 1-2 sentence description of what gets built
- **Why now:** what this unblocks or why it's the right time (dependency argument)
- **Risk:** what could go wrong or take longer than expected
- **Size estimate:** small (1-2 phases) / medium (2-3 phases) / large (3-4+ phases)

Prioritize options by dependency logic: things that unblock the most future work should rank higher. Don't just echo the backlog — synthesize. A sprint can combine related items (e.g. "inventory + trading" or "spell slots + first spells").

Also consider whether it's time for a tech sprint. Signals: backlog has accumulated >5 "should" tech debt items, last tech sprint was >4 sprints ago, audit findings are piling up.

Be opinionated. If one option is clearly better than the others, say so and explain why. Challenge the user if they pick something that has unmet dependencies or is premature.

### 4. Dialogue

The user picks a direction (or proposes their own). Discuss until you both agree on:

- **Sprint goal** — one sentence describing the end state
- **Scope boundary** — what's explicitly in and out

Once agreed, rename the sprint folder to `NNN-slug` (derive slug from the goal, kebab-case, 2-3 words). Write the goal and context into `sprint.md`:

```markdown
# Sprint NNN — <Title>

**Goal:** <one sentence>

**Started:** <date>

## Context

<Why this sprint, what it unblocks, references to relevant docs>

**Ссылки:** [relevant-doc](path), ...
```

### 5. Phase breakdown

Now break the scope into phases. Rules for phases:

- A phase is a **vertical slice**: it touches all necessary layers (core, rules, service, adapters, frontend) so the result is testable end-to-end.
- A phase is NOT a horizontal layer ("phase 1 = backend, phase 2 = frontend"). That leads to integration hell.
- Each phase should be independently testable — either via `make test-integration` or manual E2E.
- 2-4 tasks per phase (this is a rough guide for sizing, not a hard rule).
- Earlier phases build foundation that later phases extend.
- It's OK if a phase doesn't produce a user-visible feature — but it must produce something verifiable.

Present the proposed phases to the user. For each phase, describe:

- **What it delivers** (testable outcome, not implementation steps)
- **Why this ordering** (what does this phase enable for the next one)

Discuss and adjust until the user agrees.

### 6. Finalize

Write the agreed phases into `sprint.md`:

```markdown
## Phase 1: <Name>

<1-2 sentences: what this phase delivers and how to verify it>

**Tasks:**

_(генерируются отдельно перед началом фазы)_

## Phase 2: <Name>

...

---

## Status

**Current:** Planning complete. Ready to generate Phase 1 tasks.

## Decisions

_(заполняется по ходу спринта)_

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
```

Update `STATUS.md`:

```markdown
# Sprint NNN Status

**Sprint:** NNN-slug
**Phase:** Planning (COMPLETE)
**Updated:** <date>

## Current

Sprint planned. <N> phases. Ready for Phase 1 task generation.

## Next Steps

Phase 1 task generation.
```

### 7. Commit

```bash
git add docs/sprints/NNN-slug/
git commit -m "sprint NNN: plan — <goal summary>"
```

Do NOT push.

### 8. Report

Print a brief summary:

```
Sprint NNN — <Title>
Goal: <goal>
Phases: <N>
  1. <phase name> — <one-liner>
  2. ...
Next: generate Phase 1 tasks
```
