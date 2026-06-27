---
name: meta-go
description: >
  Autonomous sprint orchestrator. Runs the full sprint pipeline hands-free by spawning one fresh agent
  per pipeline step. Each agent does exactly one granule (/plan-phase, /implement one task, /close-phase,
  /audit, etc.) and exits. Meta-go monitors results, decides if the next step is safe to run autonomously,
  and stops only when a human decision is genuinely needed. Use when the user says "meta-go", "run the sprint",
  "autopilot", "автопилот", "прогони спринт", or wants to leave and come back to a finished sprint.
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# Meta-Go — Sprint Orchestrator

Run the sprint pipeline end-to-end by spawning one Agent per step. The critical rule: **one agent = one granule**. Never let an agent do two steps. Agents accumulate context and degrade — fresh agents stay sharp.

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

Spawn an Agent with this exact prompt structure:

```
You are working on the dnd-simulator project. Your working directory is the repository root (run `git rev-parse --show-toplevel` if you need the absolute path).

Read CLAUDE.md for project rules. Read docs/STATUS.md for current sprint state.

Then invoke the /go skill to determine and execute the next pipeline step.

CRITICAL CONSTRAINTS:
- Execute /go EXACTLY ONCE. It will determine the next step and run it.
- After that single step completes, STOP. Report what you did and what the result was.
- Do NOT look at what the "next step after this" would be. Do NOT continue the pipeline.
- Do NOT invoke /go a second time. Do NOT invoke any other skill after /go finishes.
- Your job is ONE granule. Report and exit.

If /go determines the next step is /audit-triage:
- Apply all quick-fixes (bucket 1) without asking.
- For sprint-relevant items (bucket 2): create a refactor phase if there are items with effort >5min.
  Items <5min — fix immediately alongside the quick-fixes.
- Add all backlog items (bucket 3) to docs/BACKLOG.md.
- Then mark the triage complete in docs/STATUS.md.
- Prefer architecturally clean solutions. When in doubt, consult docs/VISION.md.

If you encounter an architecture problem that /implement flags as "stop and report":
- Do NOT attempt to fix it yourself.
- Report clearly: what the problem is, what file/function, and why proceeding is risky.

For all other decisions (how to split code, naming, patterns): choose the more architecturally
clean option. Prefer options aligned with VISION.md and the layer stack design in CLAUDE.md.
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

#### Stop and report to user:
- **Architecture blocker** — agent says foundation is bad and proceeding would add tech debt. Report exactly what the agent said. The user needs to decide.
- **E2E blockers** — serious bugs that need >5min to fix. Report the blocker list.
- **close_sprint failed** — gate check failed. Report what's missing.
- **Agent confusion** — output doesn't make sense, agent seems to have gone off track. Don't retry blindly — report what happened.
- **Sprint complete** — /close-sprint succeeded, code is pushed. Report the final summary.

#### Auto-recover (limited):
- If `make check` failed on a lint/format issue and the agent didn't fix it — spawn a quick fix agent. But only once. If it fails again, stop and report.

### 4. Progress tracking

After each agent, print a brief status line:

```
[N] /skill-name — result (tests: NNNN, duration: Xm)
Sprint NNN phase P: <where we are>
```

This gives the user a scannable log when they return.

### 5. Termination

The loop ends when:
- Sprint is closed and pushed (success)
- A blocker requires human judgment (report and wait)
- Three consecutive agent failures on the same step (something is fundamentally wrong)

## What NOT to do

- **Don't read agent transcripts in detail.** Read the summary result. If it says "done, tests green" — trust it and move on. Don't waste context re-verifying.
- **Don't accumulate implementation details.** You're an orchestrator. You track state transitions, not code changes.
- **Don't retry the same failing step more than once.** If an agent fails, one retry with a clearer prompt is ok. Second failure = stop and report.
- **Don't spawn agents in parallel.** The pipeline is sequential — each step depends on the previous one.
- **Don't let docs/STATUS.md get stale in your head.** Re-read it every 3-4 iterations to stay grounded, since agents update it.
