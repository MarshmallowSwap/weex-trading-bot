$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$python=(Get-Command python -ErrorAction Stop).Source
$log=Join-Path $root 'agent_watchdog.log'
try{
 & powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'run_autonomy_supervisor.ps1')
 if($LASTEXITCODE -ne 0){throw 'Autonomy supervisor failed'}
 $out=& $python (Join-Path $root 'agent_watchdog.py') 2>&1
 if($LASTEXITCODE -ne 0){throw "Agent watchdog returned failure"}
 $out | ForEach-Object {Add-Content $log "[$(Get-Date -Format o)] $_"}
}catch{
 Add-Content $log "[$(Get-Date -Format o)] ERROR $($_.Exception.Message)"
 exit 1
}

