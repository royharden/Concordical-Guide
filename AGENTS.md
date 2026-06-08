# AGENTS.md - Concordical Guide

The single, tool-neutral source of truth for every agent and harness in this repository. Tool-specific files point here; skill folders in this repo are mirrors of the canonical PJ-OD skills.

**Version:** 1.0.0 - 2026-06-05. Changelog at the bottom.

---

## 0. Repo Root Rule

This repository, `Concordical-Guide/`, is the root for all harnesses. Run agents with this directory as the working root. The parent `CG/` folder is a workspace wrapper only and must not contain live instruction or skill folders.

## 1. Project

CG is a scripture study app with an expected mobile/offline surface and a data pipeline for scripture texts, lexicons, morphology, Strong's alignment, cross-references, search indexes, and SQLite-backed local data.

The main rot risks are not DOM drift; they are scripture data provenance, licensing drift, importer correctness, schema migrations, search correctness, Strong's alignment, and mobile offline behavior.

## 2. Read First

Keep always-loaded context small:
1. `AGENTS.md`.
2. `ARCHITECTURE.md`.
3. `planning/cg-manifest.md`.
4. The active plan's `_status.md` in `planning/`, if one exists.
5. The top of `LESSONS.md`.

Read full plans, decision records, manifests, validation scripts, and `.agent-work/` only when the current task needs them.

## 3. Active Skills

Canonical source: `C:\Users\Roy Harden\OneDrive\PJ-OD\skills\<name>\SKILL.md`.
WSL path: `/mnt/c/Users/Roy Harden/OneDrive/PJ-OD/skills/<name>/SKILL.md`.

Repo folders (`.agents/skills`, `.claude/skills`, `.codex/skills`, `.cursor/skills-cursor`, `.grok/skills`) are mirrors. Never edit a mirror first.

| Skill | Use when |
|---|---|
| `prime-cg-scripture-study-app` | Start of any substantive CG session. |
| `ai-first-persistent-memory-and-planning-framework` | Planning, recon, memory, decisions, receipts, handoffs, `.agent-work`. |
| `data-ingest-discipline-cg-scriptures` | Before source manifests, licenses, importers, SQLite, search indexes, Strong's, morphology, or generated data changes. |
| `testing-discipline-cg-scripture-app` | Before app behavior, tests, fixtures, migrations, search, Strong's alignment, or offline workflow changes. |
| `sync-skills-across-agents` | Whenever a skill or instruction file is created, edited, renamed, removed, or mirrored. |

Recommended later: create `mobile-app-fix-discipline-cg` after Roy chooses the app stack.

## 4. Storage Policy

Committed durable truth:
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`.
- `ARCHITECTURE.md`, `LESSONS.md`, `docs/decisions/`.
- `planning/` immutable plans, `_status.md` companions, and manifest.
- `data/manifests/`, schema files, tiny license-safe fixtures, validation scripts, CI.

Gitignored scratch/rebuildable work:
- `.agent-work/` draft plans, reviews, raw notes, receipts, generated indexes, local caches.
- raw downloads, generated SQLite databases, generated search indexes, large data exports.

Committed does not mean auto-loaded. Promote only stable project truth and read it on demand.

## 5. Work Rules

- Recon before edit: find the canonical path and cite it.
- No second truths: manifests describe provenance, importers transform, SQLite/search stores derived artifacts.
- Data bug to regression: add a tiny fixture with `what_bug_this_catches`.
- License uncertainty blocks bundled/user-facing data until Roy decides.
- Run `scripts/gauntlet.ps1` before declaring meaningful work done.
- Never use `--no-verify`.
- Report changed files, checks run, known gaps, and human decisions still needed.

## 6. Enforcement

`scripts/gauntlet.ps1` is the shared local/CI hook. It currently runs CG validation for source manifests, license/provenance manifests, SQLite schema/import integrity, and tracked large/generated data. Once an app stack exists, it also runs `lint`, `typecheck`, and `test` scripts from `package.json` when present.

Install hooks once with `scripts/setup-hooks.ps1`. GitHub Actions runs the same gauntlet.

## 7. Cross-Harness Discovery

| Harness | Instructions | Skills |
|---|---|---|
| Claude Code | `CLAUDE.md` imports `AGENTS.md` | `.claude/skills/` |
| Codex | `AGENTS.md` | `.codex/skills/` |
| Cursor | `.cursor/rules/cg-skills.mdc` points to `AGENTS.md` | `.cursor/skills-cursor/` |
| Grok CLI | repo-root `AGENTS.md` scan | `.grok/skills/`, then `.agents/skills/` |

## Changelog

- **1.0.0 (2026-06-05):** Initial repo-rooted anti-rot constitution for CG. See `docs/decisions/ADR-0001-agent-led-anti-rot-architecture.md`.
