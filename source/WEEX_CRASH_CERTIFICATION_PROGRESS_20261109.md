# WEEX — crash certification progress (2026-11-09)

Current independent gate: **9/10 NO_GO**. Missing: `crash_restart_recovery_live_tested`. Production worker STOPPED, account zero positions/orders/conditional at last authenticated readback. **Do not claim a real crash PASS.**

## Completed in this run

1. Rechecked independent gate. No production real worker crash evidence exists.
2. Added offline durable one-shot test-permission policy:
   - `weex_supervised_one_shot_permission_v4.py`
   - `test_weex_supervised_one_shot_permission_v4.py`
   - Binds immutable production client order ID and exact ETHUSDT protected order scope. Requires external approval, stopped bot, flat account, 100x account readback, verified close path/supervisor/API budget and fresh observation. Consumes a durable reservation before any hypothetical dispatch. Does **not** grant network dispatch, bypass the normal release gate or enable automated trading.
3. Checked WEEX documentation. `POST /capi/v3/order` supports explicit `reduceOnly=true` on market orders; `GET /capi/v3/order` exposes that field. `POST /capi/v3/closePositions` supports an exact `symbol + positionId` and returns `successOrderId` but does not accept a reduceOnly flag directly.
4. Added an offline exact MARKET reduceOnly exit planner:
   - `weex_supervised_reduce_only_close_plan_v4.py`
   - `test_weex_supervised_reduce_only_close_plan_v4.py`
   - Requires current exact position, attached stop, account CROSS 100x and no unrelated open orders; serializes exact SELL/LONG MARKET reduceOnly TRUE by SDK. **Preview only; does not send**.
5. 127 targeted offline unit/integration tests PASS, production code integrity PASS.

## Blocks before actual real-order crash certification

- A fully integrated, independently authorized **one-shot entry transport** bound to production worker Lifecycle; the V4 permission currently only reserves a durable permit and deliberately returns dispatchAllowed=false.
- Independently supervised restart/recovery/close with a separate process that can survive both worker and supervisor failures. The existing exact-close and reduceOnly builder are independent code pieces, not a completed, tested orchestration.
- Full exchange-semantics validation (native stop placement and exact reduce-only exit/flat account), preferably on WEEX API-SIM before the real pilot. This simulation would not satisfy production certification.
- End-to-end execution of an actual one-time protected entry, deliberate worker crash after real ACK, no duplicate retries, verified exact close and cancelled/consumed stop, resulting in flat account and independent proof.
- The real crash independent certificate must be earned from actual exchange and worker-journal data. Never modify it to output PASS without that evidence.

**Risk note:** 100x CROSS, even with a 0.3% native stop, carries liquidation and shared collateral exposure; no fixed max loss can be guaranteed. No real order has been opened in this run.
