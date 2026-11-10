$ErrorActionPreference='Continue'
Set-Location 'D:\FUNDSHOT\weex_alerts'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_reattest_supervised_worker_offline_20261109.py'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_live_worker.py' --supervised-crash-recovery
Write-Output ('WORKER_RECOVERY_EXIT_CODE=' + $LASTEXITCODE)
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_supervised_worker_recovery_process_v8.py'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_final_live_status_readonly_20261109.py'
