# WEEX — Windows task recovery probe V28 — 2026-11-10

## Account and permissions
- Current Windows user DESKTOP-HFC0ULG\guidi, not elevated (IS_ADMIN=False).
- Schedule service RUNNING. Production S4U task RUNNING, unchanged.
- S4U isolated probe registration in V27 failed AccessDenied (0x80070005).
- Separate INTERACTIVE limited-user task WEEX_Restart_Interactive_Probe_V28 successfully created without privilege elevation.

## Actual scheduler test V28
- Task configured RestartOnFailure Count=2, Interval=PT1M,
  with non-repeating trigger in future, started manually once.
- Test program does no network, WEEX imports, or trading.
- First launch recorded 2026-11-10T09:46:44.573029Z, PID=24372;
  deliberate exit code 23. Scheduler LastTaskResult=23.
- A 100-second subsequent observation recorded no second run.
- Separate later task read at 2026-11-10 10:49:16+01:00
  still LastTaskResult=23, same LastRunTime.
- Thus RestartOnFailure in this isolated on-demand interactive
  scenario did NOT produce a certified automatic restart.
  This does not prove that the production S4U task cannot
  restart, but its behavior is NOT ATTESTED.
- Isolated task unregistered successfully after the test.
  PROBE_REMAINING=False.

## Risk and exit scope
- 11/11 tests PASS for offline exit path, OS restart
  logic and CROSS exposure veto. No production permit.
- Independent recovery capability verified with real S4U heartbeat,
  reduceOnly SDK preview and sufficient API headroom, but
  EXIT permit absent and no real post-ACK UNKNOWN worker journal.
- Real account: AINUSDT manual CROSS position + one conditional TP,
  no regular order, no unresolved writes. CROSS occupied, no
  authorized crash test entry. No modification to this position.

## Final verification
- STOPPED, integrity clean, live release NO_GO 9/10.
- Prearm OPERATIONAL_PREARM_BLOCKED:
  INDEPENDENT_ONE_SHOT_EXIT_PERMIT_REQUIRED,
  SHARED_CROSS_COLLATERAL_OCCUPIED,
  INDEPENDENT_PROCESS_RESTART_AND_EXIT_DRILL_NOT_ATTESTED.
- API budget 328/490 remaining; preflight and recovery budget fit.
- No new WEEX entry, close, TP change or leverage change.

## Necessary next step
- From elevated Windows session, configure/verify genuine
  independent task restart with auditable TaskScheduler operational
  events (preserve existing production monitor), rather than
  assuming configuration equals functionality.
- Real reduceOnly close readback only after explicit scoped
  operator permit, real protected trial position and account
  compatibility checks; current AINUSDT prevents new CROSS pilot.
- Maintain 9/10 NO_GO until real crash/recovery/exit evidence exists.
