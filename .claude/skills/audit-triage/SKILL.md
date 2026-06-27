---
name: audit-triage
description: >
  Analyze audit findings in context of the current sprint. Triages into three buckets: quick-fixes
  (do now), sprint-relevant (refactor fuel), and backlog (defer). Does NOT auto-fix or update files —
  presents findings and waits for user decision. Use when user says "triage", "audit triage",
  "review audit", "what should we fix", "prioritize findings", or after /audit completes and
  the user wants to decide what to act on. Also useful between phases to decide if a refactor phase is needed.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Audit Triage

Analyze `docs/audit.md` findings and triage them into actionable buckets. Read-only — no files modified, no commits, just analysis and recommendations in chat.

## Protocol

### 1. Read the audit

Read `docs/audit.md`. If it doesn't exist or is empty — tell the user to run `/audit` first and stop.

### 2. Determine context

Check if there's an active sprint: read `docs/STATUS.md` and the sprint's `sprint.md` from `docs/sprints/NNN-slug/`.

**If active sprint exists:**
- Note the sprint goal, current phase, and which code areas the sprint touches
- This context determines what's "sprint-relevant" vs "backlog"

**If no active sprint:**
- Triage is general: "sprint-relevant" bucket becomes "high-impact" — things that affect the most code or the most critical paths

### 3. Analyze each finding

For every finding in the audit, assess:

- **How long to fix?** (<5 min = quick-fix candidate, 5-30 min = medium, >30 min = large)
- **Risk of fixing?** (isolated change = safe, touches many files = risky, changes interfaces = very risky)
- **Does it affect current sprint work?** (same module, same layer, same feature area)
- **How much worse does it get if we ignore it?** (grows with new code = urgent, static = can wait)

### 4. Triage into three buckets

#### Bucket 1: Quick-fix (do now)

Criteria — ALL of these must be true:
- Fixable in <5 minutes
- Safe — isolated change, no interface changes, no cascading effects
- Clearly correct — no ambiguity about what the fix should be

Examples: unused import, missing type annotation, obvious dead code, trivial lint fix, off-by-one in a comment.

NOT quick-fix: anything that requires a design decision, touches tests, or changes behavior.

#### Bucket 2: Sprint-relevant (refactor fuel)

Criteria — at least one:
- Directly in code we're modifying this sprint (same files, same module)
- Will get worse because of sprint work (we're adding code to an already-bloated function)
- Blocks clean implementation of a sprint task (e.g. hardcoded data we need to extend)

These are candidates for a dedicated refactor task within the current sprint. They don't get fixed silently — they get discussed and planned.

#### Bucket 3: Backlog (defer)

Everything else. Not simple enough for a quick-fix, not relevant enough for the current sprint. Goes to `docs/BACKLOG.md` if the user agrees.

### 5. Present to user

Print the triage in chat. Format:

```
## Quick-fix (N items)

These can be fixed right now, <5 min each, zero risk:

1. **<file:line>** — <issue>. Fix: <what to do>
2. ...

## Sprint-relevant (N items)

These affect code we're working on in Sprint NNN:

1. **<file:line>** — <issue>. Impact: <why it matters for the sprint>. Effort: <estimate>
2. ...

Recommendation: <create a refactor task / fold into existing task / handle between phases>

## Backlog (N items)

Not urgent, not blocking. Candidates for BACKLOG.md:

1. **<file:line>** — <issue>. Category: <tech-debt/security/convention>
2. ...
```

### 6. Wait for user

Do NOT:
- Apply any fixes
- Create tasks
- Update backlog
- Modify any files
- Write any markers or status updates

Just present the triage and wait. The user decides:
- "Fix quick-fixes" → apply bucket 1
- "Add to backlog" → append bucket 3 to BACKLOG.md (skip items already tracked there; mark a finding already fixed in code as done rather than re-adding it)
- "Create refactor task" → create a task file for bucket 2 items
- Or any combination / custom decision

### 7. Mark triage complete (ONLY after all items are handled)

This step happens ONLY when the user has given the go-ahead AND every finding has been dispatched somewhere:
- Quick-fixes applied
- Sprint-relevant items either in a refactor phase or explicitly deferred
- Backlog items added to BACKLOG.md or explicitly dismissed

Only then — append audit triage note to `docs/STATUS.md`:

```markdown
**Audit:** Triaged <date>. Quick-fix: N applied. Sprint-relevant: N (→ refactor phase / deferred). Backlog: N added.
```

Then commit the marker (and any backlog/task files changed during triage):

```bash
git add docs/STATUS.md docs/BACKLOG.md docs/sprints/NNN-slug/
git commit -m "sprint NNN: audit triaged"
```

Do NOT push.

Do NOT write this marker at the start of the triage or after just presenting the report. It signals to `/go` and `/close-sprint` that the audit cycle is complete.
