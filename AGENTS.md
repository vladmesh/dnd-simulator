# AGENTS.md

Guidance for non-Claude coding agents (Codex, etc.) working in this repo. Claude Code reads CLAUDE.md instead; this file points to the same sources of truth — do not duplicate content here.

## Conventions (details in CLAUDE.md)

- Pipe test output to a file and read the file: `make check 2>&1 | tee /tmp/check.log`. Never rerun a suite just to re-read its output.
- Halves: `make check-backend` / `make check-frontend`; the pre-push hook scope-filters via `scripts/classify-scope.sh` (docs-only pushes run nothing).
- Never add `Co-Authored-By` or any AI attribution to commit messages or PR bodies.
- User-visible strings go through gettext `_()`; default locale is RU.
- Dev servers: uvicorn on :8001, vite on :5173. Start detached (`setsid <cmd> > /tmp/x.log 2>&1 &`), kill them when done. Browser E2E runs are serialized on these ports — if you work under a coordinator, ask before running E2E.
- `main` is protected: changes land via PR (merge commits, not squash). Do not merge your own PR unless told to.
- Product vision: [docs/VISION.md](docs/VISION.md) · what is planned: [docs/ROADMAP.md](docs/ROADMAP.md) · code map: [ARCHITECTURE.md](ARCHITECTURE.md).

## Where state and backlog live (not in this repo)

Since 2026-09-21 this repository holds no state file and no backlog file.

- **Current state and what hurts** — the secretary board:
  `issue list --product dnd-simulator`, `sprint list --status open`,
  `task list --project dnd-simulator`. Bugs, tech debt, test gaps and feature candidates are issues
  of the `dnd-simulator` product.
- **History, design and decisions** — knowledge of the secretary instance,
  `state/knowledge/projects/dnd-simulator/` (`README.md` is the entry point; `brainstorms/` — live
  design documents including `simulation-core.md`; `archive/` — implemented and cancelled documents
  plus snapshots of the former `BACKLOG.md`/`STATUS.md`/audit; `decisions/`; `sprints/`;
  `e2e-reports/`).
- **Do not create** `BACKLOG.md`, `STATUS.md`, `audit.md` or any similar state/backlog file in this
  repository, and do not restore the deleted ones. A card that seems to require it is a card that
  needs to be sent back, not obeyed. Findings and leftovers go into the worker report; the PO turns
  them into issues.

## Process

Sprints run on the secretary board, not in this repo — see [docs/SPRINT_PIPELINE.md](docs/SPRINT_PIPELINE.md).

## Domain skills (executable checklists)

Treat each `SKILL.md` as a step-by-step checklist: follow the body, ignore Claude-specific frontmatter (`allowed-tools`, trigger phrases).

| Request | Checklist |
|---|---|
| run E2E | `.claude/skills/e2e/SKILL.md` + [docs/e2e-playbook.md](docs/e2e-playbook.md) |
| audit the codebase | `.claude/skills/audit/SKILL.md` (reports findings; writes no files in this repo) |
| sync documentation | `.claude/skills/update-docs/SKILL.md` |

## Claude-specific → generic equivalents

- "run in background" (Claude Bash tool feature) → `setsid <cmd> > /tmp/x.log 2>&1 &`.
- A skill invoking another skill → open that skill's `SKILL.md` and continue with it.
- `AskUserQuestion` / user prompts → if you run under an Orca coordinator, use `orca orchestration ask` and poll for the reply; otherwise stop and report.
