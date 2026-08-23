# qa/heartbeat-check.ps1 - dead-man switch (Windows PowerShell 5.1).
# Runs as a separate scheduled task ~08:00. If qa.heartbeats has no beat dated
# today, the loop did not run - alert. Silence is the worst failure mode.
#
# LIMITATION: same-box as run.ps1 - if beeep is off, neither this nor the run
# fires. The VPS migration (cron) removes that blind spot.

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$QaDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Python = 'C:\Python313\python.exe'
$env:PYTHONPATH = $QaDir
Set-Location $QaDir

if (Test-Path (Join-Path $QaDir 'DISABLED')) { exit 0 }

# qa.heartbeats.created_at is UTC; compare in UTC so an evening-local run
# (which stamps the next UTC day) does not trip a spurious dead-man alert.
$today = ((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd'))
$last = ''
try { $last = (& $Python -m lib.runctl last-beat 2>$null | Select-Object -First 1).Trim() } catch {}

if ($last -ne $today) {
    $msg = "DEAD-MAN: QA loop has not run today (last beat: $last, expected $today)."
    & $Python -m lib.notifyctl run_failed $msg 2>$null | Out-Null
    Write-Output $msg
    exit 1
}
Write-Output "OK: beat present for $today"
exit 0
