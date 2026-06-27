---
name: meta-go
description: >
  Fully autonomous sprint orchestrator — an experimental hands-free development format with NO human in
  the loop. Runs the full sprint pipeline by spawning one fresh agent per pipeline step; each agent does
  exactly one granule (/plan-phase, /implement one task, /close-phase, /audit, etc.) and exits. The
  orchestrator is the SOLE decision authority: it makes every call itself, answers any clarifying
  questions its sub-agents raise, and ends the run only on success or an unrecoverable dead-end — never to
  ask a human. Optionally bounded: `/meta-go N` runs at most N granules then stops with a resume report.
  Use when the user says "meta-go", "run the sprint", "autopilot", "автопилот",
  "прогони спринт", or wants to leave and come back to a finished sprint.
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: "[N]"
---

# Meta-Go — Sprint Orchestrator

Run the sprint pipeline end-to-end by spawning one Agent per step. The critical rule: **one agent = one granule**. Never let an agent do two steps. Agents accumulate context and degrade — fresh agents stay sharp.

## Autonomy contract

This is an experiment in fully autonomous development. There is **no human in the loop** for the duration of the run. You — the orchestrator — are the sole decision authority for the whole project:

- **You make every decision yourself.** Scope, design, naming, trade-offs, whether to proceed, whether to refactor. Default to the choice best aligned with `docs/VISION.md` and the layer-stack design in `CLAUDE.md`. When genuinely uncertain, take the most reversible option and proceed — do not halt.
- **You answer your sub-agents.** If a spawned agent surfaces a clarifying question or a decision it could not make alone, *you* answer it: read its report, decide, and thread the answer into the next spawn (or a short dedicated follow-up agent). Never defer a sub-agent's question to a human.
- **You don't stop to ask.** "Stop and report to user" / "wait for user" steps in the per-step skills (e.g. `/audit-triage`) are addressed to the interactive `/go` path. Under meta-go you ARE the user — apply the decision and continue.
- **You end the run** only on sprint completion (closed and pushed), the granule budget running out, or an unrecoverable dead-end (see Termination). Log your decisions as you go so a human can review the run afterward.

## Run length — the `N` argument

`/meta-go N` runs **at most N granules**, then stops and reports. `/meta-go` with no argument runs until the sprint is closed or a dead-end.

- **A granule is one `/go` call**, and `/go` may pick any step (`/plan-phase`, `/implement` one task, `/close-phase`, `/audit`, `/audit-triage`, `/e2e`, `/close-sprint`). N counts ALL of them, not just implement-tasks. So `/meta-go 5` might be five implements, or three implements + one close-phase + one audit. Calibrate N knowing a step can be heavy (a `/close-phase` runs the full E2E).
- **Each granule costs 1 from the budget, retries included.** A targeted auto-recover micro-fix that doesn't go through `/go` (e.g. a lone lint fix) doesn't count, but the 3-failure rail still bounds it.
- **`/close-sprint` is allowed within the budget.** If it lands inside N, the run closes the sprint and pushes to `main` — flag this loudly in the final report.
- **Never start a new sprint.** If the next granule would be `/new-sprint` (sprint complete / none active), STOP and report even if budget remains. A bounded run finishes authorized work, it doesn't open new scope.

## What is a "granule"

One granule = one invocation of /go. By the /go decision tree, that means exactly one of:

- `/plan-phase` — generate tasks for one phase
- `/implement` — implement ONE task (not two, not "the rest")
- `/close-phase` — validate and close one phase
- `/audit` — scan the codebase
- `/audit-triage` — triage findings
- `/e2e` — post-audit E2E run
- `/close-sprint` — final gate + push

Each of these is a single agent spawn. No combining.

## Protocol

### 1. Read initial state

Read `docs/STATUS.md` to understand where we are. This tells you how many steps remain and what the next one is.

### 2. The loop

If invoked as `/meta-go N`, set a granule budget of N; with no argument the budget is unbounded. Before each spawn, check the budget — if it's 0, stop (see Termination). Decrement it after each granule.

Spawn an Agent with this exact prompt structure:

```
You are working on the dnd-simulator project. Your working directory is the repository root (run `git rev-parse --show-toplevel` if you need the absolute path).

This is a FULLY AUTONOMOUS run — there is NO human available. The orchestrator that spawned you is the sole decision authority. Never wait for a human, never ask a human, never defer a decision to a human.

Read CLAUDE.md for project rules. Read docs/STATUS.md for current sprint state.

Then invoke the /go skill to determine and execute the next pipeline step.

CRITICAL CONSTRAINTS:
- Execute /go EXACTLY ONCE. It will determine the next step and run it.
- After that single step completes, STOP. Report what you did and what the result was.
- Do NOT look at what the "next step after this" would be. Do NOT continue the pipeline.
- Do NOT invoke /go a second time. Do NOT invoke any other skill after /go finishes.
- Your job is ONE granule. Report and exit.

DECISIONS & QUESTIONS (no human to ask):
- Make routine decisions yourself (code splitting, naming, patterns): choose the option best aligned with VISION.md and the layer-stack design in CLAUDE.md.
- If the step's skill says "wait for user" (e.g. /audit-triage), do NOT wait — apply the decision: bucket-1 quick-fixes applied; sprint-relevant items <5min fixed now, >5min → a refactor phase; bucket-3 → docs/BACKLOG.md; then mark the triage complete in docs/STATUS.md.
- If you face a decision you genuinely should not make alone (architecture-level fork, ambiguous scope): do NOT ask and do NOT block. Take the most reversible option, proceed, and in your report state the question, the option you took, and why — so the orchestrator can course-correct on the next granule.
- If /implement flags an architecture problem as "stop and report": do NOT start a large refactor (that breaks the one-granule rule). Finish/stop the current granule and report the problem — file/function, the risk, AND your recommended fix. The orchestrator decides the next granule from your report.

Prefer architecturally clean solutions aligned with VISION.md and CLAUDE.md.
```

After each agent completes, read its result. Then:

### 3. Evaluate the result

Check the agent's report for:

#### Continue (spawn next agent):
- Task implemented successfully, tests green → next
- Phase planned, tasks generated → next
- Phase closed, no blockers → next
- Audit complete → next
- Audit triaged, all items handled → next
- E2E green → next

#### Decide and continue (you are the authority — no human to escalate to):
- **Architecture blocker** — a sub-agent says the foundation is bad. Decide the path yourself: if a refactor phase fixes it, make the next granule plan that phase (`/plan-phase` for a refactor phase) and continue; if it's a local fix, spawn one fix granule; if it's a deep design fork, take the most reversible option, record the decision, and proceed. Log what you chose and why.
- **E2E blockers** — spawn a fix granule (or, for >5min/structural issues, a refactor phase) and continue. Don't stop.
- **`/close-sprint` failed** — read what the gate says is missing, run the granule that supplies it (e.g. `/audit`, `/e2e`, a fix), then re-attempt `/close-sprint`.
- **Sprint complete** — `/close-sprint` succeeded, code is pushed. End the run with a final summary.

#### Auto-recover:
- **`make check` lint/format failure** the agent didn't fix → spawn one quick-fix granule. If it fails again, treat it as a failed step (see Termination).
- **Agent confusion** (output makes no sense / went off track) → re-ground from `docs/STATUS.md` and git, then spawn a fresh agent with a clearer, narrower prompt. Repeated confusion on the same step counts toward the failure limit.

### 4. Progress tracking

After each agent, print a brief status line:

```
[N] /skill-name — result (tests: NNNN, duration: Xm) — budget: K left
Sprint NNN phase P: <where we are>
```

This is the run log a human can scan afterward (the run itself does not wait for anyone).

### 5. Termination

The loop ends when (first to hit):
- **Granule budget exhausted** — `/meta-go N` ran its N granules. Clean stop.
- **Sprint boundary** — the next granule would be `/new-sprint` (sprint just closed, or none active). Stop even with budget remaining; a bounded run finishes authorized work, it doesn't open new scope. (A successful `/close-sprint` ends the run here too.)
- **Unrecoverable dead-end** — the same step fails 3 consecutive times despite remediation, or a gate can't be satisfied after you've run the granules that should satisfy it. Runaway/cost safety rail, not a human escalation.

On any stop, print a final summary: granules run (and budget left, if bounded), what's done vs still pending in the plan, the next step to resume with, whether anything was pushed to `main`, and the autonomous decisions you made. Record the final state for later review.

There is no "wait for human" exit. If you find yourself wanting to stop and ask, decide instead and continue.

## What NOT to do

- **Don't read agent transcripts in detail.** Read the summary result. If it says "done, tests green" — trust it and move on. Don't waste context re-verifying.
- **Don't accumulate implementation details.** You're an orchestrator. You track state transitions, not code changes.
- **Don't retry the same failing step endlessly.** One retry with a clearer prompt is ok; if it still fails, try an alternate remediation (refactor phase, narrower task). Persistent failure on the same step (3 in a row) is the dead-end stop from Termination — not a prompt to a human.
- **Don't spawn agents in parallel.** The pipeline is sequential — each step depends on the previous one.
- **Don't let docs/STATUS.md get stale in your head.** Re-read it every 3-4 iterations to stay grounded, since agents update it.
