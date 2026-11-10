$ErrorActionPreference='Stop'
$name='WEEX_Recovery_Restart_Probe_V27'
$root='D:\FUNDSHOT\weex_alerts'
$script=Join-Path $root 'weex_sched_restart_probe_v27.py'
$state=Join-Path $root 'weex_sched_restart_probe_v27_state.json'
$python=Join-Path $root '.venv_weex_live\Scripts\python.exe'
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){
 Write-Output 'ISOLATED_PROBE_TASK_ALREADY_EXISTS_NO_REPLACE';exit 4
}
if(Test-Path -LiteralPath $state){Write-Output 'ISOLATED_PROBE_STATE_EXISTS_NO_OVERWRITE';exit 5}
$action=New-ScheduledTaskAction -Execute $python -Argument ('-B "'+$script+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5)
$settings=New-ScheduledTaskSettingsSet -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -MultipleInstances IgnoreNew
$username=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal=New-ScheduledTaskPrincipal -UserId $username -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Output 'REGISTERED_S4U_ISOLATED_PROBE'
Start-ScheduledTask -TaskName $name
Write-Output 'START_REQUESTED'
Get-ScheduledTaskInfo -TaskName $name | Select-Object LastRunTime,LastTaskResult,NextRunTime | ConvertTo-Json -Compress
