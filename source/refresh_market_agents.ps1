$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$python=(Get-Command python -ErrorAction Stop).Source
$livePython=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$log=Join-Path $root 'market_agents_refresh.log'
try{
 if(-not (Test-Path -LiteralPath $livePython)){throw 'WEEX SDK Python runtime missing'}
 $output=& $livePython -B (Join-Path $root 'weex_simple_bot.py') 2>&1
 if($LASTEXITCODE -ne 0){throw "read-only pretrade cycle failed"}
 $execution=& $livePython -B (Join-Path $root 'weex_execution_cycle.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'read-only execution cycle failed'}
 $output += $execution
 $telemetry=& $python (Join-Path $root "market_agent_telemetry.py") 2>&1
 if($LASTEXITCODE -ne 0){throw "telemetry failed"}
 $modules=& $python (Join-Path $root "module_health.py") 2>&1
 if($LASTEXITCODE -ne 0){throw "module health failed"}
 $output += $telemetry
 $output += $modules
 $shadow=& $python (Join-Path $root 'weex_agent_orchestrator.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'shadow orchestration failed'}
 $health=& $python (Join-Path $root 'agent_health.py') 2>&1
 if($LASTEXITCODE -ne 0){throw 'agent health failed'}
 $output += $shadow
 $output += $health
 $output | ForEach-Object { Add-Content -Path $log -Value "[$(Get-Date -Format o)] $_" }
}catch{
 Add-Content -Path $log -Value "[$(Get-Date -Format o)] ERROR $($_.Exception.Message)"
 exit 1
}
