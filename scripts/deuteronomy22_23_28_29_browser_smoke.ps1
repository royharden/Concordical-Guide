param([Parameter(Mandatory=$true)][string]$Url, [switch]$Numbers26JoinCandidate)
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
try {
 Run-Browser @('open',$Url) | Out-Null
 Run-Browser @('select','aside > label select','bcbooks:deut') | Out-Null
 Run-Browser @('find','role','button','click','--name','Open word study') | Out-Null
 foreach ($pair in @(@('22','29','Deut.22.29'),@('22','30','Deut.23.1'),@('23','1','Deut.23.2'),@('23','25','Deut.23.26'),@('28','68','Deut.28.68'),@('29','1','Deut.28.69'),@('29','23','Deut.29.22'),@('29','29','Deut.29.28'),@('30','1','Deut.30.1'))) {
  Run-Browser @('select','.controls label:nth-child(1) select',$pair[0]) | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select',$pair[1]) | Out-Null
  Run-Browser @('wait','--text',"OSHB $($pair[2])") | Out-Null
 }
 Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
 Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
 Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
 Run-Browser @('select','aside > label select','bcbooks:num') | Out-Null
 Run-Browser @('select','.controls label:nth-child(1) select','26') | Out-Null
 Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
 Run-Browser @('wait','--text','OSHB Num.25.19 + Num.26.1') | Out-Null
 Write-Host 'Deuteronomy two-shift browser regression passed.'
} finally {
 try { Run-Browser @('close') | Out-Null } catch { Write-Warning 'Could not close isolated browser session.' }
}
