# WEEX supervised crash V3 — real-account integration status

**Result:** real-account authenticated readback and recovery verification module implemented; actual order dispatch intentionally blocked. Production LIVE remains STOPPED. Independent release gate remains 9/10 NO_GO.

## Artifacts

- `weex_supervised_crash_executor_v2.py`: scoped ETHUSDT CROSS 100x preflight, max $5 order notional, exchange-attached MARK_PRICE stop (indicative offset 0.3%), standalone offline child crash with durable SQLite intent and no retry.
- `weex_supervised_real_recovery_v3.py`: actual production journal read-only provenance and authenticated GET history -> exact orderId lookup -> parent-child protective stop -> exact open position verification; no POST or DELETE.
- `weex_supervised_release_integration_audit_v3.py`: checks existing code hash, production gate, pilot ID, source-code stop behavior and exact-close adapter compatibility; explicit BLOCKED_FOR_REAL_POST.
- `test_weex_supervised_crash_executor_v2.py`, `test_weex_supervised_real_recovery_v3.py`, `test_weex_supervised_real_reader_v3.py`: offline and injected-readback tests.

## Certified observations

- Offline real OS child crash exit 79 between simulated ACK and local journal ACK; immutable UNKNOWN prevents any repeat entry.
- The test client ID is now calculated via the same SHA-256 signal ID algorithm and wxentry_ prefix as production Lifecycle.
- The WEEX SDK order detail GET accepts **orderId** only; the verifier first discovers an unambiguous client ID through bounded order-history GET, then reads exact orderId.
- Stop verification requires exact `clientAlgoId=entryId+'sl'`, parent orderId, side, quantity, trigger, reduceOnly, MARK_PRICE, and active status.
- STOP_PCT adjusted from 1.5% to 0.3% for the theoretical 100x pilot. This is *not* a liquidation or max-loss guarantee. CROSS shared collateral remains exposed.
- 87 combined offline tests PASS as of latest run; test files updated to real production ID namespace.
- Last real account check showed zero positions/orders; production worker code unchanged and integrity PASS.

## Blocking integration requirements — DO NOT SEND THE REAL TEST ORDER YET

1. Production Lifecycle `prepare` currently **drops exchange-native stop fields** when constructing the immutable entry payload. The supervised pilot must preserve them through production code and SDK serialization without altering ordinary strategy orders.
2. Existing exact-position close adapter is restricted to an old **ISOLATED 1x** pilot. CROSS 100x needs independent close-only authorization, exact live positionId, durable journal and separate recovery supervisor, including supervisor process crash.
3. Production `dispatch_permission` requires release GO; a separate, strictly one-shot test-only permission must be designed, tested, and reviewed **without weakening normal GO requirements or permitting strategy entries**.
4. The resulting real worker ACK crash, independent exchange order/stop/fills/close proof and final flat account must actually occur before the independent release certification can change.
5. ETHUSDT account setting was last confirmed **CROSSED 50x**, not 100x. Any future test must explicitly set + independently readback 100x, confirming official risk tiers for 0.001 ETH.

No test order, setting write, close request or production activation occurred in this V3 integration work. No existing gate or test evidence was falsified.

## Safe checks

```powershell
Set-Location D:\FUNDSHOT\weex_alerts
.\.venv_weex_live\Scripts\python.exe -m unittest -q test_weex_supervised_real_reader_v3 test_weex_supervised_real_recovery_v3 test_weex_supervised_crash_executor_v2
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_crash_executor_v2.py --drill
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_release_integration_audit_v3.py
```
