# CG Architecture

CG is a desktop-first scripture study app designed so the product code can move to iOS and Android without rewriting the domain model or data pipeline.

The app target is Flutter: Windows desktop first, then iOS and Android from the same UI/application layer. The data pipeline is Python-owned and produces a versioned SQLite asset for offline use. NLVue is deferred until the scripture text, Strong's data, search, and local storage contracts are stable.

The central rot risks are data provenance, license drift, importer correctness, schema migration safety, search semantics, Strong's alignment, and mobile offline behavior.

## Runtime Architecture

- App shell: Flutter desktop first, with mobile layout constraints kept in the component design from the start.
- Domain core: pure Dart services for references, navigation, search requests, study state, and Strong's lookups.
- Data access: repository interfaces over SQLite, with no UI code reading source JSON directly.
- Local data: a generated SQLite database bundled as an app asset, then copied/migrated into app storage on first run.
- Search: SQLite FTS for initial offline search; richer semantic/NLVue work is a later layer.
- User data: notes, bookmarks, reading progress, and preferences live in a separate mutable local database so source updates do not endanger user data.

## Data Pipeline Architecture

- Manifests in `data/manifests/` declare all source, license, and download provenance before import.
- Raw downloads live under gitignored `data/downloads/`.
- Importers normalize source files into canonical records and build a generated SQLite database.
- Schema and migration SQL live under `schema/sqlite/`.
- Tiny license-safe fixtures validate reference parsing, scripture import, Strong's import, search behavior, and migrations.
- Generated databases, search indexes, and caches are rebuildable artifacts and are not committed.

## Layered Model

Layer 1 - Orientation:
- `prime-cg-scripture-study-app` establishes the repo root, lean read-first list, and CG-specific invariants.

Layer 2 - Memory and planning:
- `ai-first-persistent-memory-and-planning-framework` governs recon-before-edit, committed versus gitignored memory, immutable plans, ADRs, lessons, receipts, and handoffs.

Layer 3 - Build/data/test disciplines:
- `data-ingest-discipline-cg-scriptures` protects source, license, import, SQLite, search, Strong's, and morphology work.
- `testing-discipline-cg-scripture-app` protects importer, schema, search, app-service, UI, and mobile offline behavior.
- A Flutter/Dart fix discipline should be added before app scaffolding or CI expansion.

Layer 4 - Mechanical enforcement:
- `scripts/gauntlet.ps1` runs manifest, license/provenance, SQLite, and tracked-data checks now.
- The same gauntlet is wired for hooks and CI.
- App lint/type/test checks are discovered from `package.json` once the stack exists.

## Invariants

- `Concordical-Guide/` is the only live harness root.
- Canonical skills live in `C:\Users\Roy Harden\OneDrive\PJ-OD\skills`; repo skill folders are mirrors.
- Source manifests and license manifests precede imports.
- Raw downloads, generated databases, search indexes, caches, and `.agent-work/` stay out of git.
- SQLite schema/import validation is mechanical.
- Search and Strong's behavior are fixture-backed.
- Desktop behavior must not assume desktop-only storage or navigation patterns when mobile equivalents are known.
- Mobile offline behavior must be tested once the app exists.

## Data Boundaries

Manifests describe provenance and license status. Importers transform source bytes into normalized records. SQLite and search indexes are derived outputs. UI and mobile services consume derived data; they do not become alternate data authorities.

## Memory Boundaries

Committed memory is lean durable truth: architecture, decisions, manifest, plans/status, lessons, tiny fixtures, and validation scripts. `.agent-work/` is for draft plans, raw notes, reviews, generated indexes, receipts, and local downloads.
