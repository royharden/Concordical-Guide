# Plan 0001 Status

Plan: `planning/Plan_0001_desktop_first_architecture_and_initial_ingest.md`

## Status

Complete.

## Completed

- Accepted desktop-first/mobile-portable Flutter architecture direction in `docs/decisions/ADR-0002-desktop-first-mobile-portable-flutter.md`.
- Updated `ARCHITECTURE.md` with runtime and data-pipeline boundaries.
- Added LDS scripture JSON and Strong's JSON source/license manifests.
- Ran `scripts/download-initial-sources.ps1` from the `Concordical-Guide/` repo root on 2026-06-07.
- Downloaded all 9 manifest URLs into ignored raw-data directories:
  - `data/downloads/lds-scriptures-json/`
  - `data/downloads/strongs/`
- Wrote `.agent-work/receipts/initial-source-downloads.json` with byte counts and SHA-256 hashes.
- Confirmed `git status --short --ignored data/downloads data/generated .agent-work` reports raw downloads and receipts as ignored, with no generated SQLite database present.
- Ran `scripts/gauntlet.ps1`; it passed, warning only that no SQLite schema existed yet at that point.

## Current Task

Plan 0001 is complete. Next work can begin on the schema/import/search milestone.

## Receipts

- Download receipt: `.agent-work/receipts/initial-source-downloads.json`.
- Download receipt timestamp: `2026-06-07T21:15:09Z`.
- Downloaded bytes:
  - `bcbooks-scriptures-json`: 14,262,301 bytes across 6 files.
  - `mormon-documentation-project-strongs`: 3,904,442 bytes across 3 files.

## Notes

- The first direct script invocation was blocked by local PowerShell execution policy, so the script was run with process-local `ExecutionPolicy Bypass`.
- `scripts/download-initial-sources.ps1` was adjusted for Windows PowerShell compatibility by removing unsupported `ConvertFrom-Json -Depth`; receipt generation still uses `ConvertTo-Json -Depth`.

## Open Items

- Confirm the LDS scripture public-domain/bundling policy before shipping app data.
- Create Flutter/Dart fix discipline before app scaffolding.
- Draft or promote schema/import/search planning only if Roy wants a formal Plan 0002 artifact.
