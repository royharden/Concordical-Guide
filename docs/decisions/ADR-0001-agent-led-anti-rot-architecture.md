# ADR-0001: Agent-Led Anti-Rot Architecture

Status: Accepted
Date: 2026-06-05

## Context

CG will likely be maintained largely by AI agents across multiple harnesses. The biggest long-term risks are split-brain instructions, provenance/licensing drift, importer mistakes, schema migration errors, search regressions, Strong's alignment drift, and mobile offline failures.

## Decision

Use `Concordical-Guide/` as the single repo root for all harnesses. Keep canonical skills in `C:\Users\Roy Harden\OneDrive\PJ-OD\skills` and mirror them into repo-root harness folders only. Use a small skill set plus mechanical validation through a shared gauntlet, hooks, and CI.

## Consequences

- Parent `CG/` remains a workspace wrapper with no live config.
- Skills stay concise and point to scripts/tests for enforcement.
- Data work starts from manifests and validation instead of raw imports.
- A stack-specific mobile fix discipline is deferred until the app stack is chosen.
