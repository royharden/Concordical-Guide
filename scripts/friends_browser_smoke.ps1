param([Parameter(Mandatory=$true)][string]$Url)
$ErrorActionPreference='Stop'
$session='cg-friends-test-'+[guid]::NewGuid().ToString('N')
Write-Host "Isolated browser session: $session"
$shim=(Get-Command agent-browser.ps1 -ErrorAction Stop).Source
$cli=Join-Path (Split-Path -Parent $shim) 'node_modules/agent-browser/bin/agent-browser-win32-x64.exe'
function Browser([string[]]$argsList){
  Write-Host "Browser check: $($argsList -join ' ')"
  $id=[guid]::NewGuid().ToString('N');$out=Join-Path $env:TEMP "$session-$id.out";$err=Join-Path $env:TEMP "$session-$id.err"
  $quoted=(@('--session',$session)+$argsList)|ForEach-Object {'"'+$_.Replace('"','\"')+'"'}
  $p=Start-Process -FilePath $cli -ArgumentList ($quoted -join ' ') -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  if(-not $p.WaitForExit(30000)){throw "Timed out: $($argsList -join ' ')"}
  $result=if($argsList[0] -eq 'open'){''}else{[IO.File]::ReadAllText($out)+[IO.File]::ReadAllText($err)}
  if($p.ExitCode -ne 0){throw "Failed: $($argsList -join ' ') $result"};return $result
}
function Has([string]$actual,[string]$expected){if(-not $actual.Contains($expected)){throw "Expected '$expected', got '$actual'"}}
try {
  Browser @('open',$Url)|Out-Null
  Has (Browser @('get','count','.friends-insights')) '0'
  Browser @('fill','.notes form textarea','Synthetic private note - never shared')|Out-Null
  Browser @('click','.notes button[type=submit]')|Out-Null
  Browser @('wait','--text','Note saved on this device.')|Out-Null
  Browser @('eval','window.__noteBefore=localStorage.getItem("cg-notes-v1");window.__gets=[];window.__requests=[];window.__origGet=Storage.prototype.getItem;Storage.prototype.getItem=function(k){window.__gets.push(k);return window.__origGet.call(this,k)};window.__origFetch=window.fetch.bind(window);window.fetch=(...a)=>{window.__requests.push(String(a[0]));return window.__origFetch(...a)};null')|Out-Null
  Browser @('focus','button[aria-controls=friends-insights-panel]')|Out-Null
  Browser @('press','Space')|Out-Null
  Browser @('wait','.friends-insights')|Out-Null
  Has (Browser @('get','text','.friends-insights')) 'FICTIONAL LOCAL DEMO'
  Browser @('select','.controls label:nth-child(2) select','31')|Out-Null
  Browser @('wait','--text','Maya (fictional)')|Out-Null
  Has (Browser @('get','text','.friends-insights')) 'genesis 1:30–2:2'
  Browser @('select','.controls label:nth-child(1) select','2')|Out-Null
  Browser @('select','.controls label:nth-child(2) select','2')|Out-Null
  Has (Browser @('get','text','.friends-insights')) 'Maya (fictional)'
  Browser @('select','.controls label:nth-child(2) select','3')|Out-Null
  Has (Browser @('get','text','.friends-insights')) 'No followed fictional insights match'
  Browser @('select','aside > label select','bcbooks:1-ne')|Out-Null
  Browser @('select','.controls label:nth-child(2) select','2')|Out-Null
  Has (Browser @('get','text','.friends-insights')) '1-nephi 1:1–1:3'
  Has (Browser @('get','count','.friends-insights article')) '1'
  Browser @('select','aside > label select','bcbooks:gen')|Out-Null
  Browser @('eval','document.querySelector(".toolbar .actions button").click();null')|Out-Null
  Browser @('wait','--text','Insights are unavailable')|Out-Null
  Has (Browser @('get','text','.friends-insights')) 'Insights are unavailable'
  Browser @('focus','button[aria-controls=friends-insights-panel]')|Out-Null
  Browser @('press','Space')|Out-Null
  Has (Browser @('get','count','.friends-insights')) '0'
  Has (Browser @('eval','!window.__gets.includes("cg-notes-v1") && !window.__requests.some(x=>/social|insight|Synthetic.private.note/i.test(x))') ) 'true'
  Has (Browser @('eval','Storage.prototype.getItem=window.__origGet;window.fetch=window.__origFetch;localStorage.getItem("cg-notes-v1")===window.__noteBefore')) 'true'
  Browser @('reload')|Out-Null
  Has (Browser @('get','count','.friends-insights')) '0'
  Browser @('wait','--text','Synthetic private note - never shared')|Out-Null
  Write-Host 'Friends integration browser smoke passed; synthetic notes remained private and unchanged.'
} catch {try {Write-Host (Browser @('errors'));Write-Host (Browser @('snapshot','-i'))}catch{};throw} finally {try {Browser @('close')|Out-Null}catch{Write-Warning 'Isolated browser cleanup could not be verified.'}}
