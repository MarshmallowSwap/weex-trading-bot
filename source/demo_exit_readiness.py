"""WEEX demo exit guard, matching the documented sim position schema.
This module NEVER submits an order. Only a uniquely bot-owned position may be considered.
"""
from decimal import Decimal,InvalidOperation
def check(position,owned_client_ids,*,demo_close_verified=False):
 if position.get("symbol")!="BTCSUSDT":return {"allowed":False,"reason":"NON_DEMO_SYMBOL"}
 if not demo_close_verified:return {"allowed":False,"reason":"DEMO_CLOSE_NOT_CERTIFIED"}
 side=position.get("side")
 if side not in ("LONG","SHORT"):return {"allowed":False,"reason":"AMBIGUOUS_HEDGE_SIDE"}
 if position.get("marginType") not in ("CROSSED","CROSS"):return {"allowed":False,"reason":"NOT_CROSS"}
 try:
  q=Decimal(str(position.get("size")))
  if not q.is_finite() or q<=0:raise ValueError()
 except (ValueError,InvalidOperation,TypeError):return {"allowed":False,"reason":"INVALID_POSITION_SIZE"}
 # WEEX position endpoint does not attest to the opening clientOrderId.
 # A local exchange-order binding is insufficient for attribution in mixed/manual positions.
 if position.get("ownershipVerified") is not True or position.get("manualOrMixed") is not False:
  return {"allowed":False,"reason":"POSITION_OWNERSHIP_UNVERIFIED"}
 if position.get("originClientOrderId") not in owned_client_ids:
  return {"allowed":False,"reason":"UNOWNED_POSITION"}
 return {"allowed":True,"closingSide":"SELL" if side=="LONG" else "BUY",
         "positionSide":side,"quantity":str(q),"ordersSubmitted":False}
