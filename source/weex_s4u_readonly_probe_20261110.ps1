$ErrorActionPreference='Stop'
$root='D:\FUNDSHOT\weex_alerts'
$name='WEEX_S4U_Readonly_Probe_20261110'
$out=Join-Path $root 'weex_s4u_probe_executed_20261110.json'
$exe=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$script=Join-Path $root 'weex_s4u_readonly_probe_task_20261110.py'
if(Test-Path $out){Remove-Item $out -Force}
$action=New-ScheduledTaskAction -Execute $exe -Argument ('-B "'+$script+'"') -WorkingDirectory $root
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType S4U -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
$created=$false
try {
 Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
 $created=$true
 Write-Output 'S4U_REGISTER_PASS'
 Start-ScheduledTask -TaskName $name
 for($n=0;$n -lt 25 -and -not (Test-Path $out);$n++){Start-Sleep -Milliseconds 300}
 if(Test-Path $out){
  Write-Output 'S4U_EXECUTION_PASS'
  Get-Content $out
 }else{
  Write-Output 'S4U_EXECUTION_NOT_VERIFIED'
  Get-ScheduledTaskInfo -TaskName $name | Select-Object LastTaskResult,LastRunTime | Format-List
 }
} catch {
 Write-Output ('S4U_TEST_FAILED: '+$_.Exception.Message)
} finally {
 if($created) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false
  Write-Output 'TEMPORARY_TASK_REMOVED'
 }
}
