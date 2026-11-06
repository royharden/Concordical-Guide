param([Parameter(Mandatory=$true)][string]$Url, [switch]$Genesis10Candidate, [switch]$Genesis30Candidate, [switch]$Genesis50Candidate, [switch]$GenesisCompleteCandidate, [switch]$Psalms10Candidate, [switch]$Psalms30Candidate, [switch]$Psalms50Candidate, [switch]$Psalms75Candidate, [switch]$Psalms100Candidate, [switch]$Psalms125Candidate, [switch]$Psalms150Candidate, [switch]$Psalm13SpansCandidate, [switch]$PsalmHeadingCandidate, [switch]$Exodus10Candidate, [switch]$Exodus20Candidate, [switch]$Exodus30Candidate, [switch]$Exodus40Candidate, [switch]$Psalm4244Candidate, [switch]$Leviticus10Candidate, [switch]$Leviticus20Candidate, [switch]$Leviticus27Candidate, [switch]$Numbers10Candidate, [switch]$Numbers20Candidate, [switch]$Numbers30Candidate)
if ($Numbers30Candidate) { $Numbers20Candidate = $true }
if ($Numbers20Candidate) { $Numbers10Candidate = $true }
if ($Numbers10Candidate) { $Leviticus27Candidate = $true }
if ($Leviticus27Candidate) { $Leviticus20Candidate = $true }
if ($Leviticus20Candidate) { $Leviticus10Candidate = $true }
if ($Leviticus10Candidate) { $Psalm4244Candidate = $true }
if ($Psalm4244Candidate) { $Exodus40Candidate = $true }
if ($Exodus40Candidate) { $Exodus30Candidate = $true }
if ($Exodus30Candidate) { $Exodus20Candidate = $true }
if ($Exodus20Candidate) { $Exodus10Candidate = $true; $PsalmHeadingCandidate = $true }
if ($Exodus10Candidate) { $Psalm13SpansCandidate = $true }
if ($PsalmHeadingCandidate) { $Psalm13SpansCandidate = $true }
if ($Psalm13SpansCandidate) { $Psalms150Candidate = $true }
if ($Psalms150Candidate) { $Psalms125Candidate = $true }
if ($Psalms125Candidate) { $Psalms100Candidate = $true }
if ($Psalms100Candidate) { $Psalms75Candidate = $true }
if ($Psalms75Candidate) { $Psalms50Candidate = $true }
if ($Psalms50Candidate) { $Psalms30Candidate = $true }
if ($Psalms30Candidate) { $Psalms10Candidate = $true }
if ($Psalms10Candidate) { $GenesisCompleteCandidate = $true }
$ErrorActionPreference = 'Stop'
$session = 'cg-reader-test-' + [guid]::NewGuid().ToString('N')
Write-Host "Isolated browser session: $session"
$shim = (Get-Command agent-browser.ps1 -ErrorAction Stop).Source
$agentCli = Join-Path (Split-Path -Parent $shim) 'node_modules/agent-browser/bin/agent-browser-win32-x64.exe'
if (-not (Test-Path -LiteralPath $agentCli)) { throw 'agent-browser executable is unavailable.' }
function Run-Browser([string[]]$BrowserArgs) {
  Write-Host "Browser check: $($BrowserArgs -join ' ')"
  $suffix = [guid]::NewGuid().ToString('N')
  $stdoutFile = Join-Path $env:TEMP ($session + '-' + $suffix + '.out')
  $stderrFile = Join-Path $env:TEMP ($session + '-' + $suffix + '.err')
  $argv = @('--session',$session) + $BrowserArgs
  $quoted = $argv | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }
  $process = Start-Process -FilePath $agentCli -ArgumentList ($quoted -join ' ') -WindowStyle Hidden -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
  if (-not $process.WaitForExit(30000)) { throw "Browser command timed out: $($BrowserArgs -join ' ')" }
  # The launched daemon can retain the first command's inherited file handles.
  $out = if ($BrowserArgs[0] -eq 'open') { '' } else { [IO.File]::ReadAllText($stdoutFile) + [IO.File]::ReadAllText($stderrFile) }
  if ($process.ExitCode -ne 0) { throw "Browser command failed: $($BrowserArgs -join ' ')`n$out" }
  return $out
}
function Require-Text([string]$Actual,[string]$Expected) {
  if (-not $Actual.Contains($Expected)) { throw "Expected '$Expected', observed '$Actual'" }
}
function Check-Heading([int]$Chapter,[int]$BodyCount,[int]$HeadingCount) {
  Run-Browser @('select','.controls label:nth-child(1) select',"$Chapter") | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('wait','--text',"OSHB Ps.$Chapter.3") | Out-Null
  Run-Browser @('wait','--text','These are verse-body words') | Out-Null
  if ((Run-Browser @('get','count','.hebrew-verse > div[dir=rtl] .hebrew-token')).Trim() -ne "$BodyCount") { throw "Wrong verse-body token count for Psalm $Chapter" }
  Run-Browser @('eval','document.querySelector(".hebrew-verse summary").scrollIntoView({block:"center"});null') | Out-Null
  Run-Browser @('click','.hebrew-verse details summary') | Out-Null
  if ((Run-Browser @('eval','document.querySelector(".hebrew-verse details").open')).Trim() -ne 'true') { throw 'Pointer did not open heading disclosure' }
  Run-Browser @('focus','.hebrew-verse details summary') | Out-Null
  Run-Browser @('press','Enter') | Out-Null
  if ((Run-Browser @('eval','document.querySelector(".hebrew-verse details").open')).Trim() -ne 'false') { throw 'Keyboard did not close heading disclosure' }
  Run-Browser @('press','Enter') | Out-Null
  Run-Browser @('wait','--text',"OSHB Ps.$Chapter.2") | Out-Null
  Run-Browser @('wait','--text','Source superscription excerpt (not verse text)') | Out-Null
  if ((Run-Browser @('get','count','.hebrew-verse details .hebrew-token')).Trim() -ne "$HeadingCount") { throw "Wrong heading token count for Psalm $Chapter" }
}
function Wait-ForTab([string]$Id) {
  for ($attempt=0; $attempt -lt 10; $attempt++) {
    $tabs = Run-Browser @('tab')
    if ($tabs.Contains("[$Id]")) { return }
    Start-Sleep -Milliseconds 300
  }
  $ui = Run-Browser @('eval','document.querySelector(".workspace > [role=status]")?.textContent || "no status"')
  $errors = Run-Browser @('errors')
  throw "Comparison tab $Id did not appear. Last tab listing: $tabs. Reader status: $ui. Page errors: $errors"
}
try {
  Run-Browser @('open',$Url) | Out-Null
  Run-Browser @('select','aside > label select','bcbooks:1-ne') | Out-Null
  Require-Text (Run-Browser @('get','text','.edition-current')) 'Old and New Testaments'
  Run-Browser @('select','aside > label select','bcbooks:gen') | Out-Null
  Run-Browser @('find','role','button','click','--name','Open word study') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.1') | Out-Null
  Require-Text (Run-Browser @('get','count','.hebrew-token')) '7'
  if ($Psalms10Candidate) { Require-Text (Run-Browser @('get','text','.hebrew-verse')) 'alternate readings in notes' }
  Require-Text (Run-Browser @('get','attr','.hebrew-verse [lang=he]','dir')) 'rtl'
  if ($Exodus10Candidate) {
    Run-Browser @('select','aside > label select','bcbooks:ex') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.1.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','4') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.4.2') | Out-Null
    if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '7') { throw 'Expected seven primary tokens at Exodus 4:2' }
    Run-Browser @('select','.controls label:nth-child(1) select','7') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','25') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.7.25') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','8') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.7.26') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','4') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.7.29') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.8.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','32') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.8.28') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','9') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.9.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','10') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','29') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.10.29') | Out-Null
    Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
    Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
    Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
    Run-Browser @('wait','--text','OSHB Exod.10.29') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','11') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
    if ($Exodus20Candidate) {
      Run-Browser @('wait','--text','OSHB Exod.11.1') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','16') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
      Run-Browser @('wait','--text','OSHB Exod.16.2') | Out-Null
      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '10') { throw 'Expected ten main words at Exodus 16:2' }
      Run-Browser @('select','.controls label:nth-child(2) select','7') | Out-Null
      Run-Browser @('wait','--text','OSHB Exod.16.7') | Out-Null
      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '15') { throw 'Expected fifteen main words at Exodus 16:7' }
      Run-Browser @('select','.controls label:nth-child(1) select','20') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','26') | Out-Null
      Run-Browser @('wait','--text','OSHB Exod.20.26') | Out-Null
      Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
      Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
      Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
      Run-Browser @('wait','--text','OSHB Exod.20.26') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','21') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
      if ($Exodus30Candidate) {
        Run-Browser @('wait','--text','OSHB Exod.21.1') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','36') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.21.36') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','22') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.21.37') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.22.1') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.22.4') | Out-Null
        if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '17') { throw 'Expected 17 main words at KJV Exodus 22:5' }
        Run-Browser @('select','.controls label:nth-child(2) select','27') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.22.26') | Out-Null
        if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '17') { throw 'Expected 17 main words at KJV Exodus 22:27' }
        Run-Browser @('select','.controls label:nth-child(2) select','31') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.22.30') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','23') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.23.1') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','30') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','38') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.30.38') | Out-Null
        Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
        Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
        Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
        Run-Browser @('wait','--text','OSHB Exod.30.38') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','31') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
        if ($Exodus40Candidate) {
          Run-Browser @('wait','--text','OSHB Exod.31.1') | Out-Null
          Run-Browser @('select','.controls label:nth-child(1) select','32') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','19') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.32.19') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '20') { throw 'Expected 20 primary words at Exodus 32:19' }
          Run-Browser @('select','.controls label:nth-child(1) select','37') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','8') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.37.8') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '15') { throw 'Expected 15 primary words at Exodus 37:8' }
          Run-Browser @('select','.controls label:nth-child(1) select','39') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','4') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.39.4') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '8') { throw 'Expected eight primary words at Exodus 39:4' }
          Run-Browser @('select','.controls label:nth-child(2) select','33') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.39.33') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '15') { throw 'Expected 15 primary words at Exodus 39:33' }
          Run-Browser @('select','.controls label:nth-child(1) select','40') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','38') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.40.38') | Out-Null
          Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
          Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
          Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
          Run-Browser @('wait','--text','OSHB Exod.40.38') | Out-Null
          Run-Browser @('select','aside > label select','bcbooks:lev') | Out-Null
          if ($Leviticus10Candidate) {
            Run-Browser @('wait','--text','OSHB Lev.1.1') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','5') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','19') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.5.19') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','6') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.5.20') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','7') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.5.26') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','8') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.6.1') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','30') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.6.23') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','7') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.7.1') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','9') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','22') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.9.22') | Out-Null
            if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '12') { throw 'Expected 12 primary words at Leviticus 9:22' }
            Run-Browser @('select','.controls label:nth-child(1) select','10') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','20') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.10.20') | Out-Null
            Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
            Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
            Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
            Run-Browser @('wait','--text','OSHB Lev.10.20') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','11') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
            if ($Leviticus20Candidate) {
              Run-Browser @('wait','--text','OSHB Lev.11.1') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','21') | Out-Null
              Run-Browser @('wait','--text','OSHB Lev.11.21') | Out-Null
              if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '19') { throw 'Expected 19 primary words at Leviticus 11:21' }
              Run-Browser @('select','.controls label:nth-child(1) select','16') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','21') | Out-Null
              Run-Browser @('wait','--text','OSHB Lev.16.21') | Out-Null
              if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '31') { throw 'Expected 31 primary words at Leviticus 16:21' }
              Run-Browser @('select','.controls label:nth-child(1) select','20') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','27') | Out-Null
              Run-Browser @('wait','--text','OSHB Lev.20.27') | Out-Null
              Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
              Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
              Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
              Run-Browser @('wait','--text','OSHB Lev.20.27') | Out-Null
              Run-Browser @('select','.controls label:nth-child(1) select','21') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
              if ($Leviticus27Candidate) {
                Run-Browser @('wait','--text','OSHB Lev.21.1') | Out-Null
                Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
                Run-Browser @('wait','--text','OSHB Lev.21.5') | Out-Null
                if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '12') { throw 'Expected 12 primary words at Leviticus 21:5' }
                Run-Browser @('select','.controls label:nth-child(1) select','25') | Out-Null
                Run-Browser @('select','.controls label:nth-child(2) select','30') | Out-Null
                Run-Browser @('wait','--text','OSHB Lev.25.30') | Out-Null
                if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '22') { throw 'Expected 22 primary words at Leviticus 25:30' }
                Run-Browser @('select','.controls label:nth-child(1) select','27') | Out-Null
                Run-Browser @('select','.controls label:nth-child(2) select','34') | Out-Null
                Run-Browser @('wait','--text','OSHB Lev.27.34') | Out-Null
                Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
                Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
                Run-Browser @('wait','--text','OSHB Lev.27.34') | Out-Null
                Run-Browser @('select','aside > label select','bcbooks:num') | Out-Null
                if ($Numbers10Candidate) {
                  Run-Browser @('wait','--text','OSHB Num.1.1') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(2) select','16') | Out-Null
                  Run-Browser @('wait','--text','OSHB Num.1.16') | Out-Null
                  if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '10') { throw 'Expected 10 primary words at Numbers 1:16' }
                  Run-Browser @('select','.controls label:nth-child(1) select','7') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(2) select','89') | Out-Null
                  Run-Browser @('wait','--text','OSHB Num.7.89') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(1) select','10') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(2) select','36') | Out-Null
                  Run-Browser @('wait','--text','OSHB Num.10.36') | Out-Null
                  Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
                  Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                  Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
                  Run-Browser @('wait','--text','OSHB Num.10.36') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(1) select','11') | Out-Null
                  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                  if ($Numbers20Candidate) {
                    Run-Browser @('wait','--text','OSHB Num.11.1') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(1) select','12') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','3') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.12.3') | Out-Null
                    if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '10') { throw 'Expected 10 primary words at Numbers 12:3' }
                    Run-Browser @('select','.controls label:nth-child(1) select','14') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','36') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.14.36') | Out-Null
                    if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '17') { throw 'Expected 17 primary words at Numbers 14:36' }
                    Run-Browser @('select','.controls label:nth-child(1) select','16') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','11') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.16.11') | Out-Null
                    if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '13') { throw 'Expected 13 primary words at Numbers 16:11' }
                    Run-Browser @('select','.controls label:nth-child(2) select','35') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.16.35') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','36') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.17.1') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','50') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.17.15') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(1) select','17') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.17.16') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','13') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.17.28') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(1) select','20') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','29') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.20.29') | Out-Null
                    Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
                    Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                    Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
                    Run-Browser @('wait','--text','OSHB Num.20.29') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(1) select','21') | Out-Null
                    Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                    if ($Numbers30Candidate) {
                      Run-Browser @('wait','--text','OSHB Num.21.1') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','32') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.21.32') | Out-Null
                      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '12') { throw 'Expected 12 primary words at Numbers 21:32' }
                      Run-Browser @('select','.controls label:nth-child(1) select','23') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','13') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.23.13') | Out-Null
                      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '21') { throw 'Expected 21 primary words at Numbers 23:13' }
                      Run-Browser @('select','.controls label:nth-child(1) select','25') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','18') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.25.18') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(1) select','26') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                      Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.26.2') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','9') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.26.9') | Out-Null
                      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '21') { throw 'Expected 21 primary words at Numbers 26:9' }
                      Run-Browser @('select','.controls label:nth-child(1) select','29') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','39') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.29.39') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','40') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.30.1') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(1) select','30') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.30.2') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','16') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.30.17') | Out-Null
                      Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
                      Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                      Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
                      Run-Browser @('wait','--text','OSHB Num.30.17') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(1) select','31') | Out-Null
                      Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
                      Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
                    } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
                  } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
                } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
              } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
            } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
          } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
        } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
      } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
    } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
    Run-Browser @('select','aside > label select','bcbooks:gen') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.1.1') | Out-Null
  }
  Run-Browser @('find','role','button','click','--name','Look up H7225') | Out-Null
  Run-Browser @('wait','--text','beginning') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','16') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.16') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','31') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.31') | Out-Null
  Run-Browser @('set','viewport','390','844') | Out-Null
  $studyColumns = (Run-Browser @('eval','getComputedStyle(document.querySelector(".study-layout")).gridTemplateColumns') | ConvertFrom-Json)
  if (($studyColumns -split ' ').Count -ne 1) { throw "Expected portrait word-study layout to stack; got $studyColumns" }
  Run-Browser @('set','viewport','1280','800') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
  Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.31') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','2') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.2.1') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','13') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.2.13') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','25') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.2.25') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
  Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','3') | Out-Null
  if ($Genesis10Candidate -or $Genesis30Candidate -or $Genesis50Candidate -or $GenesisCompleteCandidate) {
    Run-Browser @('wait','--text','OSHB Gen.3.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','6') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','11') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.6.11') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','10') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','32') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.10.32') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','11') | Out-Null
    if ($Genesis30Candidate -or $Genesis50Candidate -or $GenesisCompleteCandidate) {
      Run-Browser @('wait','--text','OSHB Gen.11.1') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','20') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','18') | Out-Null
      Run-Browser @('wait','--text','OSHB Gen.20.18') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','30') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','43') | Out-Null
      Run-Browser @('wait','--text','OSHB Gen.30.43') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','31') | Out-Null
    }
  }
  if ($GenesisCompleteCandidate) {
    Run-Browser @('select','.controls label:nth-child(2) select','47') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.31.47') | Out-Null
    Require-Text (Run-Browser @('get','count','.hebrew-token [lang=arc]')) '2'
    Require-Text (Run-Browser @('get','text','.hebrew-verse')) 'Aramaic (source morphology)'
    Run-Browser @('select','.controls label:nth-child(2) select','55') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.32.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','32') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.32.2') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','32') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.32.33') | Out-Null
  } else {
    Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  }
  if ($Genesis50Candidate -or $GenesisCompleteCandidate) {
    if (-not $GenesisCompleteCandidate) {
      Run-Browser @('select','.controls label:nth-child(1) select','32') | Out-Null
      Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
    }
    Run-Browser @('select','.controls label:nth-child(1) select','33') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.33.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','42') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','19') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.42.19') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','50') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','26') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.50.26') | Out-Null
  }
  Run-Browser @('select','aside > label select','bcbooks:ps') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','3') | Out-Null
  Run-Browser @('wait','--text','OSHB Ps.3.2') | Out-Null
  if ($Psalms10Candidate) {
    Run-Browser @('select','.controls label:nth-child(1) select','1') | Out-Null
    Run-Browser @('wait','--text','OSHB Ps.1.1') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','5') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','12') | Out-Null
    Run-Browser @('wait','--text','OSHB Ps.5.13') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','10') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','18') | Out-Null
    Run-Browser @('wait','--text','OSHB Ps.10.18') | Out-Null
    Run-Browser @('select','.controls label:nth-child(1) select','13') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
    if ($Psalm13SpansCandidate) {
      Run-Browser @('wait','--text','OSHB Ps.13.6, source-word span a') | Out-Null
      Run-Browser @('wait','--text','This is a partial source verse') | Out-Null
      if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '6') { throw 'Expected six tokens in Psalm 13:5 source span' }
    } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
    if ($Psalms30Candidate) {
      Run-Browser @('select','.controls label:nth-child(2) select','6') | Out-Null
      if ($Psalm13SpansCandidate) {
        Run-Browser @('wait','--text','OSHB Ps.13.6, source-word span b') | Out-Null
        if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '5') { throw 'Expected five tokens in Psalm 13:6 source span' }
      } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
      Run-Browser @('select','.controls label:nth-child(2) select','4') | Out-Null
      Run-Browser @('wait','--text','OSHB Ps.13.5') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','12') | Out-Null
      Run-Browser @('wait','--text','OSHB Ps.12.2') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','30') | Out-Null
      Run-Browser @('select','.controls label:nth-child(2) select','12') | Out-Null
      Run-Browser @('wait','--text','OSHB Ps.30.13') | Out-Null
      Run-Browser @('select','.controls label:nth-child(1) select','31') | Out-Null
      if ($Psalms50Candidate) {
        Run-Browser @('wait','--text','OSHB Ps.31.2') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','42') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
        if ($Psalm4244Candidate) {
          Run-Browser @('wait','--text','OSHB Ps.42.2') | Out-Null
          Run-Browser @('wait','--text','Locally adjudicated reference') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '10') { throw 'Unexpected locally adjudicated Psalm 42 token count' }
          Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
          Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
          Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.42.2') | Out-Null
        } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
        Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.42.3') | Out-Null
        if ($Psalm4244Candidate -and (Run-Browser @('get','text','.hebrew-verse')).Contains('Locally adjudicated reference')) { throw 'Adjudication label leaked into adjacent ordinary verse' }
        Run-Browser @('select','.controls label:nth-child(1) select','44') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
        if ($Psalm4244Candidate) {
          Run-Browser @('wait','--text','OSHB Ps.44.2') | Out-Null
          Run-Browser @('wait','--text','Locally adjudicated reference') | Out-Null
          if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '11') { throw 'Unexpected locally adjudicated Psalm 44 token count' }
          Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
          Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
          Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.44.2') | Out-Null
        } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
        Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.44.3') | Out-Null
        if ($Psalm4244Candidate -and (Run-Browser @('get','text','.hebrew-verse')).Contains('Locally adjudicated reference')) { throw 'Adjudication label leaked into adjacent ordinary verse' }
        Run-Browser @('select','.controls label:nth-child(1) select','50') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','23') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.50.23') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','51') | Out-Null
      }
      if ($PsalmHeadingCandidate) {
        Check-Heading 51 7 9
        Check-Heading 52 8 12
        Check-Heading 54 5 8
        Check-Heading 51 7 9
      } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
      if ($Psalms75Candidate) {
        Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.51.4') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','60') | Out-Null
        if ($PsalmHeadingCandidate) { Check-Heading 60 6 17 } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
        Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.60.4') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','66') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.66.1') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','75') | Out-Null
        Run-Browser @('select','.controls label:nth-child(2) select','10') | Out-Null
        Run-Browser @('wait','--text','OSHB Ps.75.11') | Out-Null
        Run-Browser @('select','.controls label:nth-child(1) select','76') | Out-Null
        if ($Psalms100Candidate) {
          Run-Browser @('select','.controls label:nth-child(2) select','10') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.76.11') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.76.2') | Out-Null
          Run-Browser @('select','.controls label:nth-child(1) select','89') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.89.2') | Out-Null
          Run-Browser @('select','.controls label:nth-child(1) select','100') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','3') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.100.3') | Out-Null
          $psalm100Count = (Run-Browser @('get','count','.hebrew-token')).Trim()
          if ($psalm100Count -ne '12') { throw "Expected 12 main-reading tokens at Psalm 100:3, got $psalm100Count" }
          Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
          Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
          Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
          Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
          Run-Browser @('wait','--text','OSHB Ps.100.5') | Out-Null
          Run-Browser @('select','.controls label:nth-child(1) select','101') | Out-Null
          if ($Psalms125Candidate) {
            Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
            Run-Browser @('wait','--text','OSHB Ps.101.5') | Out-Null
            $psalm101Count = (Run-Browser @('get','count','.hebrew-token')).Trim()
            if ($psalm101Count -ne '12') { throw "Expected 12 main-reading tokens at Psalm 101:5, got $psalm101Count" }
            Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
            Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
            Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','102') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
            Run-Browser @('wait','--text','OSHB Ps.102.2') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','108') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
            Run-Browser @('wait','--text','OSHB Ps.108.2') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','119') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','176') | Out-Null
            Run-Browser @('wait','--text','OSHB Ps.119.176') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','125') | Out-Null
            Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
            Run-Browser @('wait','--text','OSHB Ps.125.5') | Out-Null
            Run-Browser @('select','.controls label:nth-child(1) select','126') | Out-Null
            if ($Psalms150Candidate) {
              Run-Browser @('select','.controls label:nth-child(2) select','4') | Out-Null
              Run-Browser @('wait','--text','OSHB Ps.126.4') | Out-Null
              $psalm126Count = (Run-Browser @('get','count','.hebrew-token')).Trim()
              if ($psalm126Count -ne '6') { throw "Expected 6 main-reading tokens at Psalm 126:4, got $psalm126Count" }
              Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
              Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
              Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
              Run-Browser @('select','.controls label:nth-child(1) select','140') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
              Run-Browser @('wait','--text','OSHB Ps.140.2') | Out-Null
              Run-Browser @('select','.controls label:nth-child(1) select','142') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
              Run-Browser @('wait','--text','OSHB Ps.142.2') | Out-Null
              Run-Browser @('select','.controls label:nth-child(1) select','150') | Out-Null
              Run-Browser @('select','.controls label:nth-child(2) select','6') | Out-Null
              Run-Browser @('wait','--text','OSHB Ps.150.6') | Out-Null
            } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
          } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
        } else { Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null }
      }
    }
  }
  Run-Browser @('select','aside > label select','bcbooks:gen') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.1') | Out-Null
  if ($Psalms10Candidate) {
    Run-Browser @('select','.controls label:nth-child(1) select','8') | Out-Null
    Run-Browser @('select','.controls label:nth-child(2) select','17') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.8.17') | Out-Null
    $mainCount = (Run-Browser @('get','count','.hebrew-token')).Trim()
    if ($mainCount -ne '21') { throw "Expected 21 main-reading tokens at Genesis 8:17, got $mainCount" }
    Run-Browser @('select','.controls label:nth-child(1) select','1') | Out-Null
    Run-Browser @('wait','--text','OSHB Gen.1.1') | Out-Null
  }
  Run-Browser @('eval','window.__cgFetch=window.fetch.bind(window);window.__cgStarted=false;window.__cgFinished=false;window.fetch=(...a)=>String(a[0]).includes("/api/hebrew-passage?")&&String(a[0]).includes("verse=5")?new Promise((resolve,reject)=>{window.__cgStarted=true;window.__cgRelease=()=>window.__cgFetch(a[0]).then(r=>{window.__cgFinished=true;resolve(r)},reject)}):window.__cgFetch(...a);null') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
  Require-Text (Run-Browser @('eval','window.__cgStarted && typeof window.__cgRelease === "function"')) 'true'
  Run-Browser @('select','.controls label:nth-child(2) select','31') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.31') | Out-Null
  Require-Text (Run-Browser @('eval','window.__cgStarted && !window.__cgFinished')) 'true'
  Run-Browser @('eval','window.__cgRelease();null') | Out-Null
  Run-Browser @('wait','--fn','window.__cgFinished === true') | Out-Null
  Require-Text (Run-Browser @('get','text','.hebrew-verse')) 'OSHB Gen.1.31'
  Run-Browser @('eval','window.fetch=window.__cgFetch') | Out-Null
  Run-Browser @('eval','window.__cgStarted=false;window.__cgFinished=false;window.fetch=(...a)=>String(a[0]).includes("/api/hebrew-passage?")&&String(a[0]).includes("verse=5")?new Promise((resolve,reject)=>{window.__cgStarted=true;window.__cgRelease=()=>window.__cgFetch(a[0]).then(r=>{window.__cgFinished=true;resolve(r)},reject)}):window.__cgFetch(...a);null') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
  Require-Text (Run-Browser @('eval','window.__cgStarted && !window.__cgFinished')) 'true'
  Run-Browser @('find','role','button','click','--name','Hide word study') | Out-Null
  Run-Browser @('eval','window.__cgRelease();null') | Out-Null
  Run-Browser @('wait','--fn','window.__cgFinished === true') | Out-Null
  Require-Text (Run-Browser @('get','count','.word-study')) '0'
  Run-Browser @('eval','window.fetch=window.__cgFetch') | Out-Null
  Run-Browser @('find','role','button','click','--name','Open word study') | Out-Null
  Run-Browser @('wait','--text','OSHB Gen.1.5') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('fill','.word-study input','H7225') | Out-Null
  Run-Browser @('press','Enter') | Out-Null
  Run-Browser @('wait','--text','beginning') | Out-Null
  Require-Text (Run-Browser @('get','text','.word-study')) 'beginning'
  Run-Browser @('fill','.word-study input','G26') | Out-Null
  Run-Browser @('press','Enter') | Out-Null
  Run-Browser @('wait','--text','affection') | Out-Null
  Require-Text (Run-Browser @('get','text','.word-study')) 'affection'
  Run-Browser @('select','aside > label select','bcbooks:1-ne') | Out-Null
  Require-Text (Run-Browser @('get','text','.word-study')) 'applies to the Old and New Testaments'
  Run-Browser @('select','aside > label select','bcbooks:gen') | Out-Null
  Run-Browser @('find','role','button','click','--name','Hide word study') | Out-Null
  Require-Text (Run-Browser @('get','text','.edition-current')) 'Main edition: KJV'
  Require-Text (Run-Browser @('get','count','.panes .reading')) '2'
  Run-Browser @('set','viewport','1280','800') | Out-Null
  $desktopColumns = (Run-Browser @('eval','getComputedStyle(document.querySelector(".panes")).gridTemplateColumns') | ConvertFrom-Json)
  if (($desktopColumns -split ' ').Count -ne 2) { throw "Expected two desktop columns; got $desktopColumns" }
  Run-Browser @('set','viewport','390','844') | Out-Null
  $phoneColumns = (Run-Browser @('eval','getComputedStyle(document.querySelector(".panes")).gridTemplateColumns') | ConvertFrom-Json)
  if (($phoneColumns -split ' ').Count -ne 1) { throw "Expected stacked portrait panes; got $phoneColumns" }
  Run-Browser @('set','viewport','1280','800') | Out-Null
  Run-Browser @('find','role','button','click','--name','Hide side-by-side comparison') | Out-Null
  Require-Text (Run-Browser @('get','count','.panes .reading')) '1'
  Run-Browser @('find','role','button','click','--name','Compare side by side') | Out-Null
  Require-Text (Run-Browser @('get','count','.panes .reading')) '2'
  Run-Browser @('scroll','down','500','--selector','.panes .reading:first-child .verse-list') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','2') | Out-Null
  Require-Text (Run-Browser @('get','text','.toolbar h2')) 'Genesis 2:1'
  Run-Browser @('select','.controls label:nth-child(1) select','1') | Out-Null
  Run-Browser @('find','role','button','click','--name','Open comparison window') | Out-Null
  Wait-ForTab 't2'
  Run-Browser @('tab','t1') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','5') | Out-Null
  Run-Browser @('tab','t2') | Out-Null
  Require-Text (Run-Browser @('get','text','.toolbar h2')) 'Genesis 1:5'
  Run-Browser @('select','.controls label:nth-child(2) select','9') | Out-Null
  Run-Browser @('tab','t1') | Out-Null
  Require-Text (Run-Browser @('get','text','.toolbar h2')) 'Genesis 1:9'
  Run-Browser @('reload') | Out-Null
  Require-Text (Run-Browser @('get','text','.toolbar h2')) 'Genesis 1:9'
  Run-Browser @('tab','close','t2') | Out-Null
  Run-Browser @('find','role','button','click','--name','Open comparison window') | Out-Null
  Wait-ForTab 't3'
  Run-Browser @('tab','t1') | Out-Null
  Run-Browser @('tab','close','t3') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
  Require-Text (Run-Browser @('get','text','.panes .reading:first-child .verse-list .verse:first-child')) 'the heavens and the earth'
  Run-Browser @('find','role','button','click','--name','Open comparison window') | Out-Null
  Wait-ForTab 't4'
  Run-Browser @('tab','t4') | Out-Null
  Require-Text (Run-Browser @('get','text','.pane-header')) 'KJV'
  Run-Browser @('tab','close','t4') | Out-Null
  Run-Browser @('tab','t1') | Out-Null
  Run-Browser @('fill','.notes form textarea','Isolated browser test note') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','3') | Out-Null
  Require-Text (Run-Browser @('get','text','.notes form label:first-child')) 'Genesis 1:1'
  Run-Browser @('click','.notes button[type="submit"]') | Out-Null
  Run-Browser @('wait','--text','Note saved on this device.') | Out-Null
  Run-Browser @('reload') | Out-Null
  Run-Browser @('wait','--text','Isolated browser test note') | Out-Null
  Require-Text (Run-Browser @('get','text','.note-text')) 'Isolated browser test note'
  $serialized = Run-Browser @('eval','localStorage.getItem("cg-notes-v1")') | ConvertFrom-Json
  $doc = $serialized | ConvertFrom-Json
  $original = $doc.notes[0]
  $conflict = @{id=$original.id;book=$original.book;chapter=$original.chapter;start=$original.start;end=$original.end;text='Conflicting import';updated=$original.updated}
  $extra = @{id=[guid]::NewGuid().ToString();book=$original.book;chapter=$original.chapter;start=$original.start;end=$original.end;text='Imported synthetic note';updated=$original.updated}
  $backup = Join-Path $env:TEMP ($session + '-import.json')
  @{version=1;notes=@($conflict,$extra)} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $backup -Encoding utf8
  Run-Browser @('upload','input[type=file]',$backup) | Out-Null
  Run-Browser @('wait','--text','1 conflicting IDs skipped') | Out-Null
  Require-Text (Run-Browser @('get','text','.notes')) 'Imported synthetic note'
  Run-Browser @('reload') | Out-Null
  Run-Browser @('wait','--text','Imported synthetic note') | Out-Null
  Run-Browser @('tab','new',$Url) | Out-Null
  Wait-ForTab 't5'
  Run-Browser @('wait','--text','Imported synthetic note') | Out-Null
  Run-Browser @('tab','t1') | Out-Null
  Run-Browser @('fill','.notes form textarea','First simultaneous draft') | Out-Null
  Run-Browser @('click','.notes button[type="submit"]') | Out-Null
  Run-Browser @('wait','--text','First simultaneous draft') | Out-Null
  Run-Browser @('tab','t5') | Out-Null
  Run-Browser @('eval','document.querySelector(".note-actions button").click()') | Out-Null
  Run-Browser @('wait','--text','Backup ready.') | Out-Null
  Require-Text (Run-Browser @('get','value','.notes textarea[readonly]')) 'First simultaneous draft'
  Run-Browser @('fill','.notes form textarea','Second simultaneous draft') | Out-Null
  Run-Browser @('click','.notes button[type="submit"]') | Out-Null
  Run-Browser @('wait','--text','Notes changed in another window') | Out-Null
  Require-Text (Run-Browser @('get','value','.notes form textarea')) 'Second simultaneous draft'
  Run-Browser @('tab','close','t5') | Out-Null
  Run-Browser @('tab','t1') | Out-Null
  Require-Text (Run-Browser @('get','text','.notes')) 'First simultaneous draft'
  Run-Browser @('select','aside > label select','bcbooks:rom') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','16') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','25') | Out-Null
  Require-Text (Run-Browser @('get','count','.panes .reading')) '2'
  Require-Text (Run-Browser @('get','text','.panes .reading:nth-child(2)')) 'Verse 25 is unavailable'
  Run-Browser @('select','.controls label:nth-child(1) select','14') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','24') | Out-Null
  Run-Browser @('wait','--text','Verse 24 is unavailable') | Out-Null
  Require-Text (Run-Browser @('get','text','.panes .reading:nth-child(1)')) 'Verse 24 is unavailable'
  Run-Browser @('select','aside > label select','bcbooks:1-ne') | Out-Null
  Require-Text (Run-Browser @('get','count','.panes .reading')) '1'
  Require-Text (Run-Browser @('get','text','.edition-current')) 'Old and New Testaments'
  Run-Browser @('select','aside > label select','bcbooks:gen') | Out-Null
  Require-Text (Run-Browser @('get','count','.panes .reading')) '2'
  $export = Join-Path $env:TEMP ($session + '-export.json')
  Run-Browser @('eval','document.querySelector(".note-actions button").click()') | Out-Null
  Run-Browser @('wait','--text','Backup ready.') | Out-Null
  # The CLI's download handler cancels blob downloads on this host. Exercise the
  # explicit copyable-backup fallback and import it without claiming a download.
  $backupText = Run-Browser @('get','value','.notes textarea[readonly]')
  [IO.File]::WriteAllText($export,$backupText,[Text.UTF8Encoding]::new($false))
  $exportedDoc = Get-Content -Raw -LiteralPath $export | ConvertFrom-Json
  if ($exportedDoc.version -ne 1 -or $exportedDoc.notes[0].text -ne 'Isolated browser test note') { throw 'Export did not preserve the synthetic note.' }
  Run-Browser @('upload','input[type=file]',$export) | Out-Null
  Run-Browser @('wait','--text','identical') | Out-Null
  Write-Host 'Browser smoke passed: WEB, rapid navigation, notes and backup-text round-trip, import conflict and cross-tab protection, popup reopen, two-way sync, reconnect and missing verses in both editions. Browser download completion was not verified.'
} finally {
  try { Run-Browser @('close') | Out-Null } catch { Write-Warning 'Could not close the isolated browser session.' }
}
