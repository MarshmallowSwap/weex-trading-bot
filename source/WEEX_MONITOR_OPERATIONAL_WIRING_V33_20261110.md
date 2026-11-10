# WEEX — V33: Monitor operational wiring audit
2026-11-10

## Actual source code findings
- Production S4U task runs weex_supervised_process_monitor_v6.py.
- Monitor tick ALREADY invokes the existing real recovery
  module weex_supervised_worker_recovery_process_v8.recover
  upon exact independently verified protected-entry incident.
- Tick also invokes exit_policy_v7.run_exit only if the independent
  operator one-shot exit permit is active and the exact-close
  proposal is independently verified.
- Emergency reduceOnly exit is not made contingent upon worker
  restart success. Unknown exit outcome is read back with the
  independent close readback module without repeating a POST.
- Monitor always writes OBSERVING_NOT_ARMED; no automatic
  READY_TO_RECOVER publication has been demonstrated.

## Test evidence
- New test_weex_monitor_operational_wiring_v33.py verifies:
  incident->prepare->restart->permit->exit sequence;
  deny dispatch without permit;
  emergency exit possible if worker restart fails;
  deny dispatch when proposal invalid;
  deny restart and exit on unverified exposure.
- New suite + regressions: 29/29 PASS (offline).
- Test scenarios use injected synthetic incident/exchange evidence:
  no external network and no grant on production.
- This confirms code-level orchestration, not an actual
  post-ACK live entry crash or verified production exit.

## Production final check
- STOPPED, integrity=[].
- One manual AINUSDT CROSS position, one conditional TP.
- 0 regular orders, 0 unresolved writes.
- S4U monitor and heartbeat live; no real worker durable UNKNOWN.
- No production one-shot exit authorization exists.
- WEEX API emergency headroom verified at final read.
- Release 9/10 NO_GO.
- No real exchange POST, no modify of manual AINUSDT or TP.

## Actual unresolved requirement
Do NOT duplicate an already wired executor. The missing capability
is independently tested operational promotion/readiness plus a
real protected crash pilot, exact scope exit permit and readback.
A manual CROSS position still makes a new pilot inadmissible.
No rewriting of the release-gate result or forced READY.
