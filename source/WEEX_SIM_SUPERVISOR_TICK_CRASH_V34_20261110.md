# WEEX — API-SIM monitor-driven crash and close V34
Date: 2026-11-10

## Actual exchange-sim transaction
- Brand-new one-shot demo client ID wxpilot_crashsim_v34a01.
- Destination strictly https://api-sim.weex.com.
- SIM ISOLATED 1x, source code validates empty SIM account
  before the entry and protective SL.
- One demo ETH long protected entry POST; child exited 73
  directly after successful POST before durable ACK.
- Independent SIM account/history readback found exactly
  one entry, one position and one attached stop.
- Real production monitor tick() dispatched the independent
  demo close callback under a DEMO-ONLY injected permission
  and its own temporary state root, not production permissions.
- Exactly one demo closePositions POST; independent GETs
  confirmed zero positions, zero regular orders, zero stops.
- Result: DEMO_SUPERVISOR_TICK_EXIT_PASS.
- No entry retry, no stop-cancellation POST.
- Reinvocation returned ONE_SHOT_RESERVED with no new POST.
- Follow-up regressions: 11/11 PASS.

## Important limits and correct terminology
- True weex_supervised_process_monitor_v6.tick orchestration
  was exercised using demo-specific callbacks.
- The demo child is NOT the real production weex_live_worker.py
  recovery process; workerRestartConfirmed=False is recorded.
- The demo close used WEEX SIM post_capi_v3_closePositions,
  NOT production post_capi_v3_order reduceOnly. Do not certify
  the production reduceOnly endpoint from this demo.
- Permission was injected ONLY inside the temporary SIM test,
  not issued through production exit_policy_v7.
- No real production S4U readiness published;
  monitorStatus=OBSERVING_NOT_ARMED.
- No live 10/10 certification and no real-account close.

## Production check after trial
- STOPPED, integrity [], main trading not armed.
- One manual AINUSDT CROSS position and one attached
  conditional order unchanged.
- 0 regular orders, 0 unresolvedWrites.
- 9/10 NO_GO: crash_restart_recovery_live_tested still absent.

## Files
- weex_demo_supervisor_bridge_v34.py (one-shot)
- weex_demo_supervisor_bridge_v34_result.json (proof)
- weex_demo_supervisor_crash_child_v34.py (demo child)
- weex_demo_supervisor_child_v34_state.json
- weex_build_demo_supervisor_bridge_v34.py (source adaptation)

## Next engineering threshold
1. An isolated SIM supervisor process (not only a tick invoked
   inside the parent) must be shown to detect the crash and
   start a real worker's GET-only readback branch, with
   a SIM-safe alternate Reader and durable one-shot reservation.
2. Actual production exact reduceOnly close authority remains
   subject to independent operator permit and fresh proof.
3. Real CROSS AINUSDT exposure and release NO_GO cannot be
   bypassed for any 100x test.
