$ErrorActionPreference='Continue'
Set-Location 'D:\FUNDSHOT\weex_alerts'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_live_worker.py' --supervised-crash-recovery
Write-Output ('WORKER_RECOVERY_EXIT_CODE=' + $LASTEXITCODE)
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_supervised_worker_recovery_process_v8.py'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_production_worker_certification_readiness_20261110.py'
