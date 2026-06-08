#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
hook_path="$repo_root/.git/hooks/pre-commit"

cat > "$hook_path" <<'HOOK'
#!/usr/bin/env sh
set -eu
if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/gauntlet.ps1
else
  sh scripts/gauntlet.sh
fi
HOOK

chmod +x "$hook_path"
echo "Installed pre-commit hook: $hook_path"
