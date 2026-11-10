$task=Get-ScheduledTask -TaskName 'WEEX_Supervised_Incident_Readonly_V6'
Write-Output ('LogonType=' + $task.Principal.LogonType)
Write-Output ('Enabled=' + $task.Settings.Enabled)
Write-Output ('State=' + $task.State)
