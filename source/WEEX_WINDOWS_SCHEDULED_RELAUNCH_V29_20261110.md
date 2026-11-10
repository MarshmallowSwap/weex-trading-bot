# WEEX — Windows scheduler periodic relaunch verification V29
Date: 2026-11-10

## Scope
- Separate task WEEX_Recovery_Repeat_Probe_V29, configured as
  interactive limited-user scheduled task, NOT production S4U.
- Trigger once after creation with repetition every 1 minute
  (for a bounded 4-minute duration).
- Probe executed no WEEX code, no exchange requests, no account writes.
- First run intentionally exited 23, with durable timestamp/PID.
- Second run occurred without Start-ScheduledTask intervention
  after initial registration; distinct PID and separate time.

## Evidence observed
- 2026-11-10T09:57:40.124310Z: pid 18360, deliberate exit 23.
- 2026-11-10T09:58:40.128474Z: pid 14676, exit 0.
- 60.004 seconds elapsed between the two runs.
- Output status AUTOMATIC_SCHEDULED_RELAUNCH_VERIFIED.
- Repetition trigger autonomously relaunched the process.
- This is NOT proof that RestartOnFailure fired: prior V28 task
  with only restart-on-failure settings did not relaunch in its
  observed window.
- This is NOT proof of actual S4U supervisor crash/restart.
  Production task does have a one-minute repetition trigger.
- V29 task removed safely after observing the successful relaunch.
  V29_TASK_EXISTS=False.

## Live production unaffected
- Main bot STOPPED; integrity=[].
- Account 1 manual AINUSDT CROSS position, 1 conditional order,
  0 regular orders, no unresolved writes.
- Release gate NO_GO 9/10:
  crash_restart_recovery_live_tested remains false.
- Independent monitor remains live, observing, not armed.
- Prearm blocked: exit permit missing, shared CROSS occupied,
  operational restart+exit drill not attested.

## Next certification step
- This is strong evidence of Windows periodic relaunch capability,
  but does not replace an audited exact protected-entry post-ACK
  crash, restart, no-duplicate entry, independent exact reduceOnly
  close, and verified final flat readback.
- Before any real test: explicit scoped authorization for any
  financial order/exit, protected position, fresh API budget,
  and no incompatible account-wide CROSS exposure.
