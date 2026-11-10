"""Independent safe order provenance verifier: prevents caller-set ownership flags.
No exchange writes. Requires unique bot order binding and observed fills.
"""
from decimal import Decimal,InvalidOperation
def verify(client_id, local_bindings, history, fills):
 if not client_id:return {"verified":False,"reason":"MISSING_ID"}
 bindings=[b for b in local_bindings if b.get("clientOrderId")==client_id and b.get("state")=="ACKNOWLEDGED"]
 if len(bindings)!=1:return {"verified":False,"reason":"MISSING_OR_DUPLICATE_LOCAL_BINDING"}
 orders=[o for o in history if o.get("clientOrderId")==client_id and str(o.get("orderId"))==str(bindings[0].get("orderId"))]
 if len(orders)!=1:return {"verified":False,"reason":"MISSING_OR_DUPLICATE_EXCHANGE_ORDER"}
 order=orders[0]
 if order.get("symbol")!="ETHUSDT" or order.get("positionSide") not in ("LONG","SHORT"):
  return {"verified":False,"reason":"WRONG_MARKET_OR_SIDE"}
 matched=[f for f in fills if str(f.get("orderId"))==str(order["orderId"])]
 if not matched:return {"verified":False,"reason":"NO_EXCHANGE_FILL"}
 try:
  quantity=sum((Decimal(str(f["qty"])) for f in matched),Decimal(0))
  executed=Decimal(str(order["executedQty"]))
  if not quantity.is_finite() or quantity<=0 or quantity!=executed:raise ValueError
 except (KeyError,ValueError,TypeError,InvalidOperation):return {"verified":False,"reason":"FILL_MISMATCH"}
 return {"verified":True,"orderId":str(order["orderId"]),"quantity":str(quantity),
         "positionCloseAuthorized":False,"reason":"POSITION_ID_PROVENANCE_STILL_REQUIRED"}
