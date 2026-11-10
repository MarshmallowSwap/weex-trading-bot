# WEEX V32 — proof of actual API-SIM recovery vs production readiness
2026-11-10

## Direct observations
- Production bot STOPPED, no build integrity errors.
- One manual CROSS AINUSDT position plus one conditional TP,
  no regular orders or unresolved exchange write journal.
- Live release 9/10 NO_GO, missing real post-ACK crash certification.
- S4U independent monitor and heartbeat observed, still
  OBSERVING_NOT_ARMED. Production promotion is not yet implemented.
- API reserve 220/490 remaining during first inspection,
  preflight 250 reserve not satisfied. Recovery-only fits.

## Existing real network demonstration (not newly dispatched)
- Read actual existing WEEX API-SIM report from Nov 9:
  weex_demo_crash_recovery_20261109_result.json
- API destination https://api-sim.weex.com
- Child process exit 73 after demo protected order submission;
  durable child stage ENTRY_OUTCOME_UNKNOWN.
- Exchange demo order history shows one unique filled entry.
- One attached stop verified, zero duplicate entries.
- One demo close POST with ACK; complete GET account readback
  0 positions, 0 regular orders, 0 algo orders.
- Zero retries, zero production order submissions.
- Evidence accepted as SIM_EXCHANGE_POST_ACK_CRASH_AND_CLOSE_VERIFIED
  by new weex_demo_evidence_acceptance_v32.py
- New 4 unit tests plus 4 exit chain tests: 8/8 PASS.

## What this does NOT prove
- The API-SIM test used a separate demo crash child and parent,
  NOT the production S4U monitor + true production worker chain.
- Production monitor hardcodes OBSERVING_NOT_ARMED.
- Missing operator-approved one-shot exit permit.
- Shared CROSS collateral is occupied by AINUSDT.
- No real production post-ACK UNKNOWN -> restart -> reduceOnly
  close -> exact flat readback proof, so remain 9/10 NO_GO.

## Actions
- No real WEEX entry or close and no change to AINUSDT/TP,
  leverage, live gate, supervisor task or real exit permit.
- Next engineering work is an independent S4U supervisor
  capability proof linked to the production worker and exit
  executor. Production readiness must not be inferred from
  successful API-SIM or synthetic tests.
