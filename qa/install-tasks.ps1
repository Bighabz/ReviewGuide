# qa/install-tasks.ps1 - register the two scheduled tasks (Windows PS 5.1).
# Hardened for unattended, run-whether-logged-on-or-not operation. Run this
# ONCE, elevated is NOT required for per-user tasks; it PROMPTS for the account
# password (Get-Credential) and never puts it on a command line.
#
# Creates:
#   RG-QA-Run       daily 05:45  -> run.ps1 (the full audit)
#   RG-QA-Heartbeat daily 08:00  -> heartbeat-check.ps1 (dead-man switch)
# Both launch via hidden-launch.vbs so no console flashes and the child exit
# code propagates to Task Scheduler's LastTaskResult.

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$QaDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Vbs     = Join-Path $QaDir 'hidden-launch.vbs'
$RunPs   = Join-Path $QaDir 'run.ps1'
$BeatPs  = Join-Path $QaDir 'heartbeat-check.ps1'
$WScript = 'C:\Windows\System32\wscript.exe'

foreach ($p in @($Vbs, $RunPs, $BeatPs)) {
    if (-not (Test-Path $p)) { throw "missing required file: $p" }
}

# Preflight the task account's environment (interactive PATH is absent under
# the task account - these must be absolute and present).
$checks = @{
    'python'      = 'C:\Python313\python.exe'
    'powershell'  = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    'wscript'     = $WScript
    'wsl'         = 'C:\Windows\System32\wsl.exe'
}
foreach ($k in $checks.Keys) {
    if (-not (Test-Path $checks[$k])) { Write-Warning "preflight: $k not found at $($checks[$k])" }
}
# Verify the WSL distro + rgvenv the unit_suite backend command needs.
try {
    $venv = & 'C:\Windows\System32\wsl.exe' -d kali-linux -u root -- bash -c 'test -x /root/rgvenv/bin/python && echo OK || echo MISSING' 2>$null
    if ($venv -notmatch 'OK') { Write-Warning "preflight: WSL kali rgvenv not found under the task account" }
} catch { Write-Warning "preflight: could not query WSL ($_)" }

$cred = Get-Credential -Message 'Enter the Windows account to run the QA tasks (run-whether-logged-on-or-not).'

function New-QaTask($Name, $ScriptPath, $Hour, $Minute) {
    $action = New-ScheduledTaskAction -Execute $WScript -Argument ('"{0}" "{1}"' -f $Vbs, $ScriptPath) -WorkingDirectory $QaDir
    $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours($Hour).AddMinutes($Minute))
    $settings = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited -Force | Out-Null
    Write-Output "registered $Name ($Hour`:$('{0:D2}' -f $Minute))"
}

New-QaTask 'RG-QA-Run' $RunPs 5 45
New-QaTask 'RG-QA-Heartbeat' $BeatPs 8 0

Write-Output ''
Write-Output 'Done. Verify with:  Get-ScheduledTask -TaskName RG-QA-*'
Write-Output 'One-time first run: Start-ScheduledTask -TaskName RG-QA-Run ; then check (Get-ScheduledTaskInfo RG-QA-Run).LastTaskResult'
Write-Output 'NOTE: "Log on as a batch job" right + a non-expiring password are required for run-when-logged-off; if LastTaskResult is 0x41303 grant that right (secpol.msc) to the account.'
