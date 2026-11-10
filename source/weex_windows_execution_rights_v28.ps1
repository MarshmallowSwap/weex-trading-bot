$ErrorActionPreference='Continue'
Write-Output ('USER='+[System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$p=[System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()
Write-Output ('IS_ADMIN='+$p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))
$policy=Get-ExecutionPolicy -List
Write-Output ('POLICY='+($policy|Out-String))
try { $svc=Get-Service -Name Schedule -ErrorAction Stop; Write-Output ('SCHEDULE_SERVICE='+$svc.Status) } catch { Write-Output ('SERVICE_ERR='+$_.Exception.GetType().Name) }
try { $task=Get-ScheduledTask -TaskName WEEX_Supervised_Incident_Noninteractive_V10 -ErrorAction Stop; Write-Output ('PRODUCTION_TASK_STATE='+$task.State); $info=Get-ScheduledTaskInfo -TaskName WEEX_Supervised_Incident_Noninteractive_V10; Write-Output ('PRODUCTION_TASK_RESULT=0x'+('{0:X8}' -f [uint32]$info.LastTaskResult)) } catch { Write-Output ('TASK_ERR='+$_.Exception.GetType().Name) }
