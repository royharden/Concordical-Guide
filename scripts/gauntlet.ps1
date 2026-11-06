Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot
$env:PYTHONDONTWRITEBYTECODE = "1"

Write-Host "== CG validation =="
& (Join-Path $PSScriptRoot "validate-cg.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "== CG importer fixture tests =="
$pythonCommand = $null
foreach ($candidate in @("py", "python", "python3")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $pythonCommand = $candidate
        break
    }
}

if ($null -eq $pythonCommand) {
    Write-Error "Python is required to run CG importer fixture tests."
}

$fixtureTest = Join-Path $PSScriptRoot "test_importers_with_fixtures.py"
if ($pythonCommand -eq "py") {
    & py -3 $fixtureTest
} else {
    & $pythonCommand $fixtureTest
}
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "== CG reader server tests =="
if ($pythonCommand -eq "py") {
    & py -3 (Join-Path $PSScriptRoot "test_reader_server.py")
} else {
    & $pythonCommand (Join-Path $PSScriptRoot "test_reader_server.py")
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path "app/package.json") {
    Write-Host "== CG browser typecheck and tests =="
    & npm --prefix app run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm --prefix app test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (Test-Path "package.json") {
    $package = Get-Content "package.json" -Raw | ConvertFrom-Json
    $scripts = @()
    if ($null -ne $package.scripts) {
        $scripts = $package.scripts.PSObject.Properties.Name
    }

    $runner = "npm"
    $runPrefix = @("run")
    if (Test-Path "pnpm-lock.yaml") {
        $runner = "pnpm"
        $runPrefix = @("run")
    } elseif (Test-Path "yarn.lock") {
        $runner = "yarn"
        $runPrefix = @()
    }

    foreach ($scriptName in @("lint", "typecheck", "test")) {
        if ($scripts -contains $scriptName) {
            Write-Host "== $runner $scriptName =="
            & $runner @runPrefix $scriptName
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
        }
    }
} else {
    Write-Host "No root package.json; root npm checks skipped."
}

Write-Host "CG gauntlet passed."
