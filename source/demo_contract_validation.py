"""WEEX demo-order contract validator. Match documented API, never place orders.
No confirmed reduceOnly/close-only parameter on /capi/v3/sim/order.
"""
from decimal import Decimal,InvalidOperation
ALLOWED={"symbol","side","positionSide","type","quantity","newClientOrderId","price","timeInForce","tpTriggerPrice","slTriggerPrice","TpWorkingType","SlWorkingType"}
def validate(payload, *, purpose="ENTRY"):
 if not isinstance(payload,dict):return {"valid":False,"reason":"INVALID_PAYLOAD"}
 extra=set(payload)-ALLOWED
 if extra:return {"valid":False,"reason":"UNDOCUMENTED_FIELDS","fields":sorted(extra)}
 if payload.get("symbol")!="BTCSUSDT":return {"valid":False,"reason":"NOT_DEMO_ALLOWLIST"}
 if payload.get("side") not in ("BUY","SELL") or payload.get("positionSide") not in ("LONG","SHORT"):
  return {"valid":False,"reason":"INVALID_DIRECTION"}
 if purpose!="ENTRY":return {"valid":False,"reason":"CLOSE_ONLY_NOT_DOCUMENTED"}
 if payload.get("type") not in ("MARKET","LIMIT"):return {"valid":False,"reason":"BAD_TYPE"}
 if payload.get("type")=="LIMIT" and (payload.get("timeInForce") not in ("GTC","IOC","FOK") or "price" not in payload):
  return {"valid":False,"reason":"BAD_LIMIT_FIELDS"}
 cid=str(payload.get("newClientOrderId",""))
 import re
 if not re.fullmatch(r"[.A-Z:/a-z0-9_-]{1,36}",cid):return {"valid":False,"reason":"BAD_CLIENT_ID"}
 for field in ("quantity",)+( ("price",) if payload["type"]=="LIMIT" else ()):
  try:
   value=Decimal(str(payload[field]))
   if not value.is_finite() or value<=0:raise ValueError()
  except (KeyError,ValueError,InvalidOperation,TypeError):return {"valid":False,"reason":"BAD_"+field.upper()}
 return {"valid":True,"reason":"DOCUMENTED_DEMO_ENTRY_FORMAT_ONLY","exchangeAccepted":False,"orderSubmitted":False}
