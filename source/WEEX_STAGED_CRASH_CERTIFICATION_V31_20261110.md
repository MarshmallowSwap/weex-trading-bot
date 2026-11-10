# WEEX V31 — staged pre-entry / post-crash certification audit
Date: 2026-11-10

## Scope
- Added weex_staged_crash_certification_v31.py, read-only
  classifier to distinguish conditions required BEFORE real
  pilot entry from those only provable AFTER intentional
  post-ACK worker crash.
- Added test_weex_staged_crash_certification_v31.py.
- 12/12 regression tests PASS together with real worker
  branch and independent supervisor OS crash tests.
- Does not modify production gate, permit, heartbeat,
  orders, account, leverage or AINUSDT.

## Pre-entry conditions
- Independent S4U task and heartbeat observed.
- Preflight API headroom temporarily failed earlier in turn,
  recovered in subsequent check; quota is time varying.
- Actual EXIT one-shot operator permit NOT present.
- CROSS account snapshot during final check was expired;
  report explicitly marks occupancy UNVERIFIED and blocks,
  never infers account flat.
- Independent promotion controller not certified and
  production heartbeat still OBSERVING_NOT_ARMED.
- Prior fresh account reads confirm AINUSDT manual CROSS
  with a conditional TP, but such reads must be refreshed
  before any live authorization.

## Post-crash evidence not yet produced
- Real durable UNKNOWN after exact protected entry.
- Independently verified attached stop and position.
- Real worker restart with zero duplicate entry.
- Single reduceOnly close and exact exchange execution.
- Verified ETH flat and termination of attached stop.
These are AFTER-crash requirements, not circular BEFORE-entry
conditions. No fake positive release.

## Outcome
- STAGED_LIVE_TRIAL_NO_GO.
- Existing release 9/10 NO_GO, STOPPED, integrity=[],
  1 manual position, 1 conditional, 0 regular orders,
  no unresolved writes.
- No financial exchange writes; AINUSDT and TP untouched.

## Engineering next steps
- Design and attest an actual independent supervisor promotion
  controller under verified functional recovery and exit capability,
  rather than treating heartbeat or unit tests as READY_TO_RECOVER.
- Acquire explicit exit-only authorization for a fully specified
  operation after eligibility conditions are met; no automatic grant.
- Require fresh account-wide CROSS flat snapshot and API budget.
- Only then run a bounded real-money pilot with separate authorization.
