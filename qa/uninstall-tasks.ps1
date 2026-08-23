# qa/uninstall-tasks.ps1 - remove the QA scheduled tasks (idempotent).
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
foreach ($name in @('RG-QA-Run', 'RG-QA-Heartbeat')) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Output "removed $name"
    } else {
        Write-Output "$name not present"
    }
}
