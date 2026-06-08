Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$hookDir = Join-Path $repoRoot ".git/hooks"
$hookPath = Join-Path $hookDir "pre-commit"

if (-not (Test-Path $hookDir)) {
    Write-Error "No .git/hooks directory found. Run this from inside the git repository."
}

$hook = @'
#!/usr/bin/env sh
set -eu
if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/gauntlet.ps1
elif command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/gauntlet.ps1
else
  sh scripts/gauntlet.sh
fi
'@

[System.IO.File]::WriteAllText($hookPath, $hook, [System.Text.UTF8Encoding]::new($false))
Write-Host "Installed pre-commit hook: $hookPath"
