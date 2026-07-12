---
name: close-sprint
description: >
  Close the current sprint: verify all phases done, audit completed, post-audit E2E green, integration
  tests green, then update docs, commit, push, and wait for CI. Blocks if anything is off. Use when user says
  "close sprint", "finish sprint", "sprint done", "wrap up sprint", or when all phases are complete
  and it's time to finalize.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# Close Sprint

Finalize the current sprint. This is a gate — everything must be green or the sprint stays open.

## Protocol

### 1. Find the sprint

Read `docs/STATUS.md` to find the active sprint. Then read `sprint.md` from `docs/sprints/NNN-slug/`.

If no active sprint — stop.

### 2. Checklist

Verify each item. If ANY fails — collect all failures, report them, and **do not proceed**.

#### 2a. All phases complete

Every phase in `sprint.md` must be marked complete (✓). Check task files too — all must be `done`.

**Blocker if:** any phase or task is not done.

#### 2b. Audit exists and was triaged

`docs/audit.md` must exist with a date AFTER the last phase was closed. Check the audit date vs the last phase completion date in `docs/STATUS.md`.

**Blocker if:** no audit, or audit predates last phase closure.

#### 2c. Audit findings were handled

Sprint-relevant findings from the audit should have been addressed — either fixed in a refactor phase/task, or explicitly deferred to backlog with a note. Check that `docs/BACKLOG.md` has entries for deferred items if any were mentioned in `docs/STATUS.md` or sprint.md.

**Blocker if:** audit findings exist but there's no evidence they were triaged (no refactor phase, no backlog entries, no notes in sprint.md).

#### 2d. Post-audit E2E is green

There must be an E2E report in `docs/e2e-reports/` dated AFTER the audit. The report must have zero blockers.

**Blocker if:** no post-audit E2E report, or report has blockers.

#### 2e. Integration tests pass

```bash
make test-integration 2>&1 | tee /tmp/integration-test-output.txt
```

**ANY failure is a hard blocker — no exceptions.** This includes tests unrelated to the sprint, pre-existing failures, and flaky tests. A failing test means something is wrong, and we fix it before closing.

If tests fail:

1. **Read from file.** Analyze `/tmp/integration-test-output.txt` — never re-run just to see different output.
2. **Full investigation.** For each failing test: read the traceback, the test code, and the production code. Determine root cause.
3. **Fix on the spot.** Whether the failure is from our changes or pre-existing — fix it:
   - Flaky tests: find the race condition, make the test deterministic. "It passes sometimes" is not acceptable.
   - Pre-existing bugs: fix the bug or fix the test if the test is wrong.
   - Our regressions: fix the code.
4. **Re-run until all green.** Repeat until 0 failures.
5. **If a fix is non-trivial (>15 min) or unclear** — stop, report to the user with full diagnosis, and block the sprint.

**Blocker if:** any test fails and cannot be fixed.

### 3. If blocked

#### Quick fixes allowed

If a blocker is clearly a small bug fixable in <5 minutes (flaky test, trivial code fix, missing import), fix it inline, re-run the failing check, and continue. Note the fix in the commit message.

#### Serious blockers

If a blocker requires significant work (new phase, architecture change, multiple files):

```
Sprint NNN cannot be closed. Blockers:

1. <blocker description>
2. <blocker description>
...

Fix these and try again.
```

Do NOT commit or push when serious blockers remain.

### 4. If all green

#### 4a. Update docs

Run `/update-docs full` — full deep review, not incremental. A sprint accumulates changes across many phases; incremental mode would only see commits since the last mid-sprint run and miss earlier changes.

**CRITICAL: If `/update-docs` launches background subagents (for parallel research), you MUST wait for ALL of them to complete and review their findings BEFORE proceeding to step 4b.** Do not commit or push while subagents are still running — their results may reveal doc gaps that need fixing. After all agents return, review each agent's findings, apply any missed updates, and only then continue.

#### 4b. Fill in sprint results

Update `sprint.md` Results section:

```markdown
## Results

**Completed:** <date>

<Brief summary: what was built, key metrics (tests added, files changed), notable decisions or discoveries.>

**Deferred:** <list items that were punted to backlog, if any>
```

#### 4c. Update docs/STATUS.md

Move the completed sprint to the Sprint History table, refresh the header (`Last updated`, `Position`, `Next`, `Blockers`), and set the current sprint section to empty or the next sprint if one is planned:

```markdown
**Last updated:** <today>
**Position:** <where the project sits on the ROADMAP ladder after this sprint>
**Next:** <next sprint candidate, or "активного спринта нет" + top BACKLOG `must` items>
**Blockers:** <none, or list>

## Current Sprint

No active sprint.

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
| NNN-slug | <goal> | <started> | <today> |
| ... previous sprints ... |
```

Also leave an explicit closure marker while the remote gate is unresolved:

```markdown
**Closure:** Ждём завершения CI для `sprint/NNN-slug`.
```

This marker is pipeline state, not a prose note. It must be committed in the sprint PR. Do not replace it
with "closed", remove it, or start another sprint until the required CI checks and merge result are known.

#### 4d. Commit, push the branch, open the PR

The sprint ran on its own branch (`sprint/NNN-slug`, created by `/new-sprint`). Close it by opening a PR into `main` with auto-merge — CI is the gate, not a human.

```bash
git add docs/ CLAUDE.md ARCHITECTURE.md README.md src/dnd_simulator/**/__init__.py
git commit -m "sprint NNN: close — <goal summary>"

branch=$(git branch --show-current)   # sprint/NNN-slug
git push -u origin "$branch"
gh pr create --base main --head "$branch" \
  --title "sprint NNN: <goal summary>" \
  --body "<sprint summary + key metrics; note it was produced autonomously>"
gh pr merge "$branch" --auto --merge --delete-branch
```

`--auto` lands the PR on `main` automatically once the required CI checks pass — no human approval (branch protection requires the checks, not a reviewer). If CI fails, the PR stays open and `main` is untouched: that is the gate doing its job. After this, return to a clean base for the next sprint: `git checkout main` (the merge lands on remote `main` asynchronously; the next `/new-sprint` fast-forwards local main).

**Note:** Do NOT stage `.claude/skills/update-docs/state.json` here — it is committed by the `/update-docs` skill itself in step 4a.

This is the only skill that pushes. Opening the auto-merge PR is not the end of the step.

#### 4e. Monitor CI through merge

After enabling auto-merge, start a monitor and keep working until every required check reaches a terminal state.
Do not end the turn while checks are queued or in progress.

Use `gh pr checks <number> --watch --interval 10` in a background process with output redirected to
`/tmp/sprint-NNN-ci.log`, or an equivalent recurring monitor. Poll it at least once per minute and keep the
user informed. Also inspect `gh pr view <number> --json state,mergedAt,mergeStateStatus,statusCheckRollup,url`;
checks being green is insufficient if the PR did not merge.

- If every required check succeeds, wait until the PR state is `MERGED`, then report closure. Leave the
  `Closure` marker for the next `/go` reconciliation, which verifies the remote result independently and
  clears the marker on `main`.
- If any required check fails, is cancelled, or times out, stop the monitor and escalate to the operator with
  the PR URL, failed check names, and log URLs. Do not claim the sprint is closed, do not remove the marker,
  and do not start unrelated fixes without operator direction.
- If auto-merge is disabled or the PR remains open after all checks succeed, escalate that merge-state problem
  to the operator instead of finishing silently.

### 5. Report

```
Sprint NNN — <Title>: CLOSED
  Phases: N completed
  Tests: integration green, E2E green
  Docs: updated
  CI: all required checks green
  PR: merged to main
```
