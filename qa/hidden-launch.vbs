' hidden-launch.vbs - run a PowerShell script fully hidden and PROPAGATE its
' exit code (a bare -WindowStyle Hidden still flashes a console; wscript 0 does
' not). Arg 0 = absolute path to the .ps1 to run. Used by the scheduled tasks
' so Task Scheduler sees the real LastTaskResult.
Set shell = CreateObject("WScript.Shell")
scriptPath = WScript.Arguments(0)
cmd = """C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -ExecutionPolicy Bypass -File """ & scriptPath & """"
WScript.Quit shell.Run(cmd, 0, True)
