$ErrorActionPreference='Stop'
$name='WEEX_Restart_Interactive_Probe_V28'
$root='D:\FUNDSHOT\weex_alerts'
$state=Join-Path $root 'weex_sched_restart_probe_v27_state.json'
if(Test-Path -LiteralPath $state){throw 'EXISTING_PROBE_STATE_REFUSED'}
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'EXISTING_TASK_REFUSED'}
$python=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$action=New-ScheduledTaskAction -Execute $python -Argument ('-B "'+(Join-Path $root 'weex_sched_restart_probe_v27.py')+'"') -WorkingDirectory $root
$settings=New-ScheduledTaskSettingsSet -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15)
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Output 'INTERACTIVE_PROBE_REGISTERED'
Start-ScheduledTask -TaskName $name
Write-Output 'INTERACTIVE_PROBE_STARTED'
Get-ScheduledTaskInfo -TaskName $name | Select-Object LastRunTime,LastTaskResult,NextRunTime | ConvertTo-Json -Compress
