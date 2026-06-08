---
name: ai-first-persistent-memory-and-planning-framework
description: Use for AI-first or agent-maintained projects when planning work, updating project memory, preventing AI code rot, creating or following immutable plans, recording lessons or decisions, coordinating multiple agents, managing context-window hygiene, or deciding what belongs in committed product docs versus gitignored agent work. Enforces a lean committed context, gitignored .agent-work for scratch, recon-before-edit, no second truths, scoped implementation, immutable plans with status companions, decision records, meaningful receipts, and fresh-session handoffs.
---

# AI-First Memory and Planning Framework

Keep long-running, agent-written codebases coherent. Stable project truth stays committed and lean; agent operations stay out of git unless promoted. Lighter than `documentation-framework-v1`.

## Repo root rule
The git repository root is the single root for all harnesses. Never read or write project config/skills from a parent wrapper folder. Treat the committed `AGENTS.md` at the repo root as the constitution.

## Storage policy
Committed product truth (kept lean):
- `AGENTS.md`, `CLAUDE.md`, Cursor rules, tool pointers.
- `ARCHITECTURE.md`, specs, public docs.
- `docs/decisions/` decision records (ADRs).
- `planning/` immutable plans + `_status` companions + manifest.
- Test contracts and golden fixtures that are part of the product quality gate.

Gitignored agent workspace (`.agent-work/`):
- `plans/` drafts before promotion · `reviews/` critiques · `memory/notes/` raw lessons · `memory/index/` generated SQLite/FTS/vector/graph · `receipts/` transcripts · `captures/` local DOM grabs.

Never commit generated indexes, SQLite, vector stores, or raw scratch unless asked. **Committed ≠ auto-loaded** — promote only stable, high-signal conclusions, and keep the always-on set tiny.

## Start of work
1. Read the repo-root `AGENTS.md` + imported `CLAUDE.md`/Cursor rule.
2. Read the manifest and the committed docs relevant to the task (especially `ARCHITECTURE.md` + the active spec).
3. Inspect `.agent-work/` only for the relevant active plan/handoff — do not bulk-load old scratch.
4. State scope in 1–2 sentences before non-trivial edits.

## Recon before edit
Before editing code, tests, fixtures, build config, docs, or skills:
- Identify the canonical implementation path.
- Check for duplicate or competing patterns.
- Cite the files/docs that establish the rule you follow.
- If the change would create a second source of truth, stop and consolidate.

## Context-window hygiene
Reliability falls as the context fills. Therefore:
- Load the lean read-first set, then read specific files on demand — don't pre-load history.
- Work in small scoped steps; summarize progress into the `_status` file instead of carrying everything in-context.
- When the thread is long or the window is large, write a handoff and start a fresh session rather than pushing on.
- Prefer decomposition into short, verifiable steps over one long run.

## Planning
Use a plan when work spans multiple files, has unclear architecture, or affects future agents.
- Draft in `.agent-work/plans/`; promote to an immutable `planning/Plan_*.md` once it is a contract.
- **Immutable:** never edit a promoted plan. All progress, drift, and receipts go in its `_status.md` companion.
- Plan shape: goal + non-goals, recon facts, small steps with success criteria, verification commands, and a handoff list (the minimum files a fresh agent must read).

## Decisions (ADRs)
Record durable choices future agents should not relitigate (tooling, architectural boundaries, lowering a floor, changing an invariant) as a numbered ADR in `docs/decisions/` using the template. Keep them short (Y-statement).

## Lessons and memory
Record a lesson only when it changes future behavior (a bug → regression test, a command/env/path gotcha, a repeated design mistake, a provider-UI capture behavior). Raw notes → `.agent-work/memory/notes/`; promote concise, stable rules into `LESSONS.md` when mature.

## Implementation discipline
- One logical change at a time; prefer existing patterns over new abstractions.
- Delete/consolidate obsolete paths when replacing behavior.
- After meaningful work, run a cleanup pass (duplicate logic, dead selectors, stale fixtures, weak types).
- Every bug fix adds a regression test or explains why impossible.

## Receipts & handoff
For meaningful work (not every command): files changed, checks run, known gaps, decisions, and a fresh-session handoff. A receipt can be a `_status` entry, `.agent-work/receipts/*.md`, or a final summary.

Use with the project prime, testing discipline, fix discipline, and `sync-skills-across-agents`.
