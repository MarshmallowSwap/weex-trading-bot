$ErrorActionPreference='Stop'
$n='WEEX_Restart_Interactive_Probe_V28'
$t=Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
if($t){
 if($t.State -eq 'Running'){ throw 'PROBE_RUNNING_REFUSE_CLEANUP' }
 Unregister-ScheduledTask -TaskName $n -Confirm:$false
 Write-Output 'ISOLATED_TEST_TASK_REMOVED'
}else{Write-Output 'ISOLATED_TEST_TASK_NOT_PRESENT'}
Write-Output ('PROBE_REMAINING=' + [bool](Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue))
