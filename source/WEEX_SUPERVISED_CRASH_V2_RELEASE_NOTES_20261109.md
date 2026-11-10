# WEEX — supervised crash executor V2 (9 November 2026)

Status: **OFFLINE OS CRASH TEST PASS / REAL TEST NOT CERTIFIED / PRODUCTION STOPPED**

## Delivered
- `weex_supervised_crash_executor_v2.py`: scoped read-only production preflight and fully offline supervised OS-process crash simulation.
- `test_weex_supervised_crash_executor_v2.py`: regression tests on scope, leverage, contract tier, account, durable intent, replay prevention, stop identity and close.
- 78 relevant tests PASS (including production worker and lifecycle regressions).
- Production manifest hashes unchanged. No production executable modified, no production configuration enabled, no order sent.

## Verified offline
- Simulated child process exits with 79 after fake exchange ACK and before SQLite ACK.
- Intent stays UNKNOWN and the recovery forbids duplicate entry.
- Exactly one simulated entry, a matching exchange-style attached MARK_PRICE stop, and one simulated exact close.
- Read-only preflight fails closed if independent reconciliation is stale or ETH CROSS leverage is not 100x.
- Account last observed empty; release gate 9/10 NO_GO and proof gate NO_REAL_WORKER_CRASH_EVIDENCE.

## Work required before any real test
1. Implement and independently test production-worker-specific one-shot live authorization. Do not bypass the general GO gate; test authorization must be strictly distinct, use production Lifecycle journaling, and never enable the automatic scanner.
2. Preserve `slTriggerPrice` and `SlWorkingType` in the exact production order submitted, without changing normal strategy paths; independently verify the exchange-native stop ID against the parent order.
3. Configure ETHUSDT to CROSS 100x only with a fresh exchange tier check and readback, no implicit order placement.
4. Implement independently supervised, restart-resumable real-world recovery and exact-position reduceOnly exit. A crash of the supervisor must not strand a position. API exhaustion must fail closed without placing a new entry.
5. Test all failure windows and ambiguous responses without retrying an entry. Audit the production worker code hashes and independent exchange evidence at the end.
6. Only after the above is fully tested execute a bounded, one-shot real micro test, confirm flat account, then let the existing independent certificate determine release.
7. Maintain normal production trading STOPPED until gate genuinely returns GO. Strategy is 100x minimum, CROSS, ordinary SL OFF, and high risk.

## Commands (network-free drill)
```powershell
Set-Location D:\FUNDSHOT\weex_alerts
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_crash_executor_v2.py --drill
.\.venv_weex_live\Scripts\python.exe -m unittest -q test_weex_supervised_crash_executor_v2
```

## Read-only exchange preflight
```powershell
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_crash_executor_v2.py --read-only-preflight
```
This preflight currently blocks while ETHUSDT is not independently confirmed CROSS 100x, and may block on stale reconciliation. It **never** submits an order.
