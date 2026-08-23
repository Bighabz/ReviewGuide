# qa/run.ps1 - the single supervised entrypoint (Windows PowerShell 5.1).
# Runs the runners sequentially with per-runner timeouts, aborts prod runners
# on a containment breach, writes a SUMMARY, and notifies. No secrets on the
# command line (runners read qa/.env themselves).

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$QaDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Python = 'C:\Python313\python.exe'
$env:PYTHONPATH = $QaDir
Set-Location $QaDir

# 1. Kill-switch.
if (Test-Path (Join-Path $QaDir 'DISABLED')) {
    Write-Output 'qa/DISABLED present - exiting 0 (kill-switch).'
    exit 0
}

# 2. Run id + artifacts dir.
$RunId = 'run-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$RunDir = Join-Path $QaDir ("runs\" + $RunId)
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Invoke-Py([string]$Name, [string[]]$ArgList, [int]$TimeoutSec) {
    $out = Join-Path $RunDir ("{0}.out" -f $Name)
    $err = Join-Path $RunDir ("{0}.err" -f $Name)
    $p = Start-Process -FilePath $Python -ArgumentList $ArgList -WorkingDirectory $QaDir `
        -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
    try {
        $p | Wait-Process -Timeout $TimeoutSec -ErrorAction Stop
    } catch {
        try { Stop-Process -Id $p.Id -Force } catch {}
        return 124
    }
    return $p.ExitCode
}

function Ctl([string[]]$ArgList) {
    try { & $Python @ArgList 2>$null | Out-Null } catch {}
}

# 3. start_run + first heartbeat (best-effort - never fail the run on store I/O).
Ctl @('-m','lib.runctl','start','--run-id',$RunId,'--host',$env:COMPUTERNAME)
Ctl @('-m','lib.runctl','beat','--run-id',$RunId)

$Timeout = 900
$order = @('unit_suite','deps_audit','api_suite','browser_qa','lighthouse','data_integrity')
$prodRunners = @('api_suite','browser_qa','lighthouse','data_integrity')
$results = @{}
$breached = $false

foreach ($runner in $order) {
    if ($breached -and ($prodRunners -contains $runner)) {
        $results[$runner] = 'SKIPPED(breach)'
        continue
    }
    $rc = Invoke-Py $runner @('-m',"runners.$runner",'--run-id',$RunId,'--artifacts-dir',$RunDir) $Timeout
    $results[$runner] = $rc
    Ctl @('-m','lib.runctl','beat','--run-id',$RunId)
    if ($runner -eq 'api_suite' -and $rc -eq 3) {
        $breached = $true
        & $Python -m lib.notifyctl breach "CONTAINMENT BREACH in api_suite (run $RunId) - prod runners aborted." 2>$null | Out-Null
    }
}

# 4. Aggregate findings by severity from the runner artifacts.
$counts = @{ high = 0; medium = 0; low = 0; info = 0 }
Get-ChildItem -Path $RunDir -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -eq 'qa-writes-manifest.json' -or $_.Name -eq 'playwright-report.json') { return }
    try {
        $doc = Get-Content $_.FullName -Raw | ConvertFrom-Json
        foreach ($f in @($doc.findings)) {
            if ($f.severity -and $counts.ContainsKey($f.severity)) { $counts[$f.severity]++ }
        }
    } catch {}
}

# 5. SUMMARY.txt (UTF-8).
$summary = @()
$summary += "run: $RunId"
$summary += "breached: $breached"
$summary += "findings: high=$($counts.high) medium=$($counts.medium) low=$($counts.low) info=$($counts.info)"
$summary += 'runners:'
foreach ($runner in $order) { $summary += ("  {0}: {1}" -f $runner, $results[$runner]) }
$summaryPath = Join-Path $RunDir 'SUMMARY.txt'
$summary -join "`n" | Out-File -FilePath $summaryPath -Encoding utf8

# 6. finish_run + notify.
$countsJson = ($counts | ConvertTo-Json -Compress)
Ctl @('-m','lib.runctl','finish','--run-id',$RunId,'--counts',$countsJson)

$crashed = $false
foreach ($runner in $order) { if ($results[$runner] -eq 2 -or $results[$runner] -eq 124) { $crashed = $true } }
if ($breached -or $crashed) {
    $kind = 'run_failed'
    $msg = "QA run $RunId FAILED (breach=$breached crash=$crashed). high=$($counts.high) med=$($counts.medium)."
} else {
    $kind = 'run_complete'
    $msg = "QA run $RunId OK. high=$($counts.high) med=$($counts.medium) low=$($counts.low)."
}
& $Python -m lib.notifyctl $kind $msg 2>$null | Out-Null

# 7. Retention: prune run dirs older than retention_days (default 30).
try {
    $cfg = Get-Content (Join-Path $QaDir 'config.json') -Raw | ConvertFrom-Json
    $days = if ($cfg.retention_days) { [int]$cfg.retention_days } else { 30 }
} catch { $days = 30 }
$cutoff = (Get-Date).AddDays(-$days)
Get-ChildItem -Path (Join-Path $QaDir 'runs') -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Output $summaryPath
if ($breached -or $crashed) { exit 1 } else { exit 0 }
