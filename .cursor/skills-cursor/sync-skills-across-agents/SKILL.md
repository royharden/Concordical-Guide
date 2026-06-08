---
name: sync-skills-across-agents
description: Keep project and global skills visible across Claude Code, Codex, Cursor, and Grok CLI. Use whenever an agent creates, copies, renames, updates, removes, or recommends a skill; edits global or project AGENTS.md, CLAUDE.md, CURSOR.md, .cursor/rules, .claude/skills, .codex/skills, .cursor/skills-cursor, .grok/skills, or .agents skill mirrors; or needs to verify a skill is discoverable from all agent tools. Enforces the canonical PJ-OD skills directory, repo-root-only project mirrors, instruction-file updates, collision handling, and verification including a no-duplicate-outside-repo-root check.
---

# Sync Skills Across Agents

Keep skill content and references aligned across Claude Code, Codex, Cursor, and Grok CLI. The canonical `PJ-OD\skills` folder is the source of truth; mirror or reference it where each tool reads.

## Canonical source
```text
C:\Users\Roy Harden\OneDrive\PJ-OD\skills
/mnt/c/Users/Roy Harden/OneDrive/PJ-OD/skills
```
Never edit a mirror first. Update the canonical skill, then sync outward.

## Project mirrors live at the repo root ONLY
For a project, the git repo root is the single root for all harnesses. Mirror skills only into the repo root's folders:
- `.agents/skills/<name>/SKILL.md` (tool-neutral source mirror)
- `.claude/skills/<name>/SKILL.md`
- `.codex/skills/<name>/SKILL.md`
- `.cursor/skills-cursor/<name>/SKILL.md`
- `.grok/skills/<name>/SKILL.md`

Do NOT place skill folders in a parent wrapper directory above the repo root — that causes split-brain discovery depending on the working directory.

## Project workflow
1. Update the canonical `SKILL.md`.
2. Copy it into the five repo-root mirror folders above.
3. Update repo-root instruction files: `AGENTS.md` (list the skill, its when-to-use, and canonical path; bump the AGENTS version + changelog), `CLAUDE.md` (imports `AGENTS.md`), `.cursor/rules/*.mdc` (pointer). Grok scans `AGENTS.md` from the repo root downward and loads `.grok/skills` (highest) then `.agents/skills`.

## Global workflow (only when a skill is reused beyond the project)
1. Update canonical.
2. Mirror to `~/.claude/skills`, `~/.codex/skills`, `~/.cursor/skills-cursor`, `~/.grok/skills` (+ WSL equivalents if used).
3. Update `~/AGENTS.md` and `~/.codex/AGENTS.md`; keep `~/.claude/CLAUDE.md` importing `@../AGENTS.md`; update `~/.grok/config.toml [skills]` if adding canonical paths.

## Collision rules
- Don't auto-overwrite a same-named canonical skill that has different content — compare intent first.
- Prefer a generalized canonical skill; rename project-specific ones clearly (e.g. `prime-c2m-chat-to-markdown`, not `prime`).
- Treat `.claude / .codex / .cursor / .grok / .agents` copies as mirrors unless the project declares a source.

## Verification
1. Every intended repo-root mirror folder has the `SKILL.md`; compare hashes/counts against canonical.
2. **No skill folders exist outside the repo root** (no parent-wrapper `.agents/.claude/.codex/.cursor/.grok`). If found, remove them.
3. `AGENTS.md` lists each skill with its canonical path; `CLAUDE.md` imports it; Cursor has a `.cursor/rules` pointer; Grok shows them via `grok /skills`.
