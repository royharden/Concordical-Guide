#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python3}"
export PYTHONDONTWRITEBYTECODE=1
"$python_bin" scripts/validate_cg.py

echo "== CG importer fixture tests =="
"$python_bin" scripts/test_importers_with_fixtures.py

if [ -f package.json ]; then
  if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then
    runner="pnpm run"
  elif command -v yarn >/dev/null 2>&1 && [ -f yarn.lock ]; then
    runner="yarn"
  else
    runner="npm run"
  fi

  for script_name in lint typecheck test; do
    if node -e "const p=require('./package.json'); process.exit(p.scripts && p.scripts['$script_name'] ? 0 : 1)"; then
      # shellcheck disable=SC2086
      $runner "$script_name"
    fi
  done
else
  echo "No package.json yet; app lint/type/test checks skipped."
fi

echo "CG gauntlet passed."
