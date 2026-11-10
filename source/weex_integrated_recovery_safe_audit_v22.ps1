$ErrorActionPreference='Continue'
Set-Location 'D:\FUNDSHOT\weex_alerts'
& '.\.venv_weex_live\Scripts\python.exe' -m unittest -q test_weex_supervised_worker_recovery_process_v8 test_weex_supervised_process_monitor_v6 test_weex_independent_incident_supervisor_v6 test_weex_supervised_real_recovery_v3 test_weex_supervised_exit_policy_v7 test_weex_supervised_exact_close_readback_v6 test_weex_real_worker_crash_evidence_gate test_weex_supervisor_promotion_policy_v16 test_weex_exact_crash_trial_admission_v15
Write-Output ('UNIT_TEST_EXIT='+$LASTEXITCODE)
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_live_worker.py' --supervised-crash-recovery
Write-Output ('TRUE_WORKER_RECOVERY_EXIT='+$LASTEXITCODE)
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_supervised_worker_recovery_process_v8.py'
& '.\.venv_weex_live\Scripts\python.exe' -B 'weex_final_live_status_readonly_20261109.py'
