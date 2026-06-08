---
name: testing-discipline-cg-scripture-app
description: Use before writing, changing, refactoring, reviewing, or deleting CG app behavior, scripture navigation, search, Strong's or morphology alignment, SQLite migrations, offline/local-cache behavior, data fixtures, validation floors, or test configuration. Enforces a layered test pyramid for importer correctness, schema/search behavior, mobile offline workflows, and bug-to-regression coverage.
---

# Testing Discipline - CG Scripture App

Test the product contracts that would otherwise fail quietly: data correctness, search semantics, schema migration, Strong's alignment, and mobile offline behavior.

## Test layers
- L1 pure functions: reference normalization, parser transforms, search tokenization, Strong's mapping helpers.
- L2 data integration: tiny fixture import into SQLite, migrations, FTS/search queries, integrity checks.
- L3 app services/state: verse lookup, reading plans, bookmarks/notes if present, cache invalidation, offline read/search.
- L4 mobile/UI: cold start, navigation, font scaling, offline mode, migration on app upgrade, no-network search.
- L5 data audit smoke: manifest-to-import reproducibility and sample cross-checks against source provenance.

## If you touch X
- Source/import logic: add or update a tiny fixture and run data validation.
- SQLite schema/migration: prove a new in-memory schema loads and, when applicable, old fixture data migrates forward.
- Search: include exact reference, phrase, punctuation, case/diacritic, and Strong's-linked cases.
- Strong's/morphology: assert token-to-identifier alignment and document unmapped tokens.
- Offline/cache behavior: test no-network startup, local data availability, and cache invalidation.
- A bug: add a regression with `what_bug_this_catches`, or explain why a mechanical test is impossible.

## Floors
Once the app stack and test runner exist, track minimum coverage, fixture counts, and data-validation gates in a committed floor file. Lowering a floor requires an ADR and a status/receipt note.

## Minimum contract
- Tests must exercise import/search independently from the UI.
- Golden data fixtures are behavioral contracts, not decorative samples.
- Do not change tests to match broken data or unreviewed license assumptions.
- Run the narrow failing command first, then `scripts/gauntlet.ps1`.

## Cross-skill
Use `prime-cg-scripture-study-app` for orientation, `data-ingest-discipline-cg-scriptures` for manifest/import obligations, `ai-first-persistent-memory-and-planning-framework` for plans and receipts, and `sync-skills-across-agents` if skills or instructions change.
