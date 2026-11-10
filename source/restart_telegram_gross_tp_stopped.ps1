$ErrorActionPreference='Stop'
$root='D:\FUNDSHOT\weex_alerts'
$config=Get-Content -LiteralPath (Join-Path $root 'weex_ai_risk_config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($config.execution.enabled -ne $false -or $config.execution.mode -ne 'PRETRADE'){throw 'LIVE_EXECUTION_NOT_DISABLED'}
$py=Join-Path $root '.venv_weex_live\Scripts\python.exe'
$mode=& $py -c "import live_control;from pathlib import Path;print(live_control.state(Path.cwd())['mode'])"
if($LASTEXITCODE -ne 0 -or $mode -ne 'STOPPED'){throw 'LIVE_SWITCH_NOT_STOPPED'}
$script=Join-Path $root 'commands.py'
$processes=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$script*" })
$parent=@($processes | Where-Object { $_.ExecutablePath -like "*weex_alerts*.venv_weex_live*" })
if($parent.Count -ne 1){throw "EXPECTED_ONE_VENV_PARENT_ACTUAL_$($parent.Count)"}
$children=@($processes | Where-Object { $_.ParentProcessId -eq $parent[0].ProcessId })
if($children.Count -gt 1 -or $processes.Count -ne (1+$children.Count)){throw 'UNEXPECTED_TELEGRAM_PROCESSES'}
foreach($child in $children){Stop-Process -Id $child.ProcessId -Force -ErrorAction Stop}
Stop-Process -Id $parent[0].ProcessId -Force -ErrorAction Stop
Start-Sleep -Milliseconds 450
$existing=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$script*" })
if($existing.Count -ne 0){throw 'OLD_TELEGRAM_PROCESS_STILL_RUNNING'}
$venv=Join-Path $root '.venv_weex_live\Scripts\pythonw.exe'
$launch=Start-Process -FilePath $venv -ArgumentList @('-B',('"' + $script + '"')) -WorkingDirectory $root -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
$check=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$script*" })
if($check.Count -lt 1 -or $check.Count -gt 2){throw "RESTART_CHECK_FAILED_$($check.Count)"}
$mode2=& $py -c "import live_control;from pathlib import Path;print(live_control.state(Path.cwd())['mode'])"
if($mode2 -ne 'STOPPED'){throw 'UNEXPECTED_LIVE_STATE_CHANGE'}
Write-Output ("BOT_PROCESS_RESTARTED; launcherPid="+$launch.Id+"; processes="+$check.Count+"; live="+$mode2)
