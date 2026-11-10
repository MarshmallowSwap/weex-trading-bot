# WEEX — Windows task restart and protected exit audit V27
2026-11-10 | Read-only operational audit

## Existing production state
- Main bot STOPPED, integrity clean, 1 CROSS manual AINUSDT position,
  1 conditional TP, 0 regular orders; release 9/10 NO_GO.
- Existing Windows scheduled task:
  WEEX_Supervised_Incident_Noninteractive_V10, S4U,
  Arguments python -B weex_supervised_process_monitor_v6.py --loop --interval 3,
  RestartOnFailure Count=3 Interval=PT1M,
  repetition interval PT1M, MultipleInstancesPolicy=IgnoreNew.
- Task Scheduler Operational event log ENABLED=False,
  no queryable task events. Cannot claim that a real task restart has
  ever happened from current Scheduler evidence.
- Scheduler LastTaskResult 0x800710E0 (request refused);
  consistent with IgnoreNew on overlapping launches,
  but logs absent so causation NOT proven.
- Live monitor heartbeat age 1.95s, PID 6208 reported alive,
  status OBSERVING_NOT_ARMED, entry/close dispatch false.

## Attempt to certify automatic Windows restart
- Wrote isolated no-network child weex_sched_restart_probe_v27.py,
  first run exits 23, second run exits 0, persists PID/time.
- Attempted to register a SEPARATE S4U test task
  WEEX_Recovery_Restart_Probe_V27.
- Register-ScheduledTask returned AccessDenied 0x80070005.
- The test task was NOT registered. Neither the production scheduler
  task nor its running monitor was killed or reconfigured.
- Therefore automatic Windows restart after a real process crash
  remains NOT CERTIFIED.

## Offline validation
- Re-executed 23/23 tests PASS:
  isolated OS supervisor abrupt stop and process restart,
  real worker recovery branch with simulated WEEX reads,
  one-shot exit permit/close/readback chain with fake transport,
  prearm controller and CROSS veto.
- Test PID mismatch in initial V26 harness fixed; subsequent run PASS.
- No real WEEX entry, exit, cancellation, margin or leverage changes.
- No production one-shot permit created.

## Remaining constraints
1. Need permission to create isolated S4U task to certify Windows
   restart without touching production process, OR Windows event
   logging enabled and genuine restart evidence collected.
2. Need actual independently verified close authority one-shot
   and successful reduceOnly readback on pilot position.
3. Current manual CROSS exposure AINUSDT blocks the new pilot
   according to existing guard. No automatic eviction allowed.
4. Real post-ACK worker crash, durable UNKNOWN and readback still
   untested. Gate 9/10 NO_GO and bot STOPPED retained.
