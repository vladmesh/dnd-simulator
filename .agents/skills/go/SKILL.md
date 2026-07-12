---
name: go
description: Advance the dnd-simulator sprint pipeline by reading repository state, selecting the next project playbook, and executing exactly one pipeline step. Use when the user invokes /go or $go, or says go, next, continue, дальше, продолжай, or asks Codex to keep the current dnd-simulator sprint moving.
---

# Go

Execute one next pipeline step in `dnd-simulator`. Keep the project-owned Claude skill files as the source of truth; do not copy their procedures into this Codex skill.

## Locate the project

Require a checkout whose repository contains all of:

- `AGENTS.md`
- `docs/STATUS.md`
- `.claude/skills/go/SKILL.md`

Start from the current working directory and use `git rev-parse --show-toplevel`. If it is not `dnd-simulator`, stop and report the wrong project instead of searching outside this repository.

## Execute

1. Read the repository `AGENTS.md` completely and obey it.
2. Search shared memory as required by `AGENTS.md` before acting on prior state.
3. Read `.claude/skills/go/SKILL.md` completely.
4. Read `docs/STATUS.md`, the active sprint's `sprint.md`, and the other state files required by the repository `go` checklist.
5. Apply the repository `go` decision tree. The first matching state wins.
6. Read the selected `.claude/skills/<step>/SKILL.md` completely, including any other checklist it explicitly invokes.
7. Execute that selected checklist in the current turn. Do not merely recommend a slash command.
8. Execute exactly one pipeline granule: one CI-closure reconciliation, one planning step, one implementation task, one phase closure, one audit/triage, one E2E run, or one sprint closure. Stop after its own commit/report boundary.

## Codex adaptations

- Treat Claude frontmatter such as `allowed-tools`, `argument-hint`, and trigger phrases as metadata, not runtime restrictions.
- When a checklist says to invoke another skill, open that skill's `SKILL.md` and continue with it.
- Use `apply_patch` for file edits and preserve unrelated worktree changes.
- Pipe test output to the file required by project instructions and read that file instead of rerunning tests.
- Use detached processes for dev servers and kill them when finished.
- When the repository checklist says CI must be monitored, keep the turn alive until terminal check and merge
  state. A queued or running check is not a valid report boundary.
- Do not force-push, rewrite pushed history, merge `main`, or add AI attribution.
- If repository instructions and a project checklist disagree, follow `AGENTS.md`, then the user's current request. In particular, use merge commits rather than squash when the repository says so.

If state is contradictory, report the concrete contradiction and stop. Otherwise act autonomously through the selected granule.
