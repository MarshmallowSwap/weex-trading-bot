# WEEX — Live post-ACK crash admission and recovery test, V30
Date: 2026-11-10

## Read-only account / trial admission
- Live switch STOPPED, code integrity empty errors.
- Account: 1 manual AINUSDT CROSS position, 1 conditional TP,
  0 regular orders, 0 unresolved writes.
- Release 9/10 NO_GO: crash_restart_recovery_live_tested outstanding.
- Independent supervision: S4U task and heartbeat verified.
- API headroom ready, exact SDK reduceOnly preview pass.
- Live one-shot exit permit absent.
- True live crash trial admission failed with:
  SUPERVISOR_NOT_READY_TO_RECOVER,
  SHARED_CROSS_ACCOUNT_NOT_FLAT,
  EXACT_EXIT_PERMIT_NOT_AUTHORIZED.
- No live entry was attempted.

## Actual real worker CLI recovery branch
- 18/18 isolated unit/integration tests PASS for genuine
  worker subprocess (with synthetic exchange proofs), monouse
  close transport, OS process restart and CROSS trial admission.
- Executed actual weex_live_worker.py --supervised-crash-recovery
  against its own real production journal:
  status RECOVERY_READBACK_UNCERTAIN,
  errorType RecoveryBlocked,
  ordersSent=0, entryRetries=0.
- This is the correct fail-closed result without a real
  post-ACK durable UNKNOWN entry journal. It does not
  demonstrate a successfully recovered live position.
- Subsequent live status STOPPED, 1 position, 1 conditional,
  0 regular, no unresolved writes, 9/10 NO_GO.

## Not certified
- No real post-ACK worker crash with live protected pilot exposure.
- No independent successful real reduceOnly emergency close.
- No proof of flat ETH after emergency close.
- No READY_TO_RECOVER publication.
- No orders, cancellations, leverage or margin edits
  executed during this intervention.
- Manual AINUSDT and its protective TP remain untouched.

## Needed before live test
1. Verify genuinely operational independent failover and safe
   close authority under a bounded one-shot test permit.
2. Require fresh account-wide CROSS admission; current AINUSDT
   disqualifies additional pilot entry.
3. Only then separate authorization for small real entry/exit.
4. Verify crash post-ACK -> unique durable UNKNOWN ->
   real worker GET-only restart -> exact stop readback ->
   one-shot reduceOnly close -> flat confirmation.
No gate bypass, no fake 10/10.
