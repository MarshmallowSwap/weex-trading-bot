$ErrorActionPreference='Stop'
$name='WEEX_Recovery_Repeat_Probe_V29'
$root='D:\FUNDSHOT\weex_alerts'
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'TASK_EXISTS'}
if(Test-Path (Join-Path $root 'weex_sched_repeat_probe_v29_state.json')){throw 'STATE_EXISTS'}
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$action=New-ScheduledTaskAction -Execute (Join-Path $root '.venv_weex_live\Scripts\python.exe') -Argument ('-B "'+(Join-Path $root 'weex_sched_repeat_probe_v29.py')+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(8) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Minutes 4)
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Output 'V29_REPEAT_TASK_REGISTERED'
Get-ScheduledTask -TaskName $name | Select-Object TaskName,State | ConvertTo-Json -Compress
Get-ScheduledTaskInfo -TaskName $name | Select-Object LastRunTime,LastTaskResult,NextRunTime | ConvertTo-Json -Compress
