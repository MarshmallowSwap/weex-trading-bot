$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$log=Join-Path $root 'integrated_position_audit.log'
$livePython=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$demoScript='C:\Users\guidi\Documents\Codex\2026-10-23\ho\work\demo_strategy_cycle.py'
$failed=$false
# Independent bounded demo recovery must run even if the production read-only audit fails.
try{
 $demo=& $livePython -B $demoScript tick 2>&1
 $demoExit=$LASTEXITCODE
 $demo | ForEach-Object {Add-Content $log "[$(Get-Date -Format o)] DEMO $_"}
 if($demoExit -ne 0){
  Add-Content $log "[$(Get-Date -Format o)] DEMO REVIEW REQUIRED (exit $demoExit); independent LIVE worker continues"
 }
}catch{
 Add-Content $log "[$(Get-Date -Format o)] DEMO ERROR $($_.Exception.Message); independent LIVE worker continues"
}
try{
 $python=(Get-Command python -ErrorAction Stop).Source
 $out=& $livePython -B (Join-Path $root 'position_manager_integrated.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'Position manager integrated audit failed'}
 $execution=& $livePython -B (Join-Path $root 'weex_execution_cycle.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'Read-only execution recovery failed'}
 $out += $execution
 $out | ForEach-Object {Add-Content $log "[$(Get-Date -Format o)] $_"}
}catch{
 Add-Content $log "[$(Get-Date -Format o)] ERROR $($_.Exception.Message)"
 $failed=$true
}
# User-controlled live worker. Its persistent switch defaults to STOPPED.
# Independent of legacy diagnostics: TP recovery still runs if an audit fails.
try{
 $liveCycle=& $livePython -B (Join-Path $root 'weex_live_worker.py') 2>&1
 $liveExit=$LASTEXITCODE
 $liveCycle | ForEach-Object {Add-Content $log "[$(Get-Date -Format o)] LIVE-CONTROL $_"}
 if($liveExit -ne 0){throw "Controlled worker requires review (exit $liveExit)"}
}catch{
 Add-Content $log "[$(Get-Date -Format o)] LIVE-CONTROL ERROR $($_.Exception.Message)"
 $failed=$true
}
if($failed){exit 1}
