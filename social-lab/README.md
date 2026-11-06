# CG social lab

A standalone local-only demonstration. People and text are fictional; there are no accounts, network sync or real scripture text. Browser storage can be read by anyone using the same browser profile. Export contains private drafts.

Prerequisites: Node.js and Python. Install the lab's own pinned TypeScript dependency (no global installation). From repository root:

```powershell
npm --prefix social-lab ci
npm --prefix social-lab run build
python -m http.server 23802 --bind 127.0.0.1 --directory social-lab
```

Open http://127.0.0.1:23802/ . Stop with Ctrl+C. Before starting, run the agent-ports `check CG/social-lab` preflight; this machine reserves 23802 for this lab. `npm --prefix social-lab test` runs the domain checks. The sample catalog is deliberately incomplete; unknown references are rejected. `planning/social-plan.md` documents the contract and production gaps.

Preflight command (run in a context able to query Docker):

```powershell
python "<path-to-agent-ports>/scripts/ports.py" check CG/social-lab
```

Proceed only when it reports OK. A restricted-context UNKNOWN requires a host-capable check; it does not establish that Docker is stopped.

## Portable local backups

Export creates a versioned `cg-social-lab` JSON envelope containing saved demo posts (including private drafts), follows and blocks. It does not include an unsaved editor buffer; export is blocked until that work is saved or cancelled. Files are unencrypted and must be treated as private. Import validates the entire file before offering a preview, supports legacy version-1 raw saves, and rejects unknown versions, invalid references, duplicate post IDs and oversized files. Merge adds missing post IDs, keeps local content for identical or conflicting IDs and unions follow/block lists; replacement is separately confirmed and discards local records absent from the backup. States remain as saved: importing never publishes a draft. The preview is rejected if saved local data changed since it was prepared. A comparison with current storage detects ordinary other-tab changes but is not an atomic multi-tab transaction; use one tab for editing. Corrupt or unsupported existing local data is not silently replaced; a recovery screen offers a raw download and an explicit reset.

Manual browser QA for the new backup/recovery interface is pending. It is not encrypted backup, production identity, permission enforcement or sync.
