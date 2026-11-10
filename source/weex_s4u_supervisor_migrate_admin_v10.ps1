# Admin-only safe promotion of the real WEEX supervisor from InteractiveToken to S4U.
# Tests a separate S4U candidate before any change. Rollback restores original.
$ErrorActionPreference='Stop'
$root='D:\FUNDSHOT\weex_alerts'
$oldName='WEEX_Supervised_Incident_Readonly_V6'
$newName='WEEX_Supervised_Incident_Noninteractive_V10'
$probeName='WEEX_S4U_Supervisor_Candidate_20261110'
$exe=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$monitor=Join-Path $root 'weex_supervised_process_monitor_v6.py'
$candidate=Join-Path $root 'weex_s4u_supervisor_candidate_v10.py'
$probeJson=Join-Path $root 'weex_s4u_supervisor_candidate_v10.json'
$health=Join-Path $root 'weex_supervised_crash_supervisor_health.json'
$backup=Join-Path $root 'WEEX_Supervisor_Interactive_Task_PreS4U_20261110.xml'
$report=Join-Path $root 'weex_s4u_migration_result_v10.json'
$oldWasStopped=$false
$createdNew=$false
$oldEnabled=$false
$promoted=$false
$stage='INITIAL'
$beforePid=$null
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
function Write-Result([string]$s,[string]$detail) {
 $entry=[ordered]@{time=(Get-Date).ToString('o');status=$s;stage=$stage;detail=$detail;priorMonitorPid=$beforePid;promoted=$promoted}
 $entry|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 -Path $report
 Write-Output ($entry|ConvertTo-Json -Compress -Depth 5)
}
function Assert-Safe {
 $raw=& $exe -B (Join-Path $root 'weex_final_live_status_readonly_20261109.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'PRODUCTION_READONLY_STATUS_FAILED'}
 $s=($raw|Out-String|ConvertFrom-Json)
 if($s.mode -ne 'STOPPED' -or $s.positions -ne 0 -or $s.orders -ne 0 -or $s.conditional -ne 0 -or @($s.unresolvedWrites).Count -gt 0 -or @($s.integrity).Count -gt 0){throw 'PRODUCTION_ACCOUNT_OR_INTEGRITY_UNSAFE'}
 if($s.gate -ne 'NO_GO'){throw 'UNEXPECTED_RELEASE_GATE'}
}
function Read-Heartbeat {
 if(-not (Test-Path $health)){return $null}
 try{return (Get-Content -LiteralPath $health -Raw|ConvertFrom-Json)}catch{return $null}
}
function Same-ReadOnlyHeartbeat($h) {
 return ($null -ne $h -and $h.status -eq 'OBSERVING_NOT_ARMED' -and
     $h.releaseCertified -eq $false -and $h.entryDispatchAllowed -eq $false -and
     $h.closeDispatchAllowed -eq $false -and
     $h.supportsExactReduceOnlyClose -eq $false -and
     $h.hasIndependentRestartTask -eq $false)
}
function Restore-Old {
 if($createdNew) {
  try{Stop-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue}catch{}
  try{Disable-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue|Out-Null}catch{}
  try{Unregister-ScheduledTask -TaskName $newName -Confirm:$false -ErrorAction Stop}catch{}
 }
 if($oldWasStopped) {
  try{Enable-ScheduledTask -TaskName $oldName -ErrorAction Stop|Out-Null}catch{}
  try{Start-ScheduledTask -TaskName $oldName -ErrorAction Stop}catch{}
 }
}
try {
 $stage='ADMIN_PRIVILEGES'
 $admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
 if(-not $admin){throw 'RUN_POWERSHELL_AS_ADMINISTRATOR'}
 if(-not (Test-Path $exe) -or -not (Test-Path $monitor)){throw 'PYTHON_OR_MONITOR_NOT_FOUND'}
 $stage='PRODUCTION_PRECHECK';Assert-Safe
 if(Get-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue){throw 'NONINTERACTIVE_TASK_ALREADY_EXISTS_REVIEW_MANUALLY'}
 $old=Get-ScheduledTask -TaskName $oldName -ErrorAction Stop
 if($old.Principal.LogonType -ne 'Interactive'){throw 'ORIGINAL_TASK_NOT_INTERACTIVE'}
 $oldEnabled=$old.Settings.Enabled
 if(-not $oldEnabled){throw 'ORIGINAL_TASK_DISABLED'}
 $h=Read-Heartbeat
 if(-not (Same-ReadOnlyHeartbeat $h)){throw 'ORIGINAL_MONITOR_NOT_DISARMED'}
 $beforePid=[int]$h.pid
 $stage='BACKUP';Export-ScheduledTask -TaskName $oldName|Set-Content -Path $backup -Encoding Unicode
 $principal=New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
 $probeAction=New-ScheduledTaskAction -Execute $exe -Argument ('-B "'+$candidate+'"') -WorkingDirectory $root
 $probeSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
 $stage='S4U_CANDIDATE_REGISTER'
 if(Test-Path $probeJson){Remove-Item $probeJson -Force}
 Register-ScheduledTask -TaskName $probeName -Action $probeAction -Principal $principal -Settings $probeSettings -Force|Out-Null
 try {
  $stage='S4U_CANDIDATE_TEST'
  Start-ScheduledTask -TaskName $probeName
  $candidateProof=$null
  for($n=0;$n -lt 75;$n++){
   Start-Sleep -Seconds 1
   if(Test-Path $probeJson) {
    try{$candidateProof=Get-Content $probeJson -Raw|ConvertFrom-Json}catch{}
    if($candidateProof){break}
   }
  }
  if(-not $candidateProof -or $candidateProof.status -ne 'S4U_CANDIDATE_PASS' -or
    $candidateProof.accountFlat -ne $true -or
    $candidateProof.lifecycleReadable -ne $true -or
    $candidateProof.isolatedMonitorTickPass -ne $true){throw 'S4U_CANDIDATE_NOT_VERIFIED'}
 } finally {
  try{Unregister-ScheduledTask -TaskName $probeName -Confirm:$false -ErrorAction Stop}catch{}
 }
 $stage='PRODUCTION_RECHECK';Assert-Safe
 $action=New-ScheduledTaskAction -Execute $exe -Argument ('-B "'+$monitor+'" --loop --interval 3') -WorkingDirectory $root
 $trigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 1)
 $settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 3)
 $stage='REGISTER_NEW_DISABLED'
 Register-ScheduledTask -TaskName $newName -Action $action -Principal $principal -Trigger $trigger -Settings $settings -Force|Out-Null
 $createdNew=$true
 Disable-ScheduledTask -TaskName $newName|Out-Null
 $task=Get-ScheduledTask -TaskName $newName
 if($task.Principal.LogonType -ne 'S4U'){throw 'S4U_TASK_LOGON_TYPE_NOT_CONFIRMED'}
 $stage='SWITCH_MONITOR'
 Stop-ScheduledTask -TaskName $oldName
 $oldWasStopped=$true
 Disable-ScheduledTask -TaskName $oldName|Out-Null
 for($n=0;$n -lt 15;$n++){
  if(-not (Get-Process -Id $beforePid -ErrorAction SilentlyContinue)){break}
  Start-Sleep -Seconds 1
 }
 if(Get-Process -Id $beforePid -ErrorAction SilentlyContinue){throw 'OLD_MONITOR_STILL_RUNNING_ROLLBACK'}
 Enable-ScheduledTask -TaskName $newName|Out-Null
 Start-ScheduledTask -TaskName $newName
 $stage='VERIFY_HEARTBEAT'
 $newPid=$null;$firstEpoch=0;$lastEpoch=0
 for($n=0;$n -lt 45;$n++){
  Start-Sleep -Seconds 1
  $h=Read-Heartbeat
  if(-not (Same-ReadOnlyHeartbeat $h) -or [int]$h.pid -eq $beforePid){continue}
  $candidatePid=[int]$h.pid
  if(-not (Get-Process -Id $candidatePid -ErrorAction SilentlyContinue)){continue}
  $age=([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())-[double]$h.heartbeatEpoch
  if($age -lt 0 -or $age -gt 7){continue}
  if($newPid -and $candidatePid -eq $newPid -and [double]$h.heartbeatEpoch -gt $firstEpoch) {
   $lastEpoch=[double]$h.heartbeatEpoch;break
  }
  $newPid=$candidatePid;$firstEpoch=[double]$h.heartbeatEpoch
 }
 if(-not $newPid -or $lastEpoch -le $firstEpoch){throw 'NEW_NONINTERACTIVE_HEARTBEAT_UNVERIFIED'}
 $stage='FINAL_READONLY_CHECK';Assert-Safe
 $promoted=$true
 $stage='PROMOTED'
 Write-Result 'NONINTERACTIVE_MONITOR_PROMOTED' ('newPid='+$newPid+'; heartbeatAdvanced=true; oldTaskDisabled=true; candidateAuthenticatedReadback=true; entryWrites=0')
} catch {
 Write-Result 'PROMOTION_FAILED_ROLLBACK' ($_.Exception.Message)
 Restore-Old
 Write-Output 'INTERACTIVE_MONITOR_ROLLBACK_REQUESTED'
 exit 2
}
