# WEEX — supervised real crash V3 integration (2026-11-09)

## Summary
- **Production automatic trading** STOPPED. **Live release gate** 9/10 NO_GO.
- **Account ETHUSDT** configured CROSS **100x** on real WEEX, single setting-only POST and independent account configuration readback. Journal: `weex_eth_100x_leverage_setup_once.json`, VERIFIED_100X. No position or order opened.
- **Actual crash entry/close not yet executed**. Never mark release as passed from an offline crash.

## Delivered and validated
1. Production `weex_lifecycle.py` now preserves native MARK_PRICE stop fields for `entrySource=supervised_crash_pilot` exclusively. Hard constraints: ETHUSDT, LONG, 0.001 ETH, CROSS 100x, max $5 order notional, stop 0–0.5% below verified reference. Ordinary strategy behavior unchanged. Manifest hash updated and 98 scoped tests passed.
2. `weex_supervised_crash_executor_v2.py`: isolated OS-process crash (exit 79), durable UNKNOWN intent before simulated ACK, no duplicated entry, independent simulated readback and exact simulated close. Real-order sender NOT implemented.
3. `weex_supervised_real_recovery_v3.py`: production journal provenance; authenticated WEEX GET order history, exact orderId, native stop linked by clientAlgoId + parent orderId, exact positionId/size, fail-closed. No exchange writes. Readback unit tests passed.
4. `weex_supervised_exact_close100_v3.py`: separate **real-capable close-only SDK transport** for independently verified exact ETH positionId, with external authorization callback and persistent UNKNOWN close intent (no repeat POST). Not wired into any automated supervisor and never called against a live position. No entry support.
5. `weex_supervised_release_integration_audit_v3.py`: detects remaining blockers; production gate remains untouched.
6. `weex_eth_100x_leverage_setup_once.py`: single exact ETH CROSS 100x setting write; checked 100x official tier and empty account, irreversible request reservation before POST, real account readback afterward. Verified successful, no order writes.

## Still blocking actual test
- Develop and validate **distinct production-worker one-shot test permission** bound to exact immutable order + stop, market readback, user approval and supervisor; cannot enable ordinary strategy entries or change release GO logic.
- Independently supervise the actual crash/restart and ensure exact close occurs or manual emergency response is safely required, including supervisor crash and budget failure; don't assume a running Python supervisor is infallible.
- Demonstrate actual exchange entry ACK, durable UNKNOWN, linked native STOP, real fills, reduce-only close, cancellation of residual stop and account FLAT. Only the existing independent certificate may change release to GO.

## Risk
The 0.3% indicative stop is **not** a loss cap or guarantee. At 100x CROSS, rapid liquidation, slippage, API failure or shared collateral exposure are possible. Real trading remains STOPPED.

## Commands
```powershell
Set-Location D:\FUNDSHOT\weex_alerts
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_crash_executor_v2.py --drill
.\.venv_weex_live\Scripts\python.exe -B weex_supervised_release_integration_audit_v3.py
.\.venv_weex_live\Scripts\python.exe -B weex_final_live_status_readonly_20261109.py
```
