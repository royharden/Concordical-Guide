# ADR-0002: Desktop-First Mobile-Portable Flutter App

Status: Accepted
Date: 2026-06-07

## Context

Roy wants CG to be a desktop app first, but built in a way that can move to iOS and Android. The app needs offline scripture/search behavior and should not make early choices that force a rewrite when mobile arrives.

## Decision

Use Flutter as the app target: Windows desktop first, with iOS and Android as planned targets. Keep ingestion out of the app runtime. A Python data pipeline will build a versioned SQLite asset from source manifests and raw downloads. The app will use Dart domain services and repository interfaces over SQLite so desktop and mobile share the same domain model.

## Consequences

- The first UI can ship on desktop without abandoning mobile portability.
- SQLite/search behavior becomes a shared data contract rather than desktop-only logic.
- User data should live in a separate mutable local database from generated scripture/source data.
- A Flutter/Dart fix discipline should be created before app scaffolding or CI expansion.
- NLVue remains deferred until text, Strong's, search, and offline data contracts are stable.
