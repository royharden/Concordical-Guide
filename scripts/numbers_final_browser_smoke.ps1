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
  Run-Browser @('select','aside > label select','bcbooks:num') | Out-Null
  Run-Browser @('find','role','button','click','--name','Open word study') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','31') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.31.1') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','32') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','7') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.32.7') | Out-Null
  if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '13') { throw 'Wrong primary word count at Numbers 32:7' }
  Run-Browser @('select','.controls label:nth-child(1) select','34') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','4') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.34.4') | Out-Null
  if ((Run-Browser @('get','count','.hebrew-token')).Trim() -ne '18') { throw 'Wrong primary word count at Numbers 34:4' }
  Run-Browser @('select','.controls label:nth-child(1) select','36') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','13') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.36.13') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
  Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.36.13') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','26') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  if ($Numbers26JoinCandidate) {
    Run-Browser @('wait','--text','OSHB Num.25.19 + Num.26.1') | Out-Null
    Run-Browser @('wait','--text','Locally adjudicated reference') | Out-Null
    if ((Run-Browser @('get','count','[aria-label="Source words Num.25.19"] .hebrew-token')).Trim() -ne '3') { throw 'Wrong first source-part count' }
    if ((Run-Browser @('get','count','[aria-label="Source words Num.26.1"] .hebrew-token')).Trim() -ne '10') { throw 'Wrong second source-part count' }
    Run-Browser @('find','role','button','click','--name','Switch main to WEB') | Out-Null
    Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
    Run-Browser @('find','role','button','click','--name','Switch main to KJV') | Out-Null
    Run-Browser @('wait','--text','OSHB Num.25.19 + Num.26.1') | Out-Null
  } else {
    Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  }
  Run-Browser @('select','.controls label:nth-child(2) select','2') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.26.2') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','29') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','40') | Out-Null
  Run-Browser @('wait','--text','OSHB Num.30.1') | Out-Null
  Run-Browser @('select','aside > label select','bcbooks:lev') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','6') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('wait','--text','OSHB Lev.5.20') | Out-Null
  Run-Browser @('select','aside > label select','bcbooks:ps') | Out-Null
  Run-Browser @('select','.controls label:nth-child(1) select','42') | Out-Null
  Run-Browser @('select','.controls label:nth-child(2) select','1') | Out-Null
  Run-Browser @('wait','--text','Locally adjudicated reference') | Out-Null
  Run-Browser @('select','aside > label select','bcbooks:deut') | Out-Null
  Run-Browser @('wait','--text','Original-language source words are unavailable for this passage and edition.') | Out-Null
  Write-Host 'Focused Numbers browser regression passed: boundaries, withheld verse, variants, WEB and prior mappings.'
} finally {
  try { Run-Browser @('close') | Out-Null } catch { Write-Warning 'Could not close isolated browser session.' }
}
