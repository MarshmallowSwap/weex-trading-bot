# WEEX — supervisory V6 delivery, 2026-11-09

## Executed on DESKTOP-HFC0ULG
- Installed `weex_independent_incident_supervisor_v6.py` as a separately callable read-only incident examiner.
- Installed `test_weex_independent_incident_supervisor_v6.py` with negative tests for pending UNKNOWN, stale exchange readbacks, mismatched position/stop, integrity failure, durable incident history and exceptions.
- Fixed Windows SQLite test handle cleanup and reran tests: **65/65 PASS**.
- Authenticated production account read: **0 positions, 0 open orders, 0 conditional orders**, no unresolved writes. Production STOPPED, code integrity clear.
- Independent release gate: **9/10 NO_GO**, missing `crash_restart_recovery_live_tested`.
- No live exchange order sent; no gate or strategy switch changed.

## V6 limits
- The supervisor maintains a durable local audit log but does **not** submit orders, close positions, cancel stops, authorize dispatch, or run as a permanently installed service.
- The source audit still identifies missing V5 worker integration, crash-and-restart live evidence, and autonomously safe exact-close orchestration.
- Existing 12/12 recorded API-SIM consistency checks do not prove the V5/V6 orchestrated crash path.
- A successful production crash exercise cannot be claimed without independently verified real exchange evidence and precise separate live-operation authorization.

## Safe invocation
```powershell
Set-Location D:\FUNDSHOT\weex_alerts
.\.venv_weex_live\Scripts\python.exe -B weex_independent_incident_supervisor_v6.py
.\.venv_weex_live\Scripts\python.exe -m unittest -q test_weex_independent_incident_supervisor_v6
.\.venv_weex_live\Scripts\python.exe -B weex_final_live_status_readonly_20261109.py
```

## Future release criteria
- Independent exact per-order permit and restart service, real code-path API-SIM crash exercise, verified exit-only implementation, independent limit checks, production integration with unchanged gate; then a separately authorized minimally exposed live pilot that satisfies the original certifier. Any uncertainty remains NO_GO.
