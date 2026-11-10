$ErrorActionPreference='Continue'
$task='WEEX_Supervised_Incident_Noninteractive_V10'
$log='Microsoft-Windows-TaskScheduler/Operational'
$meta=Get-WinEvent -ListLog $log -ErrorAction SilentlyContinue
Write-Output ('OPERATIONAL_LOG_ENABLED='+[string]$meta.IsEnabled)
$events=@(Get-WinEvent -FilterHashtable @{LogName=$log;StartTime=(Get-Date).AddDays(-2)} -MaxEvents 2500 -ErrorAction SilentlyContinue | Where-Object {$_.Message -like ('*'+$task+'*') } | Select-Object -First 40)
Write-Output ('TASK_EVENTS_FOUND='+$events.Count)
$events | Select-Object TimeCreated,Id,LevelDisplayName,@{Name='MessageText';Expression={($_.Message -replace '[\r\n]+',' ').Substring(0,[Math]::Min(200,($_.Message -replace '[\r\n]+',' ').Length))}} | ConvertTo-Json -Compress
$info=Get-ScheduledTaskInfo -TaskName $task -ErrorAction SilentlyContinue
Write-Output ('TASK_LAST_RESULT='+[string]$info.LastTaskResult)
Write-Output ('TASK_LAST_RUN='+[string]$info.LastRunTime)
Write-Output ('TASK_NEXT_RUN='+[string]$info.NextRunTime)
$probe=Get-ScheduledTask -TaskName WEEX_Recovery_Restart_Probe_V27 -ErrorAction SilentlyContinue
Write-Output ('ISOLATED_PROBE_REGISTERED='+[bool]$probe)
