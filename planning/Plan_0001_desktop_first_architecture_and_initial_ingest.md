# Plan 0001: Desktop-First Architecture and Initial Ingest

## Goal

Establish CG's desktop-first/mobile-portable architecture and begin the first reproducible data acquisition pass for LDS scriptures and Strong's.

## Non-Goals

- Do not scaffold the Flutter app yet.
- Do not build the importer or SQLite schema in this plan.
- Do not commit raw scripture downloads, generated SQLite databases, or search indexes.
- Do not start NLVue work.

## Recon Facts

- `AGENTS.md` requires source/license manifests before import and keeps raw downloads gitignored.
- `ARCHITECTURE.md` defines Python-owned ingestion and SQLite/search as derived data boundaries.
- `data-ingest-discipline-cg-scriptures` requires deterministic raw acquisition, provenance, license records, and validation through the gauntlet.
- Ben Crowder's Scriptures in JSON page states the files are public domain and omit rights-restricted material.
- The mormon-documentation-project Strong's repo declares Unlicense and provides normalized JSON.

## Architecture Direction

- App: Flutter desktop first, with iOS/Android portability retained.
- Data pipeline: Python scripts download, verify, normalize, and build SQLite.
- Storage: raw downloads under `data/downloads/`, generated DB/indexes under ignored generated paths.
- App data: generated scripture DB separate from mutable user DB.
- Search: SQLite FTS first; NLVue later.

## Steps

1. Record source and license manifests for LDS scripture JSON and Strong's JSON.
2. Add a repeatable download script that reads committed manifests and writes only to ignored raw-download folders.
3. Download LDS scripture JSON and Strong's JSON.
4. Record a download receipt with file sizes and SHA-256 hashes under `.agent-work/receipts/`.
5. Run the CG gauntlet and confirm raw/generated data remains untracked.
6. Draft the next plan for schema/import/search once raw files are present.

## Success Criteria

- `data/manifests/sources.json` and `licenses.json` validate.
- `scripts/download-initial-sources.ps1` downloads all listed files.
- `.agent-work/receipts/initial-source-downloads.json` records hashes.
- `scripts/gauntlet.ps1` passes.
- `git status --short` shows no raw downloads or generated databases.

## Handoff

Read these files first in a fresh session:
- `AGENTS.md`
- `ARCHITECTURE.md`
- `planning/Plan_0001_desktop_first_architecture_and_initial_ingest_status.md`
- `data/manifests/sources.json`
- `data/manifests/licenses.json`
- `scripts/download-initial-sources.ps1`
