---
name: go
description: >
  Determine the next step in the sprint pipeline and execute it. Reads docs/STATUS.md, analyzes current
  state, and calls the appropriate skill. Use when user says "go", "next", "continue", "what's next",
  "продолжай", "дальше", or just wants to keep the pipeline moving without thinking about which
  skill to invoke.
allowed-tools: Bash, Read, Grep, Glob
---

# Go

Look at the current pipeline state and invoke the next skill. This is a dispatcher — it reads state, decides what's next, and tells the user which skill to run (or runs it directly if unambiguous).

## Protocol

### 1. Read state

Read `docs/STATUS.md` to find the current sprint and phase. Then read the sprint's `sprint.md` from `docs/sprints/NNN-slug/`. Also check:

- `docs/audit.md` — exists? date?
- `docs/e2e-reports/` — latest report? date? blockers?
- `docs/BACKLOG.md` — recent additions?

### 2. Determine state and next action

Work through this decision tree top-to-bottom. The FIRST match wins:

#### No current sprint in docs/STATUS.md or sprint marked COMPLETE
→ **`/new_sprint`** — time to plan the next sprint.

#### Sprint exists, current phase has no task files in `tasks/`
→ **`/plan_phase`** — phase needs task breakdown.

#### Phase has tasks with status `in_progress`
→ **`/implement`** — resume the in-progress task.

#### Phase has tasks with status `pending` (and none `in_progress`)
→ **`/implement`** — pick up the next pending task.

#### All tasks in current phase are `done`, phase NOT marked COMPLETE
→ **`/close_phase`** — phase is ready to close.

#### All phases marked COMPLETE, no `docs/audit.md` or audit date is BEFORE the last phase closure
→ **`/audit`** — need a fresh audit.

#### Fresh audit exists, docs/STATUS.md has NO "Audit Triage" note
→ **`/audit_triage`** — audit needs to be triaged.

#### Audit triaged, docs/STATUS.md shows sprint-relevant items went to a refactor phase, that phase has no tasks
→ **`/plan_phase`** — plan the refactor phase.

#### Audit triaged, refactor phase exists with pending/in-progress tasks
→ **`/implement`** or **`/close_phase`** — work through the refactor phase (same rules as any phase).

#### Audit triaged (marker in docs/STATUS.md), no E2E report dated AFTER the audit
→ **`/e2e`** — need post-audit E2E.

#### Post-audit E2E exists and is green
→ **`/close_sprint`** — everything should be ready.

#### Post-audit E2E exists but has blockers
→ Report blockers from the E2E report. User needs to fix them first.

### 3. Report

Print what you found and what's next:

```
Sprint NNN — <title>
State: <brief description of where we are>
Next: /skill_name — <why>
```

Then invoke the skill.

If the state is ambiguous (e.g. docs/STATUS.md is stale or contradictory) — describe what you see and ask the user instead of guessing.
