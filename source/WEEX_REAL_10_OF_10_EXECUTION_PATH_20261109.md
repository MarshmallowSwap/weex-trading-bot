# WEEX — percorso verificabile verso 10/10 (2026-11-09)

## Verifiche realmente completate
- Official WEEX API-SIM `https://api-sim.weex.com` supports futures API calls.
- Saved SIM pilot run2 records one ETH protected entry, linked active stop, one reduce-only close, cancelled stop, and empty account.
- Separate SIM audit run2 records matched exchange order IDs and closing fills, no demo writes during audit.
- `weex_sim_independent_proof_consistency_20261109.py`: 12/12 recorded-proof consistency checks PASS. This is NOT a fresh exchange query and NOT production certification.
- Standalone double OS-crash drill: PASS offline; 58 regression tests PASS.
- Latest authenticated production read: zero open positions, regular orders and conditional orders; production STOPPED.
- Independent live gate remains 9/10 NO_GO; `crash_restart_recovery_live_tested` is missing.

## Remaining blockers (actual source audit)
1. The production `weex_live_worker.py` does not invoke the supervised V5 crash-child path.
2. The V4 independent watchdog cannot close; the V5 restart demonstration uses simulated acceptances, not real exchange responses.
3. Exact close requires a separate external approval whose transport/identity and durable consumption are not fully orchestrated.
4. Real crash evidence is absent. It must be independently assembled from worker exit provenance, durable UNKNOWN before ACK, real order + fill + linked stop, exact close, canceled stop and empty account.
5. No valid procedure should issue a risky 100x CROSS real test until all prerequisites and independent supervision have passed.

## Required sequence — no shortcuts
**A. Engineering (offline)**
- Build separate supervisor process with authenticated external approval tied to immutable client ID, hash, symbol, notional, leverage and expiry.
- Worker must acquire supervisor readiness via live IPC/heartbeat, then persist a single UNKNOWN intent before exact network POST. Never retry uncertain POSTs.
- Supervisor must use authenticated fresh readbacks, identify exact order/position/stop and prevent any unrelated trading.
- Separate close-only executor must require fresh immutable position/stop proof and external exact close authorization; durable UNKNOWN close before one reduceOnly POST, followed by independent readback. A failure keeps trading disabled and alerts for manual intervention.
- Add restart service with bounded retries, a durable incident ID, stale-state rejection and API budget partition reserved for risk reduction. Test crash between write reservation, HTTP send, response and journal commit; also crash the supervisor.
- Run fuzz/negative tests for stale approvals, account-not-flat, duplicate client ID, stale heartbeat, mismatched fills, missing stop, ambiguous order status, exhausted API budget, timeout and wrong account configuration. Require zero unexpected exchange POSTs.

**B. Exchange simulation**
- Fresh API-SIM trial with the **same final code paths** as the intended live pilot, no production credentials for writes.
- Verify linked stop and exact reduceOnly order details and fills, restart after entry ACK, supervisor crash/restart, stop cancellation, and independently verified flat account. Preserve raw sanitized exchange provenance.
- Do not treat existing API-SIM run2 as proof of the new V5 orchestration.

**C. Production pilot — only after separate exact-operation authorization and independent GO**
- Prefer an isolated, lowest-permitted leverage/minimum-size pilot instead of CROSS 100x to minimize collateral exposure, or redesign the certification to test safer behavior without falsely claiming the 100x policy.
- Independently verify actual account config, min order, sufficient exit-only API budget, native stop mechanics, and supervisor running on a separate process with reliable restart.
- One real protected entry. Crash worker deliberately after exchange ACK, verify durable UNKNOWN and *no entry retry*, independently reconcile on WEEX.
- Close only the proven exact position with reduceOnly after fresh external authorization; verify fills, stop closed/canceled and zero positions, orders or conditional orders.
- Run existing `weex_real_worker_crash_evidence_gate.py` unchanged. Promote to GO only when the legitimate checker and normal release gate independently pass. Otherwise retain STOPPED, NO_GO.

## Stop conditions
- Never substitute static JSON, simulated fills or manually edited attestation for actual real exchange evidence.
- Any ambiguous close/entry/stop state blocks automation and requires independently observed exchange readback.
- A requested 10/10 is an objective, not evidence or authorization to bypass safety checks.

## Repeatable safe inspection
```powershell
Set-Location D:\FUNDSHOT\weex_alerts
.\.venv_weex_live\Scripts\python.exe -B weex_sim_independent_proof_consistency_20261109.py
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_v5_safety_audit_20261109.py
.\.venv_weex_live\Scripts\python.exe -B weex_final_live_status_readonly_20261109.py
```
