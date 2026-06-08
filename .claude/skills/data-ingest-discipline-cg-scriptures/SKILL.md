---
name: data-ingest-discipline-cg-scriptures
description: Use before adding, modifying, reviewing, or deleting CG scripture source manifests, license/provenance records, raw downloads, importers, SQLite schema/import code, search indexes, Strong's alignment, morphology data, cross-references, or data validation scripts. Enforces manifest-first ingestion, license checks, deterministic imports, small fixtures, no large committed data, and validation through the CG gauntlet.
---

# Data Ingest Discipline - CG Scriptures

Protect the project from the rot risks that come from mutable source data, licensing drift, and silent importer mistakes.

## Applies to
Scripture texts, lexicons, morphology, Strong's numbers, cross-references, commentaries, source manifests, license manifests, raw downloads, import transforms, SQLite schema/migrations, FTS/search indexes, and generated data artifacts.

## Intake contract
- Add or update `data/manifests/sources.json` before importing a source.
- Every source needs: stable id, title, kind, language, provenance URL, retrieval date, license id, storage policy, and notes for known caveats.
- Add or update `data/manifests/licenses.json` for the referenced license.
- Treat unknown, restricted, or pending-review license status as a blocker for user-facing bundled content until Roy decides.

## Import contract
- Imports are deterministic: same manifest + same source bytes produces the same SQLite/search output.
- Raw downloads and generated databases stay out of git unless explicitly approved.
- Normalize references in one canonical path; do not create competing book/chapter/verse parsers.
- Strong's and morphology alignment must preserve source identifiers and explain unmapped tokens.
- Schema changes require migration validation and a small fixture proving old data can move forward.

## Tests and fixtures
- Use tiny public-domain or synthetic fixtures for importer tests.
- A data bug becomes a regression fixture with `what_bug_this_catches`.
- Search fixtures should cover reference lookup, phrase search, diacritics/case, punctuation, and Strong's-linked queries.
- Fixture text must be license-safe; do not paste restricted translation chunks as a convenience.

## Mechanical checks
Run `scripts/gauntlet.ps1` after meaningful ingest work. At minimum it validates:
- source manifest shape and unique ids;
- license/provenance manifest shape and links;
- SQLite schema SQL and optional imported database integrity;
- no tracked `.agent-work`, raw downloads, generated databases, or oversized data files.

## Do not
- Import first and document provenance later.
- Check in raw corpora, generated SQLite files, FTS indexes, or cache directories.
- Lower validation floors or bypass a license concern without an ADR in `docs/decisions/`.
