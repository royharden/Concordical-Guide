param([Parameter(Mandatory=$true)][string]$Url)
$ErrorActionPreference='Stop'
$session='cg-notes-download-'+[guid]::NewGuid().ToString('N')
$outputFile=Join-Path $env:TEMP ($session+'.json')
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
try {
  Browser @('open',$Url)|Out-Null
  Browser @('fill','.notes form textarea','Synthetic download verification only')|Out-Null
  Browser @('click','.notes button[type=submit]')|Out-Null
  Browser @('wait','--text','Note saved on this device.')|Out-Null
  Browser @('eval','document.querySelector(".note-actions button").click();null')|Out-Null
  Browser @('wait','--text','Backup ready.')|Out-Null
  Browser @('download','.notes a[download]',$outputFile)|Out-Null
  if(-not (Test-Path -LiteralPath $outputFile -PathType Leaf)){throw 'Download command returned but the synthetic output file was not found.'}
  $doc=Get-Content -LiteralPath $outputFile -Raw -Encoding utf8 | ConvertFrom-Json
  if($doc.version -ne 1 -or $doc.notes.Count -ne 1 -or $doc.notes[0].text -ne 'Synthetic download verification only' -or $doc.notes[0].book -ne 'bcbooks:gen' -or $doc.notes[0].chapter -ne 1 -or $doc.notes[0].start -ne 1 -or $doc.notes[0].end -ne 1){throw 'Synthetic backup content or anchor did not match.'}
  Write-Host 'Synthetic JSON download verified: one Genesis 1:1 note, version 1.'
} finally {
  try {Browser @('close')|Out-Null}catch{Write-Warning 'Isolated browser cleanup could not be verified.'}
  if(Test-Path -LiteralPath $outputFile -PathType Leaf){Remove-Item -LiteralPath $outputFile}
}
