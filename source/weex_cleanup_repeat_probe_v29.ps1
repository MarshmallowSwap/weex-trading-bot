$ErrorActionPreference='Stop'
$name='WEEX_Recovery_Repeat_Probe_V29'
$t=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if($t){
 if($t.State -eq 'Running'){throw 'PROBE_STILL_RUNNING'}
 Unregister-ScheduledTask -TaskName $name -Confirm:$false
 Write-Output 'V29_TASK_REMOVED'
}
Write-Output ('V29_TASK_EXISTS=' + [bool](Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue))
