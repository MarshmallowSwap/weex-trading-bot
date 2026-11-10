"""Strict read-only reconciliation of demo exchange order fills with shadow lifecycle.
No position change from missing, duplicate or unowned order observations.
"""
from decimal import Decimal,InvalidOperation
from verified_order_state_sync import validate
def observe(client_id,orders,owned_ids):
 if client_id not in owned_ids:return {"accepted":False,"reason":"UNOWNED_CLIENT_ID"}
 verdict=validate(client_id,orders)
 if not verdict.get("verified"):return {"accepted":False,"reason":verdict.get("reason")}
 matches=[o for o in orders if str(o.get("clientOrderId") or "")==client_id]
 order=matches[0]
 symbol=order.get("symbol")
 if symbol!="BTCSUSDT":return {"accepted":False,"reason":"NOT_DEMO_SYMBOL"}
 status=verdict["target"]
 return {"accepted":True,"symbol":symbol,"clientOrderId":client_id,
   "exchangeOrderId":verdict["orderId"],"executedQty":verdict["filled"],
   "status":status,"applyToLifecycle":False,
   "reason":"Observation only; event-delta and order role must be verified before mutating state"}
