Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$validator = Join-Path $scriptDir "validate_cg.py"
$env:PYTHONDONTWRITEBYTECODE = "1"

$pythonCommand = $null
foreach ($candidate in @("py", "python", "python3")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $pythonCommand = $candidate
        break
    }
}

if ($null -eq $pythonCommand) {
    Write-Error "Python is required to run CG validation."
}

if ($pythonCommand -eq "py") {
    & py -3 $validator
} else {
    & $pythonCommand $validator
}

exit $LASTEXITCODE
