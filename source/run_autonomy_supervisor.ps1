$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$python=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
$allowed=@('WEEX_AI_Market_Diagnostics')
$mutex=New-Object System.Threading.Mutex($false,'Local\WEEX_Pretrade_Supervisor')
$acquired=$false
try {
 try {$acquired=$mutex.WaitOne(0)} catch [System.Threading.AbandonedMutexException] {$acquired=$true}
 if(-not $acquired){exit 0}
 if(-not (Test-Path -LiteralPath $python)){throw 'Configured Python missing'}
 $tasks=@{}
 foreach($name in $allowed){
  $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  $tasks[$name]=if($task){[string]$task.State}else{'Missing'}
 }
 $commandPath=Join-Path $root 'commands.py'
 $escaped=[regex]::Escape($commandPath).Replace('\\','[\\/]')
 $pids=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object {
  $_.CommandLine -match ('(?i)(?:^|[\s\x22])'+$escaped+'(?:[\s\x22]|$)')
 } | ForEach-Object {$_.ProcessId})
 $monitorPath=Join-Path $root 'monitor.py'
 $monitorEscaped=[regex]::Escape($monitorPath).Replace('\\','[\\/]')
 $monitorPids=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object {
  $_.CommandLine -match ('(?i)(?:^|[\s\x22])'+$monitorEscaped+'(?:[\s\x22]|$)')
 } | ForEach-Object {$_.ProcessId})
 $inputPath=Join-Path $root 'weex_autonomy_snapshot.json'
 @{tasks=$tasks;telegramPids=$pids;monitorPids=$monitorPids;capturedAt=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $inputPath -Encoding utf8
 # Local read-only quality audits run independently of recovery planning.
 & $python -B (Join-Path $root 'weex_quality_auditors.py') | Out-Null
 if($LASTEXITCODE -ne 0){Write-Warning 'Quality audit unavailable; recovery supervision continues'}
 $raw=& $python -B (Join-Path $root 'weex_autonomy_supervisor.py') $inputPath
 if($LASTEXITCODE -ne 0){throw 'Supervisor planning failed'}
 $plan=$raw | ConvertFrom-Json
 $outcomes=@()
 foreach($action in $plan.actions){
  try {
   # Recheck mutable configuration immediately before each local recovery action.
   $cfg=Get-Content -LiteralPath (Join-Path $root 'weex_ai_risk_config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
   if($cfg.execution.enabled -ne $false -or $cfg.execution.mode -ne 'PRETRADE'){throw 'Configuration changed; recovery blocked'}
   if($action.kind -eq 'START_EXISTING_TASK' -and $allowed -contains $action.task){
    $task=Get-ScheduledTask -TaskName $action.task
    if($task.State -eq 'Ready'){Start-ScheduledTask -TaskName $action.task; $outcomes+=@{kind=$action.kind;task=$action.task;state='REQUESTED'}}
    else {$outcomes+=@{kind=$action.kind;task=$action.task;state='SKIPPED_NOT_READY'}}
   } elseif($action.kind -in @('START_TELEGRAM_PROCESS','START_MONITOR_PROCESS')){
    $launchPath=if($action.kind -eq 'START_MONITOR_PROCESS'){$monitorPath}else{$commandPath}
    $launchEscaped=if($action.kind -eq 'START_MONITOR_PROCESS'){$monitorEscaped}else{$escaped}
    $existing=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object {
     $_.CommandLine -match ('(?i)(?:^|[\s\x22])'+$launchEscaped+'(?:[\s\x22]|$)')
    })
    if($existing.Count -eq 0){
     $process=Start-Process -FilePath $python -ArgumentList @('-B',('"'+$launchPath+'"')) -WorkingDirectory $root -WindowStyle Hidden -PassThru
     $outcomes+=@{kind=$action.kind;pid=$process.Id;state='PROCESS_STARTED_NOT_YET_HEALTH_VERIFIED'}
    } else {$outcomes+=@{kind=$action.kind;state='SKIPPED_ALREADY_PRESENT'}}
   } else {throw 'Action outside recovery allowlist'}
  } catch {$outcomes+=@{kind=$action.kind;state='FAILED';error=$_.Exception.GetType().Name}}
 }
 $record=@{checkedAt=(Get-Date).ToUniversalTime().ToString('o');status=$plan.status;issues=$plan.issues;actions=$outcomes;telegramPidsBefore=$pids;ordersSubmitted=$false}
 $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'weex_autonomy_recovery_latest.json') -Encoding utf8
 if($outcomes.Count -gt 0){$record | ConvertTo-Json -Depth 6 -Compress | Add-Content -LiteralPath (Join-Path $root 'weex_autonomy_recovery_events.jsonl') -Encoding utf8}
 $record | ConvertTo-Json -Depth 6 -Compress
 if(@($outcomes | Where-Object {$_.state -eq 'FAILED'}).Count -gt 0){exit 1}
} finally {if($acquired){$mutex.ReleaseMutex()};$mutex.Dispose()}
