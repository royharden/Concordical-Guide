Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$sourcesPath = Join-Path $repoRoot "data/manifests/sources.json"
$downloadsRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "data/downloads"))
$receiptDir = Join-Path $repoRoot ".agent-work/receipts"
$receiptPath = Join-Path $receiptDir "initial-source-downloads.json"

New-Item -ItemType Directory -Force -Path $receiptDir | Out-Null

$sources = Get-Content -LiteralPath $sourcesPath -Raw | ConvertFrom-Json
$downloaded = @()

foreach ($source in $sources.sources) {
    if ($null -eq $source.download_urls) {
        continue
    }
    $storagePath = $source.storage.path
    if ([string]::IsNullOrWhiteSpace($storagePath)) {
        throw "Source '$($source.id)' does not define storage.path."
    }
    $targetDir = Join-Path $repoRoot $storagePath
    $targetDirFull = [System.IO.Path]::GetFullPath($targetDir)
    $downloadsRootPrefix = $downloadsRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    if (
        -not $targetDirFull.Equals($downloadsRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $targetDirFull.StartsWith($downloadsRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Source '$($source.id)' storage.path must stay under data/downloads/: $storagePath"
    }
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    foreach ($url in $source.download_urls) {
        $fileName = [System.IO.Path]::GetFileName(([Uri]$url).AbsolutePath)
        if ([string]::IsNullOrWhiteSpace($fileName)) {
            throw "Could not determine file name from URL: $url"
        }
        $targetPath = Join-Path $targetDir $fileName
        Write-Host "Downloading $url"
        Invoke-WebRequest -Uri $url -OutFile $targetPath
        $file = Get-Item -LiteralPath $targetPath
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath
        $downloaded += [ordered]@{
            source_id = $source.id
            url = $url
            path = (Resolve-Path -LiteralPath $targetPath).Path.Substring($repoRoot.Path.Length + 1).Replace("\", "/")
            bytes = $file.Length
            sha256 = $hash.Hash.ToLowerInvariant()
        }
    }
}

$receipt = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    downloads = $downloaded
}

$receipt | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $receiptPath -Encoding utf8
Write-Host "Wrote receipt: $receiptPath"
