# WEEX — Independent API-SIM supervisor -> real worker recovery V36
Date: 2026-11-10

## Objective and actual outcome
An independent Windows OS supervisor process recovered and closed
an exact protected ETHUSDT position on real WEEX API-SIM,
using production monitor tick() + production v8 recover() +
the actual weex_live_worker.py --supervised-crash-recovery CLI
with an explicitly SIM-only authenticated-evidence read adapter.

Final recovery result:
INDEPENDENT_SIM_SUPERVISOR_RECOVERY_EXIT_PASS.

## Incident chronology (important: initial failure preserved)
1. One-shot SIM protected ETH long ISOLATED 1x, quantity 0.002.
   ClientId wxpilot_crashsim_v36a01. Original child exited 73
   after SIM order POST, leaving durable ENTRY_OUTCOME_UNKNOWN.
   Independent parent authenticated GET found 1 exact filled entry,
   1 long position and 1 attached protected stop; no duplicates.
2. Initial independent supervisor subprocess failed BEFORE import
   because it used base Python interpreter without requests.
   The parent saved DEMO_INDEPENDENT_SUPERVISOR_REVIEW_REQUIRED;
   no close was attempted and the demo stop remained in place.
3. Corrected both supervisor and worker subprocess launch to use
   the WEEX virtual environment interpreter.
4. Executed the independent supervisor against THE SAME exact
   already-open SIM position and the existing durable incident
   manifest; did NOT open another entry.
5. The supervisor independently authenticated read the SIM
   position, order history and attached stop, verified identifiers,
   invoked the production monitor tick(), invoked the production
   v8 worker restart reservation and spawned the actual worker
   GET-only CLI. Production CLI's exchange read was injected
   from verified SIM evidence and quantity mapped from demo
   0.002 to scoped production recovery 0.001. This is an adapter,
   not proof of production live exchange readback.
6. Supervisor reserved a close intent in its separate on-disk
   directory BEFORE its single WEEX SIM post_capi_v3_closePositions.
   Received successful close ACK and independent SIM GET readback:
   0 positions, 0 regular orders, 0 conditional orders.
   CloseOrderId: 814981673581019338.
   Supervisor PID 21372; workerRestartConfirmed true.
7. Second invocation of the same supervisor root refused with
   PermissionError, productionPosts=0, without any retry.
8. 18/18 combined regression tests PASS.

## Production isolation
- Demo destination https://api-sim.weex.com only.
- SIM credentials WEEX_SIM_V3; no production auth imported by
  simulated supervisor SDK client.
- Actual production entry/exit POST count: 0.
- Production trading switch STOPPED, integrity clean,
  manual CROSS AINUSDT position + one conditional TP unchanged,
  0 regular orders, 0 unresolved writes.
- Production release gate 9/10 NO_GO.
- Production supervisor OBSERVING_NOT_ARMED, not promoted.

## Scope limitation
- This CERTIFIES independent-process supervision + true production
  worker CLI code path + SIM authenticated readback + SIM exit.
- This does NOT verify the production S4U scheduled task's
  behavior on a real post-ACK incident.
- Actual production reduceOnly post_capi_v3_order was NOT used:
  SIM used post_capi_v3_closePositions with exact positionId.
- One-shot exit authority was demo-scoped, not real operator permit.
- The worker recovery read was SIM-adapted, not an unmodified
  production Reader authenticated to live WEEX.
- Therefore NOT a live 10/10 and NOT permission for 100x CROSS.

## Artifacts
- weex_sim_independent_supervisor_v36.py
- weex_demo_independent_supervisor_trial_v36.py
- weex_demo_independent_supervisor_v36_manifest.json
- weex_demo_independent_supervisor_v36_result.json (initial failure)
- durable rescue evidence: C:\Users\guidi\AppData\Local\Temp\weex_v36_sim_independent_rescue_persistent\weex_sim_supervisor_v36_result.json
- weex_sim_supervisor_v36_rescue_run.py
- weex_independent_supervisor_replay_v35.py
- test_weex_independent_supervisor_replay_v35.py

## Next technical step
The process integration on real API-SIM is demonstrated.
Do NOT repeat the same offline/simulated milestone indefinitely.
Any production release next requires a separately permitted
true production cross-flat pilot, verified operational
S4U readiness + exact live reduceOnly exit transport and
unambiguous final flat readback. Current AINUSDT CROSS
exposure and missing operator permit block that.
