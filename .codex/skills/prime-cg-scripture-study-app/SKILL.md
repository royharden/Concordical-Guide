---
name: prime-cg-scripture-study-app
description: Use at the start of any session that will plan, build, test, review, or modify the CG Concordical Guide scripture study app or its data pipeline. Establishes the Concordical-Guide repo root as the single harness root, the lean read-first list, the committed-docs versus gitignored .agent-work policy, scripture data provenance/licensing/import/search/offline invariants, and which CG anti-rot skills to load next.
---

# Prime - CG Scripture Study App

Run once at the start of a substantive CG session.

## Repo root
`Concordical-Guide/` is the root for all harnesses. The parent `CG/` folder is a workspace wrapper with no live config or skill folders.

## Read first
Keep this lean:
1. `AGENTS.md`.
2. `ARCHITECTURE.md`.
3. `planning/cg-manifest.md`.
4. The active plan's `_status.md` in `planning/`, if one exists.
5. The top of `LESSONS.md`.

Read on demand only: full plans, `docs/decisions/`, data manifests, validation scripts, and `.agent-work/`.

## Product invariants
- Every scripture, lexicon, morphology, Strong's, cross-reference, or commentary source must have a manifest entry with provenance and license status before import.
- Importers must be deterministic and replayable from manifests into SQLite/search indexes.
- SQLite schema changes and migrations are versioned, validated, and covered by tiny fixtures.
- Search correctness, reference normalization, and Strong's alignment need explicit fixtures.
- Mobile/offline behavior must cover cold start, local cache, schema migration, and no-network search once the app stack exists.

## Skill chain
1. `ai-first-persistent-memory-and-planning-framework` for recon, planning, memory, receipts, and handoffs.
2. `data-ingest-discipline-cg-scriptures` before source, manifest, importer, SQLite, Strong's, morphology, or search-index work.
3. `testing-discipline-cg-scripture-app` before app behavior, tests, fixtures, migrations, search, offline, or UI workflow changes.
4. A stack-specific fix discipline such as `mobile-app-fix-discipline-cg` once the mobile stack is chosen.
5. `sync-skills-across-agents` whenever skills or instruction files change.

## Session rules
- Recon before edits; cite the files or manifests that establish the rule.
- Keep source-of-truth boundaries crisp: manifests describe provenance, importers transform, SQLite/search stores derived artifacts.
- Do not commit raw downloads, generated databases, caches, or large data exports.
- Run `scripts/gauntlet.ps1` before declaring done; never bypass hooks with `--no-verify`.
- Report files changed, checks run, known gaps, and human decisions still needed.
